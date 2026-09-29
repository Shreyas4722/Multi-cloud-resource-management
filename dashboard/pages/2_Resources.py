"""Resources: searchable, filterable table of every synced resource."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import config_missing, get_resources_cached, has_synced_data, page_header, render_sidebar_filters, show_empty_state

st.set_page_config(page_title="Resources - CloudLens", page_icon="☁️", layout="wide")

page_header("Resources", "🖥️")

if config_missing():
    st.warning("No config.yaml found. Run `cloudlens init` from a terminal first.")
    st.stop()

filters = render_sidebar_filters()

if not has_synced_data():
    show_empty_state()
    st.stop()

resources = [r for r in get_resources_cached() if r.provider in filters["providers"]]

col1, col2, col3 = st.columns(3)
resource_types = sorted({r.resource_type.value for r in resources})
states = sorted({r.state.value for r in resources})
type_filter = col1.multiselect("Resource type", resource_types, default=resource_types)
state_filter = col2.multiselect("State", states, default=states)
search = col3.text_input("Search (id, size, tags)", "")

filtered = [r for r in resources if r.resource_type.value in type_filter and r.state.value in state_filter]
if search:
    needle = search.lower()
    filtered = [
        r
        for r in filtered
        if needle in r.id.lower()
        or (r.instance_size or "").lower().find(needle) >= 0
        or any(needle in f"{k}={v}".lower() for k, v in r.tags.items())
    ]

st.caption(f"{len(filtered)} of {len(resources)} resources")

if not filtered:
    st.info("No resources match the current filters.")
else:
    df = pd.DataFrame(
        [
            {
                "ID": r.id,
                "Provider": r.provider,
                "Region": r.region,
                "Type": r.resource_type.value,
                "Size": r.instance_size,
                "State": r.state.value,
                "Project": r.project,
                "Tags": ", ".join(f"{k}={v}" for k, v in r.tags.items()),
                "Monthly Cost": round(r.monthly_cost, 2),
            }
            for r in filtered
        ]
    )
    st.dataframe(df, width="stretch", hide_index=True)
