"""Abstract base class every optimization rule must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from cloudlens.models import Recommendation, Resource, UtilizationStats


class OptimizationRule(ABC):
    """Standard interface for a single optimization check.

    A rule inspects one resource (plus its utilization stats and a shared
    context dict) and either returns a `Recommendation` or `None` if the
    resource does not trigger the rule. Rules must not mutate cloud state.
    """

    rule_id: str
    description: str

    @abstractmethod
    def evaluate(
        self,
        resource: Resource,
        utilization: UtilizationStats | None,
        context: dict[str, Any],
    ) -> Recommendation | None:
        """Evaluate this rule against a single resource.

        `context` carries shared, precomputed data the rule may need, such as
        rule thresholds from config, the pricing table, and sibling resources
        (e.g. so a storage rule can check which compute instances exist).
        """
