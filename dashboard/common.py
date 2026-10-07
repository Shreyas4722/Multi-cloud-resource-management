"""Shared dashboard plumbing: the cached `CloudLens` instance, cached queries,
sidebar filters, and small render helpers.

Every function here either wraps a call into the `cloudlens` public API or
renders a widget -- no optimization/budget logic lives in the dashboard.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from cloudlens import CloudLens
from cloudlens.models import ResourceType

CONFIG_PATH = "config.yaml"
DATA_TTL_SECONDS = 60
ALL_PROVIDERS = ["aws", "azure", "gcp"]


@st.cache_resource
def get_cloudlens() -> CloudLens:
    """One CloudLens instance per Streamlit session, shared across all pages."""
    return CloudLens(config_path=CONFIG_PATH)


def config_missing() -> bool:
    from pathlib import Path

    return not Path(CONFIG_PATH).exists()


def has_synced_data() -> bool:
    return len(get_resources_cached()) > 0


def run_sync_and_analyze() -> None:
    cl = get_cloudlens()
    with st.spinner("Syncing resources and costs..."):
        cl.sync()
    with st.spinner("Running rules and budget checks..."):
        cl.analyze()
    clear_data_caches()


def clear_data_caches() -> None:
    """Drop all cached query results. Called after a re-sync from Settings."""
    get_resources_cached.clear()
    get_recommendations_cached.clear()
    get_cost_summary_cached.clear()
    get_budget_status_cached.clear()


@st.cache_data(ttl=DATA_TTL_SECONDS)
def get_resources_cached(provider: str | None = None, resource_type: str | None = None):
    cl = get_cloudlens()
    rt = ResourceType(resource_type) if resource_type else None
    return cl.get_resources(provider=provider, resource_type=rt)


@st.cache_data(ttl=DATA_TTL_SECONDS)
def get_recommendations_cached(provider: str | None = None, min_saving: float = 0.0):
    cl = get_cloudlens()
    return cl.get_recommendations(provider=provider, min_saving=min_saving)


@st.cache_data(ttl=DATA_TTL_SECONDS)
def get_cost_summary_cached(
    group_by: str = "provider",
    start_date: date | None = None,
    end_date: date | None = None,
    providers: tuple[str, ...] | None = None,
):
    cl = get_cloudlens()
    return cl.get_cost_summary(
        group_by=group_by, start_date=start_date, end_date=end_date, providers=list(providers) if providers else None
    )


@st.cache_data(ttl=DATA_TTL_SECONDS)
def get_budget_status_cached():
    cl = get_cloudlens()
    return cl.get_budget_status()


# -- sidebar / layout helpers ---------------------------------------------


def render_sidebar_filters() -> dict:
    """Render the global provider + date-range filters. Selections live in
    `st.session_state` (keyed by widget key), so they persist across pages."""
    st.sidebar.header("Filters")
    st.sidebar.multiselect("Providers", ALL_PROVIDERS, default=ALL_PROVIDERS, key="provider_filter")

    today = date.today()
    st.sidebar.date_input(
        "Date range",
        value=(today - timedelta(days=30), today),
        key="date_range",
    )

    providers = st.session_state.get("provider_filter", ALL_PROVIDERS) or ALL_PROVIDERS
    date_range = st.session_state.get("date_range", (today - timedelta(days=30), today))
    if not isinstance(date_range, tuple) or len(date_range) != 2:
        date_range = (today - timedelta(days=30), today)

    return {"providers": providers, "start_date": date_range[0], "end_date": date_range[1]}


def show_empty_state() -> None:
    st.warning("No data yet. Run a sync to fetch resources and costs.")
    if st.button("Run sync + analyze now", type="primary"):
        run_sync_and_analyze()
        st.rerun()


def page_header(title: str, icon: str = "") -> None:
    st.title(f"{icon} {title}".strip())
