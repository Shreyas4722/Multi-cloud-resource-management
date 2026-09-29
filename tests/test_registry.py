"""Registries: bundled adapters/rules are discovered, and new ones register correctly."""

from __future__ import annotations

from cloudlens.providers.base import ProviderAdapter
from cloudlens.registry import PROVIDER_REGISTRY, RULE_REGISTRY, get_provider, get_rule, list_providers, list_rules, register_provider, register_rule
from cloudlens.rules.base import OptimizationRule


def test_bundled_providers_are_registered():
    import cloudlens.core  # noqa: F401  (triggers dynamic provider discovery)

    for name in ("aws", "azure", "gcp", "demo"):
        assert name in list_providers()


def test_bundled_rules_are_registered():
    import cloudlens.rules.engine  # noqa: F401  (triggers dynamic rule discovery)

    for rule_id in (
        "idle_compute",
        "unattached_storage",
        "oversized_instance",
        "untagged_resource",
        "stopped_with_storage",
    ):
        assert rule_id in list_rules()


def test_new_provider_registers_via_decorator():
    @register_provider("_test_provider")
    class DummyAdapter(ProviderAdapter):
        def name(self):
            return "_test_provider"

        def fetch_resources(self):
            return []

        def fetch_costs(self, start_date, end_date):
            return []

        def fetch_utilization(self, resource_id, days):
            return None

    try:
        assert get_provider("_test_provider") is DummyAdapter
    finally:
        del PROVIDER_REGISTRY["_test_provider"]


def test_new_rule_registers_via_decorator():
    @register_rule
    class DummyRule(OptimizationRule):
        rule_id = "_test_rule"
        description = "test rule"

        def evaluate(self, resource, utilization, context):
            return None

    try:
        assert get_rule("_test_rule") is DummyRule
    finally:
        del RULE_REGISTRY["_test_rule"]


def test_unknown_provider_lookup_raises():
    import pytest

    with pytest.raises(KeyError):
        get_provider("_does_not_exist")
