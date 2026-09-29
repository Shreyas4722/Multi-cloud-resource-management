"""Loader for the bundled approximate pricing reference table."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def load_pricing() -> dict:
    """Load `cloudlens/data/pricing.json`, cached after the first call.

    Prices in this table are approximate on-demand reference values, not live
    pricing -- callers that surface them (rules, dashboard) should label them
    as such.
    """
    data = resources.files("cloudlens.data").joinpath("pricing.json").read_text()
    return json.loads(data)
