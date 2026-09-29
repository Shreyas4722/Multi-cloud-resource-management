"""Recommendations: sortable table, filters, savings-by-rule chart, CSV export."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import io

import pandas as pd
import plotly.express as px
import streamlit as st

from common import config_missing, get_recommendations_cached, has_synced_data, page_header, render_sidebar_filters, show_empty_state
from theme import apply_layout

st.set_page_config(page_title="Recommendations - CloudLens", page_icon="☁️", layout="wide")

page_header("Recommendations", "💡")

if config_missing():
    st.warning("No config.yaml found. Run `cloudlens init` from a terminal first.")
    st.stop()

filters = render_sidebar_filters()

if not has_synced_data():
    show_empty_state()
    st.stop()

recommendations = [r for r in get_recommendations_cached() if r.provider in filters["providers"]]

if not recommendations:
    st.info("No recommendations yet. Run analyze (Settings page, or `cloudlens analyze`).")
    st.stop()

col1, col2, col3 = st.columns(3)
rule_ids = sorted({r.rule_id for r in recommendations})
severities = sorted({r.severity.value for r in recommendations})
rule_filter = col1.multiselect("Rule", rule_ids, default=rule_ids)
severity_filter = col2.multiselect("Severity", severities, default=severities)
min_saving = col3.number_input("Minimum monthly saving ($)", min_value=0.0, value=0.0, step=10.0)

filtered = [
    r
    for r in recommendations
    if r.rule_id in rule_filter and r.severity.value in severity_filter and r.estimated_monthly_saving >= min_saving
]
filtered.sort(key=lambda r: r.estimated_monthly_saving, reverse=True)

st.caption(f"{len(filtered)} of {len(recommendations)} recommendations")

left, right = st.columns([2, 1])

with left:
    if filtered:
        df = pd.DataFrame(
            [
                {
                    "Severity": r.severity.value,
                    "Title": r.title,
                    "Provider": r.provider,
                    "Rule": r.rule_id,
                    "Current Monthly Cost": round(r.current_monthly_cost, 2),
                    "Estimated Saving": round(r.estimated_monthly_saving, 2),
                    "Suggested Action": r.suggested_action,
                }
                for r in filtered
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            "Download filtered recommendations as CSV",
            data=csv_buffer.getvalue(),
            file_name="recommendations.csv",
            mime="text/csv",
        )
    else:
        st.info("No recommendations match the current filters.")

with right:
    st.subheader("Savings by Rule")
    by_rule = (
        pd.DataFrame([{"rule_id": r.rule_id, "saving": r.estimated_monthly_saving} for r in filtered])
        .groupby("rule_id", as_index=False)["saving"]
        .sum()
        .sort_values("saving", ascending=True)
    )
    if by_rule.empty:
        st.caption("No data.")
    else:
        fig = px.bar(by_rule, x="saving", y="rule_id", orientation="h")
        fig.update_traces(marker_color="#22C55E")
        apply_layout(fig)
        st.plotly_chart(fig, width="stretch")

st.caption("Instance and storage prices used for savings estimates are approximate reference values, not live pricing.")
