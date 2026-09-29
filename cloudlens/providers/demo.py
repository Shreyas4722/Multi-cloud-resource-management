"""Demo provider adapter: generates realistic, deterministic sample data.

Lets the whole pipeline (sync -> analyze -> dashboard) run end to end with no
cloud credentials. Covers all three providers, all three resource types, 90
days of daily cost history, and a deliberate mix of healthy and wasteful
resources so every rule in `cloudlens/rules/` finds something.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

from cloudlens.config import DemoProviderConfig
from cloudlens.models import (
    CostRecord,
    Resource,
    ResourceState,
    ResourceType,
    UtilizationStats,
)
from cloudlens.pricing import load_pricing
from cloudlens.providers.base import ProviderAdapter
from cloudlens.registry import register_provider

PROVIDERS = ["aws", "azure", "gcp"]

REGIONS = {
    "aws": ["us-east-1", "us-west-2", "eu-west-1"],
    "azure": ["eastus", "westeurope", "southeastasia"],
    "gcp": ["us-central1", "europe-west1", "asia-east1"],
}

ACCOUNT_IDS = {
    "aws": "123456789012",
    "azure": "azure-sub-demo-0001",
    "gcp": "gcp-project-demo",
}

STORAGE_SIZE_KEY = {
    "aws": "gp3",
    "azure": "Premium_LRS",
    "gcp": "pd-ssd",
}

SERVICE_NAME = {
    "aws": {"compute": "EC2", "storage": "EBS", "database": "RDS"},
    "azure": {"compute": "Virtual Machines", "storage": "Managed Disks", "database": "SQL Database"},
    "gcp": {"compute": "Compute Engine", "storage": "Persistent Disk", "database": "Cloud SQL"},
}

PROJECTS = ["web-app", "data-platform", "internal-tools"]
# Daily cost multiplier per project: internal-tools is deliberately made to
# run over its (smaller) demo budget so the budget engine has something to
# flag, regardless of which day of the month the demo is run on.
PROJECT_DAILY_COST_FACTOR = {"web-app": 1.0, "data-platform": 1.0, "internal-tools": 6.0}

REQUIRED_TAG_KEYS = ["project", "owner", "environment"]
OWNERS = ["alice", "bob", "priya", "diego", "mei"]

HISTORY_DAYS = 90


@register_provider("demo")
class DemoAdapter(ProviderAdapter):
    """Generates realistic sample resources, costs and utilization in memory."""

    def __init__(self, config: DemoProviderConfig | None = None):
        self.config = config or DemoProviderConfig()
        self._rng = random.Random(self.config.seed)
        self._pricing = load_pricing()
        self._resources: list[Resource] = []
        self._costs: list[CostRecord] = []
        self._utilization: dict[str, UtilizationStats] = {}
        self._generate(self.config.resource_count)

    def name(self) -> str:
        return "demo"

    def fetch_resources(self) -> list[Resource]:
        return list(self._resources)

    def fetch_costs(self, start_date: date, end_date: date) -> list[CostRecord]:
        return [c for c in self._costs if start_date <= c.date <= end_date]

    def fetch_utilization(self, resource_id: str, days: int) -> UtilizationStats | None:
        return self._utilization.get(resource_id)

    # -- generation ----------------------------------------------------

    def _next_id(self) -> str:
        """Deterministic id fragment drawn from the seeded RNG, so the same
        seed always reproduces the same resource ids (and therefore the same
        utilization lookups) across separate process invocations."""
        return f"{self._rng.getrandbits(40):010x}"

    def _generate(self, resource_count: int) -> None:
        compute_share, storage_share = 0.45, 0.35
        n_compute = max(3 * len(PROVIDERS), round(resource_count * compute_share))
        n_storage = max(3 * len(PROVIDERS), round(resource_count * storage_share))
        n_database = max(resource_count - n_compute - n_storage, len(PROVIDERS))

        compute_resources = self._generate_compute(n_compute)
        storage_resources = self._generate_storage(n_storage, compute_resources)
        database_resources = self._generate_database(n_database)

        self._resources = compute_resources + storage_resources + database_resources
        self._generate_costs()

    def _tags(self, force_missing: bool) -> dict[str, str]:
        tags = {
            "project": self._rng.choice(PROJECTS),
            "owner": self._rng.choice(OWNERS),
            "environment": self._rng.choice(["production", "staging", "development"]),
        }
        if force_missing:
            del tags[self._rng.choice(REQUIRED_TAG_KEYS)]
        return tags

    def _created_at(self) -> datetime:
        days_ago = self._rng.randint(30, 500)
        return datetime.now(timezone.utc) - timedelta(days=days_ago)

    def _generate_compute(self, n: int) -> list[Resource]:
        resources: list[Resource] = []
        for i in range(n):
            provider = PROVIDERS[i % len(PROVIDERS)]
            sizes = list(self._pricing[provider]["compute"].keys())
            # Bias toward larger sizes for the first third (candidates for
            # idle/oversized findings), smaller/healthy sizes afterward.
            size = self._rng.choice(sizes[: len(sizes) // 2] if i % 3 != 2 else sizes[len(sizes) // 2 :])
            hourly = self._pricing[provider]["compute"][size]["hourly"]

            is_stopped = i % 9 == 0  # ~11% stopped
            state = ResourceState.STOPPED if is_stopped else ResourceState.RUNNING

            tags = self._tags(force_missing=(i % 7 == 0))
            resource = Resource(
                id=f"{provider}-vm-{self._next_id()}",
                provider=provider,
                account_id=ACCOUNT_IDS[provider],
                region=self._rng.choice(REGIONS[provider]),
                resource_type=ResourceType.COMPUTE,
                instance_size=size,
                state=state,
                tags=tags,
                created_at=self._created_at(),
                hourly_cost=hourly,
                project=tags.get("project"),
            )
            resources.append(resource)

            if not is_stopped:
                profile = i % 5
                if profile == 0:
                    # idle: triggers IdleComputeRule
                    avg_cpu, max_cpu = self._rng.uniform(0.5, 4.0), self._rng.uniform(2.0, 8.0)
                elif profile == 1:
                    # oversized: triggers OversizedInstanceRule
                    avg_cpu, max_cpu = self._rng.uniform(6.0, 18.0), self._rng.uniform(20.0, 38.0)
                else:
                    # healthy
                    avg_cpu, max_cpu = self._rng.uniform(25.0, 65.0), self._rng.uniform(50.0, 95.0)
                self._utilization[resource.id] = UtilizationStats(
                    resource_id=resource.id, avg_cpu=avg_cpu, max_cpu=max_cpu, period_days=7
                )
        return resources

    def _generate_storage(self, n: int, compute_resources: list[Resource]) -> list[Resource]:
        resources: list[Resource] = []
        by_provider: dict[str, list[Resource]] = {p: [] for p in PROVIDERS}
        for c in compute_resources:
            by_provider[c.provider].append(c)

        stopped_by_provider = {
            p: [c for c in cs if c.state == ResourceState.STOPPED] for p, cs in by_provider.items()
        }
        running_by_provider = {
            p: [c for c in cs if c.state == ResourceState.RUNNING] for p, cs in by_provider.items()
        }

        for i in range(n):
            provider = PROVIDERS[i % len(PROVIDERS)]
            size_key = STORAGE_SIZE_KEY[provider]
            price_per_gb = self._pricing[provider]["storage"][size_key]["hourly_per_gb"]
            size_gb = self._rng.choice([50, 100, 250, 500, 1000])
            hourly = price_per_gb * size_gb

            unattached = i % 5 == 0  # ~20%: triggers UnattachedStorageRule
            attach_to_stopped = (
                not unattached and i % 5 == 1 and stopped_by_provider.get(provider)
            )  # triggers StoppedInstanceWithStorageRule

            attached_to = None
            if unattached:
                state = ResourceState.UNATTACHED
                attached = False
            elif attach_to_stopped:
                attached_to = self._rng.choice(stopped_by_provider[provider]).id
                state = ResourceState.STOPPED
                attached = True
            elif running_by_provider.get(provider):
                attached_to = self._rng.choice(running_by_provider[provider]).id
                state = ResourceState.RUNNING
                attached = True
            else:
                state = ResourceState.UNATTACHED
                attached = False

            tags = self._tags(force_missing=(i % 7 == 0))
            resources.append(
                Resource(
                    id=f"{provider}-vol-{self._next_id()}",
                    provider=provider,
                    account_id=ACCOUNT_IDS[provider],
                    region=self._rng.choice(REGIONS[provider]),
                    resource_type=ResourceType.STORAGE,
                    instance_size=f"{size_gb}GB {size_key}",
                    state=state,
                    tags=tags,
                    created_at=self._created_at(),
                    hourly_cost=hourly,
                    project=tags.get("project"),
                    attached=attached,
                    attached_to=attached_to,
                )
            )
        return resources

    def _generate_database(self, n: int) -> list[Resource]:
        resources: list[Resource] = []
        db_hourly_by_provider = {
            "aws": 0.145,   # db.m5.large equivalent
            "azure": 0.170,
            "gcp": 0.160,
        }
        for i in range(n):
            provider = PROVIDERS[i % len(PROVIDERS)]
            tags = self._tags(force_missing=(i % 7 == 0))
            resources.append(
                Resource(
                    id=f"{provider}-db-{self._next_id()}",
                    provider=provider,
                    account_id=ACCOUNT_IDS[provider],
                    region=self._rng.choice(REGIONS[provider]),
                    resource_type=ResourceType.DATABASE,
                    instance_size="db.medium",
                    state=ResourceState.RUNNING,
                    tags=tags,
                    created_at=self._created_at(),
                    hourly_cost=db_hourly_by_provider[provider],
                    project=tags.get("project"),
                )
            )
        return resources

    def _generate_costs(self) -> None:
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=HISTORY_DAYS - 1)
        service_by_type = {
            ResourceType.COMPUTE: "compute",
            ResourceType.STORAGE: "storage",
            ResourceType.DATABASE: "database",
        }
        for resource in self._resources:
            if resource.state == ResourceState.STOPPED:
                # Stopped compute stops accruing compute charges, but its
                # attached storage (if any) keeps billing -- handled by the
                # storage resource's own cost records.
                daily_base = 0.0 if resource.resource_type == ResourceType.COMPUTE else resource.hourly_cost * 24
            else:
                daily_base = resource.hourly_cost * 24

            project = resource.project or self._rng.choice(PROJECTS)
            factor = PROJECT_DAILY_COST_FACTOR.get(project, 1.0)
            service = SERVICE_NAME[resource.provider][service_by_type[resource.resource_type]]

            day = start
            while day <= today:
                noise = self._rng.uniform(0.85, 1.15)
                amount = round(daily_base * factor * noise, 4)
                if amount > 0:
                    self._costs.append(
                        CostRecord(
                            provider=resource.provider,
                            account_id=resource.account_id,
                            resource_id=resource.id,
                            service=service,
                            project=project,
                            date=day,
                            amount=amount,
                            currency="USD",
                        )
                    )
                day += timedelta(days=1)
