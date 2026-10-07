"""Budgets: per-project progress bars, forecast, and active alerts."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import streamlit as st

from common import config_missing, get_budget_status_cached, has_synced_data, page_header, render_sidebar_filters, show_empty_state

st.set_page_config(page_title="Budgets - CloudLens", page_icon="☁️", layout="wide")

page_header("Budgets", "📊")

if config_missing():
    st.warning("No config.yaml found. Run `cloudlens init` from a terminal first.")
    st.stop()

render_sidebar_filters()

if not has_synced_data():
    show_empty_state()
    st.stop()

statuses = get_budget_status_cached()

if not statuses:
    st.info("No budgets configured. Add entries under `budgets:` in config.yaml.")
    st.stop()

for status in statuses:
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(status.project)
            progress = min(status.percent_used / 100, 1.0)
            st.progress(progress)
            st.caption(
                f"₹{status.spent:,.2f} spent of ₹{status.monthly_limit:,.2f} "
                f"({status.percent_used:.1f}%) this month ({status.month})"
            )
        with col2:
            st.metric(
                "Forecast (month end)",
                f"₹{status.forecast_month_end:,.2f}",
                delta=f"{status.forecast_month_end - status.monthly_limit:,.2f} vs limit",
                delta_color="inverse",
            )

        if status.forecast_exceeds_budget:
            st.error(f"Forecast to exceed budget by ₹{status.forecast_month_end - status.monthly_limit:,.2f}.")

        if status.alerts:
            for alert in sorted(status.alerts, key=lambda a: a.threshold_crossed):
                st.warning(
                    f"Crossed {alert.threshold_crossed}% threshold: "
                    f"₹{alert.spent:,.2f} / ₹{alert.limit:,.2f} ({alert.percent_used:.1f}%)"
                )
        else:
            st.caption("No thresholds crossed yet this month.")
