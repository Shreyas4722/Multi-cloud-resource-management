"""CloudLens dashboard entry point and Overview page."""

from __future__ import annotations

from datetime import date

import streamlit as st

from common import (
    config_missing,
    get_budget_status_cached,
    get_cost_summary_cached,
    get_recommendations_cached,
    has_synced_data,
    page_header,
    render_sidebar_filters,
    run_sync_and_analyze,
    show_empty_state,
)

st.set_page_config(page_title="CloudLens", page_icon="☁️", layout="wide")


def main() -> None:
    page_header("CloudLens Overview", "☁️")

    if config_missing():
        st.warning(
            "No config.yaml found. Copy config.example.yaml to config.yaml, "
            "or run `cloudlens init` from a terminal, then reload this page."
        )
        return

    filters = render_sidebar_filters()

    if not has_synced_data():
        show_empty_state()
        return

    if st.sidebar.button("Sync + analyze now"):
        run_sync_and_analyze()
        st.rerun()

    today = date.today()
    month_start = today.replace(day=1)
    provider_costs = get_cost_summary_cached(
        group_by="provider", start_date=month_start, end_date=today, providers=tuple(filters["providers"])
    )

    recommendations = [r for r in get_recommendations_cached() if r.provider in filters["providers"]]
    total_savings = sum(r.estimated_monthly_saving for r in recommendations)
    total_spend = provider_costs["total_cost"].sum() if not provider_costs.empty else 0.0

    budget_statuses = get_budget_status_cached()
    total_alerts = sum(len(s.alerts) for s in budget_statuses)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Month-to-Date Spend", f"${total_spend:,.0f}")
    col2.metric("Potential Monthly Savings", f"${total_savings:,.0f}")
    col3.metric("Open Recommendations", f"{len(recommendations)}")
    col4.metric("Active Budget Alerts", f"{total_alerts}")

    st.subheader("Spend by Provider (this month)")
    if provider_costs.empty:
        st.caption("No cost data for the selected providers.")
    else:
        cols = st.columns(len(provider_costs))
        for col, (_, row) in zip(cols, provider_costs.iterrows()):
            col.metric(row["provider"].upper(), f"${row['total_cost']:,.0f}")

    st.caption(
        "All figures come from the CloudLens public API (`get_cost_summary`, "
        "`get_recommendations`, `get_budget_status`). Instance/storage prices used "
        "for savings estimates are approximate reference values, not live pricing."
    )


main()
