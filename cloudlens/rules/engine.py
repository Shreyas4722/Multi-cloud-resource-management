"""Runs every registered, enabled rule against every resource.

This is the only place that iterates `RULE_REGISTRY` -- core.py calls into
here, never into individual rule modules. Adding a new rule file with
`@register_rule` makes it show up here automatically.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from cloudlens.config import CloudLensConfig
from cloudlens.models import Recommendation, Resource, UtilizationStats
from cloudlens.pricing import load_pricing
from cloudlens.registry import RULE_REGISTRY

import cloudlens.rules as _rules_package

_EXCLUDED_MODULES = {"base", "engine"}


def _discover_rules() -> None:
    """Import every module under `cloudlens/rules/` so its `@register_rule`
    decorator(s) run. Dropping a new rule file into this package is enough
    for it to register -- no import needs to be added here."""
    for module_info in pkgutil.iter_modules(_rules_package.__path__):
        if module_info.name in _EXCLUDED_MODULES:
            continue
        importlib.import_module(f"{_rules_package.__name__}.{module_info.name}")


_discover_rules()


def run_rules(
    resources: list[Resource],
    utilization_by_resource: dict[str, UtilizationStats],
    config: CloudLensConfig,
) -> list[Recommendation]:
    """Evaluate every enabled rule against every resource and return the
    resulting recommendations."""
    storage_by_attached_to: dict[str, list[Resource]] = {}
    for r in resources:
        if r.attached_to:
            storage_by_attached_to.setdefault(r.attached_to, []).append(r)

    context: dict[str, Any] = {
        "config": config,
        "pricing": load_pricing(),
        "resources_by_id": {r.id: r for r in resources},
        "storage_by_attached_to": storage_by_attached_to,
    }

    recommendations: list[Recommendation] = []
    for rule_id, rule_cls in sorted(RULE_REGISTRY.items()):
        if not config.rule_config(rule_id).enabled:
            continue
        rule = rule_cls()
        for resource in resources:
            rec = rule.evaluate(resource, utilization_by_resource.get(resource.id), context)
            if rec is not None:
                recommendations.append(rec)
    return recommendations
