"""Cost Explorer: daily trend and breakdowns by provider, service, project, region."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from common import (
    config_missing,
    get_cost_summary_cached,
    has_synced_data,
    page_header,
    render_sidebar_filters,
    show_empty_state,
)
from theme import PROVIDER_COLORS, apply_layout

st.set_page_config(page_title="Cost Explorer - CloudLens", page_icon="☁️", layout="wide")

page_header("Cost Explorer", "💰")

if config_missing():
    st.warning("No config.yaml found. Run `cloudlens init` from a terminal first.")
    st.stop()

filters = render_sidebar_filters()

if not has_synced_data():
    show_empty_state()
    st.stop()

providers = tuple(filters["providers"])
start_date, end_date = filters["start_date"], filters["end_date"]

st.subheader("Daily Cost Trend")
daily = get_cost_summary_cached(group_by="date", start_date=start_date, end_date=end_date, providers=providers)
if daily.empty:
    st.caption("No cost data in the selected date range.")
else:
    fig = px.line(daily, x="date", y="total_cost", markers=True)
    fig.update_traces(line_color="#22C55E", fill="tozeroy", fillcolor="rgba(34,197,94,0.15)")
    apply_layout(fig)
    st.plotly_chart(fig, width="stretch")

st.divider()

col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

breakdowns = [
    ("provider", "By Provider", col1),
    ("service", "By Service", col2),
    ("project", "By Project", col3),
    ("region", "By Region", col4),
]

for group_by, title, col in breakdowns:
    with col:
        st.subheader(title)
        df = get_cost_summary_cached(group_by=group_by, start_date=start_date, end_date=end_date, providers=providers)
        if df.empty:
            st.caption("No data.")
            continue
        color_arg = {}
        if group_by == "provider":
            color_arg = dict(color="provider", color_discrete_map=PROVIDER_COLORS)
        fig = px.bar(df.head(15), x="total_cost", y=group_by, orientation="h", **color_arg)
        fig.update_layout(yaxis=dict(categoryorder="total ascending"), showlegend=False)
        apply_layout(fig)
        st.plotly_chart(fig, width="stretch")
