"""Settings: active providers, enabled rules/thresholds, and a manual re-sync."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import clear_data_caches, config_missing, get_cloudlens, page_header, run_sync_and_analyze

st.set_page_config(page_title="Settings - CloudLens", page_icon="☁️", layout="wide")

page_header("Settings", "⚙️")

if config_missing():
    st.warning("No config.yaml found. Run `cloudlens init` from a terminal first.")
    st.stop()

cl = get_cloudlens()
config = cl.config

st.subheader("Run Pipeline")
st.caption(f"Config file: `{cl.config_path}`  |  Database: `{config.database.path}`")
if st.button("Re-run sync + analyze now", type="primary"):
    run_sync_and_analyze()
    st.success("Sync and analysis complete.")
    st.rerun()

st.divider()

st.subheader("Providers")
provider_rows = []
for name in ["aws", "azure", "gcp", "demo"]:
    provider_cfg = getattr(config.providers, name)
    provider_rows.append({"Provider": name, "Enabled": provider_cfg.enabled})
st.dataframe(pd.DataFrame(provider_rows), width="stretch", hide_index=True)
if config.demo_mode:
    st.caption("`demo_mode: true` -- only the demo provider is used regardless of the flags above.")

st.divider()

st.subheader("Optimization Rules")
rule_rows = [
    {"Rule": rule_id, "Enabled": rule_cfg.enabled, "Parameters": ", ".join(f"{k}={v}" for k, v in rule_cfg.params.items()) or "-"}
    for rule_id, rule_cfg in sorted(config.rules.items())
]
st.dataframe(pd.DataFrame(rule_rows), width="stretch", hide_index=True)

st.divider()

st.subheader("Required Tags")
st.write(", ".join(config.required_tags) or "None configured")

st.divider()

st.subheader("Budgets")
budget_rows = [
    {"Project": b.project, "Monthly Limit": f"${b.monthly_limit:,.2f}", "Thresholds": ", ".join(f"{t}%" for t in b.alert_thresholds)}
    for b in config.budgets
]
st.dataframe(pd.DataFrame(budget_rows), width="stretch", hide_index=True)

st.caption(
    "Instance and storage prices used to estimate savings (cloudlens/data/pricing.json) "
    "are approximate on-demand reference values, not live pricing."
)
