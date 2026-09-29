"""Flags running compute resources that are larger than their load requires."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cloudlens.models import Recommendation, Resource, ResourceState, ResourceType, Severity, UtilizationStats
from cloudlens.registry import register_rule
from cloudlens.rules.base import OptimizationRule


@register_rule
class OversizedInstanceRule(OptimizationRule):
    rule_id = "oversized_instance"
    description = "Running compute resource with low average and max CPU relative to its size."

    def evaluate(
        self, resource: Resource, utilization: UtilizationStats | None, context: dict[str, Any]
    ) -> Recommendation | None:
        if resource.resource_type != ResourceType.COMPUTE or resource.state != ResourceState.RUNNING:
            return None
        if utilization is None or not resource.instance_size:
            return None

        params = context["config"].rule_config(self.rule_id).params
        avg_threshold = params.get("avg_cpu_threshold_percent", 20)
        max_threshold = params.get("max_cpu_threshold_percent", 40)

        if utilization.avg_cpu >= avg_threshold or utilization.max_cpu >= max_threshold:
            return None

        compute_prices = context["pricing"].get(resource.provider, {}).get("compute", {})
        current = compute_prices.get(resource.instance_size)
        if not current or not current.get("next_smaller"):
            return None

        next_size = current["next_smaller"]
        next_hourly = compute_prices[next_size]["hourly"]
        saving = (resource.hourly_cost - next_hourly) * 730
        if saving <= 0:
            return None

        return Recommendation(
            id=f"{self.rule_id}:{resource.id}",
            resource_id=resource.id,
            provider=resource.provider,
            rule_id=self.rule_id,
            severity=Severity.MEDIUM,
            title=f"Oversized instance ({resource.instance_size})",
            description=(
                f"Average CPU {utilization.avg_cpu:.1f}% and max CPU {utilization.max_cpu:.1f}% "
                f"are both well below what {resource.instance_size} provides."
            ),
            current_monthly_cost=resource.monthly_cost,
            estimated_monthly_saving=round(saving, 2),
            suggested_action=f"Resize to {next_size}, the next smaller size in the same family.",
            created_at=datetime.now(timezone.utc),
        )
