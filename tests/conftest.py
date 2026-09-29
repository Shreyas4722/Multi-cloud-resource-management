"""Shared test fixtures and factory helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from cloudlens.config import CloudLensConfig, RuleConfig
from cloudlens.models import Resource, ResourceState, ResourceType
from cloudlens.pricing import load_pricing


def make_resource(**overrides) -> Resource:
    defaults = dict(
        id="test-resource-1",
        provider="aws",
        account_id="123456789012",
        region="us-east-1",
        resource_type=ResourceType.COMPUTE,
        instance_size="t3.large",
        state=ResourceState.RUNNING,
        tags={"project": "web-app", "owner": "alice", "environment": "production"},
        created_at=datetime.now(timezone.utc),
        hourly_cost=0.0832,
        project="web-app",
    )
    defaults.update(overrides)
    return Resource(**defaults)


def make_config() -> CloudLensConfig:
    return CloudLensConfig(
        demo_mode=False,
        required_tags=["project", "owner", "environment"],
        rules={
            "idle_compute": RuleConfig(enabled=True, params={"avg_cpu_threshold_percent": 5, "period_days": 7}),
            "unattached_storage": RuleConfig(enabled=True, params={}),
            "oversized_instance": RuleConfig(
                enabled=True, params={"avg_cpu_threshold_percent": 20, "max_cpu_threshold_percent": 40}
            ),
            "untagged_resource": RuleConfig(enabled=True, params={}),
            "stopped_with_storage": RuleConfig(enabled=True, params={}),
        },
    )


def make_context(config: CloudLensConfig | None = None, resources: list[Resource] | None = None) -> dict:
    resources = resources or []
    storage_by_attached_to: dict[str, list[Resource]] = {}
    for r in resources:
        if r.attached_to:
            storage_by_attached_to.setdefault(r.attached_to, []).append(r)
    return {
        "config": config or make_config(),
        "pricing": load_pricing(),
        "resources_by_id": {r.id: r for r in resources},
        "storage_by_attached_to": storage_by_attached_to,
    }
