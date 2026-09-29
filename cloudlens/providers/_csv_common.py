"""Shared CSV-parsing helpers for the Azure and GCP adapters.

Both providers ingest the same shape of data -- a billing/cost export CSV
plus a resource inventory CSV, with column names mapped through config -- so
the parsing logic is shared here and each adapter only supplies its provider
name, config and column mapping.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pandas as pd

from cloudlens.config import ColumnMapping
from cloudlens.models import CostRecord, Resource, ResourceState, ResourceType
from cloudlens.normalizer import normalize_resource_type, normalize_state
from cloudlens.pricing import load_pricing


def parse_tags(raw) -> dict[str, str]:
    """Best-effort parse of a tags/labels cell into a dict.

    Handles JSON objects (`{"project": "web-app"}`) and delimited key=value
    pairs (`project=web-app;owner=alice`). Returns {} for anything else,
    including missing/NaN cells.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return {}
    text = str(raw).strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            return {str(k): str(v) for k, v in json.loads(text).items()}
        except (json.JSONDecodeError, AttributeError):
            return {}
    tags: dict[str, str] = {}
    for pair in text.replace(",", ";").split(";"):
        if "=" in pair:
            key, _, value = pair.partition("=")
            key, value = key.strip(), value.strip()
            if key:
                tags[key] = value
    return tags


def load_cost_csv(path: str, provider: str, account_id: str, mapping: ColumnMapping) -> list[CostRecord]:
    """Load a cost export CSV into `CostRecord`s using `mapping.cost`."""
    m = mapping.cost
    df = pd.read_csv(path)
    dates = pd.to_datetime(df[m["date"]]).dt.date

    records: list[CostRecord] = []
    for i, row in df.iterrows():
        resource_id = row.get(m["resource_id"]) if m.get("resource_id") else None
        project = row.get(m["project"]) if m.get("project") else None
        currency = row.get(m["currency"], "USD") if m.get("currency") else "USD"
        records.append(
            CostRecord(
                provider=provider,
                account_id=account_id,
                resource_id=str(resource_id) if pd.notna(resource_id) else None,
                service=str(row[m["service"]]),
                project=str(project) if pd.notna(project) else None,
                date=dates[i],
                amount=float(row[m["amount"]]),
                currency=str(currency) if pd.notna(currency) else "USD",
            )
        )
    return records


def load_inventory_csv(path: str, provider: str, account_id: str, mapping: ColumnMapping) -> list[Resource]:
    """Load a resource inventory CSV into `Resource`s using `mapping.inventory`."""
    m = mapping.inventory
    df = pd.read_csv(path)
    compute_prices = load_pricing().get(provider, {}).get("compute", {})

    resources: list[Resource] = []
    for _, row in df.iterrows():
        size = row.get(m["size"]) if m.get("size") else None
        size = str(size) if pd.notna(size) else None
        tags = parse_tags(row.get(m["tags"])) if m.get("tags") else {}
        resource_type = normalize_resource_type(provider, str(row[m["type"]]))

        created_raw = row.get(m["created_at"]) if m.get("created_at") else None
        created_at = pd.to_datetime(created_raw).to_pydatetime() if pd.notna(created_raw) else datetime.now(timezone.utc)

        hourly_cost = compute_prices.get(size, {}).get("hourly", 0.0) if size else 0.0
        state = normalize_state(provider, str(row[m["state"]]))

        # CSV inventories carry no dedicated attachment column, but a storage
        # volume's own state ("unattached" vs. everything else) is the
        # signal the unattached-storage rule needs.
        attached = state != ResourceState.UNATTACHED if resource_type == ResourceType.STORAGE else None

        resources.append(
            Resource(
                id=str(row[m["id"]]),
                provider=provider,
                account_id=account_id,
                region=str(row[m["region"]]),
                resource_type=resource_type,
                instance_size=size,
                state=state,
                tags=tags,
                created_at=created_at,
                hourly_cost=hourly_cost,
                project=tags.get("project"),
                attached=attached,
            )
        )
    return resources
