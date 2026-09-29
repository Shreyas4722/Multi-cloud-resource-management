"""Flags stopped instances whose attached volumes are still being billed."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cloudlens.models import Recommendation, Resource, ResourceState, ResourceType, Severity, UtilizationStats
from cloudlens.registry import register_rule
from cloudlens.rules.base import OptimizationRule


@register_rule
class StoppedInstanceWithStorageRule(OptimizationRule):
    rule_id = "stopped_with_storage"
    description = "Stopped instance whose attached volumes are still being billed."

    def evaluate(
        self, resource: Resource, utilization: UtilizationStats | None, context: dict[str, Any]
    ) -> Recommendation | None:
        if resource.resource_type != ResourceType.COMPUTE or resource.state != ResourceState.STOPPED:
            return None

        attached_volumes = context["storage_by_attached_to"].get(resource.id, [])
        if not attached_volumes:
            return None

        wasted_monthly_cost = sum(v.monthly_cost for v in attached_volumes)
        if wasted_monthly_cost <= 0:
            return None

        volume_desc = ", ".join(v.instance_size or v.id for v in attached_volumes)
        return Recommendation(
            id=f"{self.rule_id}:{resource.id}",
            resource_id=resource.id,
            provider=resource.provider,
            rule_id=self.rule_id,
            severity=Severity.MEDIUM,
            title=f"Stopped instance with {len(attached_volumes)} billed volume(s)",
            description=(
                f"This instance is stopped, but its attached storage ({volume_desc}) "
                "is still being billed."
            ),
            current_monthly_cost=wasted_monthly_cost,
            estimated_monthly_saving=wasted_monthly_cost,
            suggested_action="Snapshot and release the attached volumes, or restart the instance.",
            created_at=datetime.now(timezone.utc),
        )
