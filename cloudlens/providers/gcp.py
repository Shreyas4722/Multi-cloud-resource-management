"""GCP provider adapter: imports a Google Cloud billing export CSV plus a
resource inventory export CSV. Column names are mapped through config so
different GCP export formats are supported without code changes.
"""

from __future__ import annotations

from datetime import date

from cloudlens.config import CSVProviderConfig
from cloudlens.models import CostRecord, Resource, UtilizationStats
from cloudlens.providers._csv_common import load_cost_csv, load_inventory_csv
from cloudlens.providers.base import ProviderAdapter
from cloudlens.registry import register_provider


@register_provider("gcp")
class GCPAdapter(ProviderAdapter):
    """Read-only adapter for GCP, sourced entirely from exported CSVs."""

    def __init__(self, config: CSVProviderConfig):
        self.config = config

    def name(self) -> str:
        return "gcp"

    def fetch_resources(self) -> list[Resource]:
        if not self.config.inventory_csv_path:
            return []
        return load_inventory_csv(self.config.inventory_csv_path, "gcp", self.config.account_id, self.config.column_mapping)

    def fetch_costs(self, start_date: date, end_date: date) -> list[CostRecord]:
        if not self.config.cost_csv_path:
            return []
        records = load_cost_csv(self.config.cost_csv_path, "gcp", self.config.account_id, self.config.column_mapping)
        return [r for r in records if start_date <= r.date <= end_date]

    def fetch_utilization(self, resource_id: str, days: int) -> UtilizationStats | None:
        # CPU utilization is not present in GCP billing/inventory CSV exports.
        return None
