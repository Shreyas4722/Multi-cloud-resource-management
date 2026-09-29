"""Flags resources missing one or more required tags."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cloudlens.models import Recommendation, Resource, Severity, UtilizationStats
from cloudlens.registry import register_rule
from cloudlens.rules.base import OptimizationRule


@register_rule
class UntaggedResourceRule(OptimizationRule):
    rule_id = "untagged_resource"
    description = "Resource missing one or more required tags."

    def evaluate(
        self, resource: Resource, utilization: UtilizationStats | None, context: dict[str, Any]
    ) -> Recommendation | None:
        required_tags = context["config"].required_tags
        missing = [tag for tag in required_tags if tag not in resource.tags]
        if not missing:
            return None

        return Recommendation(
            id=f"{self.rule_id}:{resource.id}",
            resource_id=resource.id,
            provider=resource.provider,
            rule_id=self.rule_id,
            severity=Severity.MEDIUM,
            title=f"Missing required tags: {', '.join(missing)}",
            description=(
                "This resource cannot be allocated to a project budget until it carries "
                f"all required tags: {', '.join(required_tags)}."
            ),
            current_monthly_cost=resource.monthly_cost,
            estimated_monthly_saving=0.0,
            suggested_action=f"Add missing tags: {', '.join(missing)}.",
            created_at=datetime.now(timezone.utc),
        )
