"""Flags running compute resources that are essentially idle."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cloudlens.models import Recommendation, Resource, ResourceState, ResourceType, Severity, UtilizationStats
from cloudlens.registry import register_rule
from cloudlens.rules.base import OptimizationRule


@register_rule
class IdleComputeRule(OptimizationRule):
    rule_id = "idle_compute"
    description = "Running compute resource with average CPU below threshold over the trailing period."

    def evaluate(
        self, resource: Resource, utilization: UtilizationStats | None, context: dict[str, Any]
    ) -> Recommendation | None:
        if resource.resource_type != ResourceType.COMPUTE or resource.state != ResourceState.RUNNING:
            return None
        if utilization is None:
            return None

        params = context["config"].rule_config(self.rule_id).params
        cpu_threshold = params.get("avg_cpu_threshold_percent", 5)

        if utilization.avg_cpu >= cpu_threshold:
            return None

        saving = resource.monthly_cost
        return Recommendation(
            id=f"{self.rule_id}:{resource.id}",
            resource_id=resource.id,
            provider=resource.provider,
            rule_id=self.rule_id,
            severity=Severity.HIGH,
            title=f"Idle {resource.resource_type.value} instance ({resource.instance_size})",
            description=(
                f"Average CPU utilization is {utilization.avg_cpu:.1f}% over the last "
                f"{utilization.period_days} days, below the {cpu_threshold}% idle threshold."
            ),
            current_monthly_cost=resource.monthly_cost,
            estimated_monthly_saving=saving,
            suggested_action="Stop or terminate this idle instance.",
            created_at=datetime.now(timezone.utc),
        )
