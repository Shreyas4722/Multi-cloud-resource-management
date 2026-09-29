"""Common Pydantic data models shared by every layer of the framework.

Provider adapters produce raw, provider-specific data. The normalizer converts
that raw data into these models. Every layer downstream of the normalizer
(storage, rules engine, budget engine, consumers) only ever sees these models.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """Normalized resource categories, common across all providers."""

    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    OTHER = "other"


class ResourceState(str, Enum):
    """Normalized resource lifecycle state."""

    RUNNING = "running"
    STOPPED = "stopped"
    UNATTACHED = "unattached"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Recommendation severity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Resource(BaseModel):
    """A single cloud resource, normalized to a common shape."""

    id: str
    provider: str
    account_id: str
    region: str
    resource_type: ResourceType
    instance_size: str | None = None
    state: ResourceState
    tags: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    hourly_cost: float = 0.0
    project: str | None = None
    attached: bool | None = None
    """For storage resources: whether the volume is attached to a compute
    instance. None for resource types where attachment does not apply."""
    attached_to: str | None = None
    """Resource id of the compute instance this storage volume is attached
    to, if any."""

    @property
    def monthly_cost(self) -> float:
        """Approximate monthly cost assuming 730 hours/month."""
        return self.hourly_cost * 730


class CostRecord(BaseModel):
    """A single day's cost for a resource/service."""

    provider: str
    account_id: str
    resource_id: str | None = None
    service: str
    project: str | None = None
    date: date
    amount: float
    currency: str = "USD"


class UtilizationStats(BaseModel):
    """Aggregated utilization for a resource over a period."""

    resource_id: str
    avg_cpu: float
    max_cpu: float
    period_days: int


class Recommendation(BaseModel):
    """A single optimization recommendation produced by a rule."""

    id: str
    resource_id: str
    provider: str
    rule_id: str
    severity: Severity
    title: str
    description: str
    current_monthly_cost: float
    estimated_monthly_saving: float
    suggested_action: str
    created_at: datetime


class Budget(BaseModel):
    """A monthly spending limit for a project."""

    project: str
    monthly_limit: float
    alert_thresholds: list[int] = Field(default_factory=lambda: [50, 80, 100])


class BudgetAlert(BaseModel):
    """An alert raised when a project's spend crosses a threshold."""

    project: str
    month: str
    """Month in YYYY-MM format."""
    spent: float
    limit: float
    percent_used: float
    threshold_crossed: int
    created_at: datetime
