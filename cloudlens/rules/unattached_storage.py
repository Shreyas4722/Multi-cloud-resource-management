"""Flags storage volumes that are not attached to any compute instance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cloudlens.models import Recommendation, Resource, ResourceType, Severity, UtilizationStats
from cloudlens.registry import register_rule
from cloudlens.rules.base import OptimizationRule


@register_rule
class UnattachedStorageRule(OptimizationRule):
    rule_id = "unattached_storage"
    description = "Storage volume not attached to any compute instance."

    def evaluate(
        self, resource: Resource, utilization: UtilizationStats | None, context: dict[str, Any]
    ) -> Recommendation | None:
        if resource.resource_type != ResourceType.STORAGE:
            return None
        if resource.attached is not False:
            return None

        return Recommendation(
            id=f"{self.rule_id}:{resource.id}",
            resource_id=resource.id,
            provider=resource.provider,
            rule_id=self.rule_id,
            severity=Severity.HIGH,
            title=f"Unattached storage volume ({resource.instance_size})",
            description="This volume is not attached to any compute instance but is still being billed.",
            current_monthly_cost=resource.monthly_cost,
            estimated_monthly_saving=resource.monthly_cost,
            suggested_action="Snapshot and delete this unattached volume.",
            created_at=datetime.now(timezone.utc),
        )
