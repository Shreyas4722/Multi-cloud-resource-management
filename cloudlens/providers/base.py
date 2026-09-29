"""Abstract base class every provider adapter must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from cloudlens.models import CostRecord, Resource, UtilizationStats


class ProviderAdapter(ABC):
    """Standard interface for a cloud provider data source.

    A provider adapter is a read-only data source: it fetches resources,
    costs and utilization from a cloud account or from exported files, and
    returns them as raw provider-native objects (dicts). The normalizer
    converts that raw output into the common models. Adapters never create,
    modify or delete cloud resources.
    """

    @abstractmethod
    def name(self) -> str:
        """Return the provider's short name, e.g. "aws", "azure", "gcp", "demo"."""

    @abstractmethod
    def fetch_resources(self) -> list[Resource]:
        """Return all resources visible to this adapter, already normalized."""

    @abstractmethod
    def fetch_costs(self, start_date: date, end_date: date) -> list[CostRecord]:
        """Return daily cost records between start_date and end_date, inclusive."""

    @abstractmethod
    def fetch_utilization(self, resource_id: str, days: int) -> UtilizationStats | None:
        """Return utilization stats for a resource over the trailing `days`.

        Returns None if utilization data is not available for the resource
        (e.g. storage resources, which have no CPU metric).
        """
