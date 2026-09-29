"""End-to-end: sync + analyze in demo mode produces recommendations from every rule."""

from __future__ import annotations

import yaml
import pytest

from cloudlens import CloudLens


@pytest.fixture
def cl(tmp_path):
    config = {
        "demo_mode": True,
        "database": {"path": str(tmp_path / "cloudlens.db")},
        "providers": {"demo": {"enabled": True, "seed": 42, "resource_count": 72}},
        "rules": {
            "idle_compute": {"enabled": True, "params": {"avg_cpu_threshold_percent": 5, "period_days": 7}},
            "unattached_storage": {"enabled": True, "params": {}},
            "oversized_instance": {
                "enabled": True,
                "params": {"avg_cpu_threshold_percent": 20, "max_cpu_threshold_percent": 40},
            },
            "untagged_resource": {"enabled": True, "params": {}},
            "stopped_with_storage": {"enabled": True, "params": {}},
        },
        "required_tags": ["project", "owner", "environment"],
        "budgets": [
            {"project": "web-app", "monthly_limit": 5000, "alert_thresholds": [50, 80, 100]},
            {"project": "internal-tools", "monthly_limit": 1500, "alert_thresholds": [50, 80, 100]},
        ],
        "webhook_url": None,
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    return CloudLens(config_path=str(config_path))


def test_demo_sync_populates_resources(cl):
    summary = cl.sync()
    assert summary["demo"] >= 60


def test_demo_analyze_produces_recommendations_from_every_rule(cl):
    cl.sync()
    recommendations = cl.analyze()

    assert len(recommendations) > 0
    rule_ids = {r.rule_id for r in recommendations}
    assert rule_ids == {
        "idle_compute",
        "unattached_storage",
        "oversized_instance",
        "untagged_resource",
        "stopped_with_storage",
    }
    assert cl.total_potential_savings() > 0


def test_demo_re_sync_does_not_duplicate_resources(cl):
    cl.sync()
    first_count = len(cl.get_resources())
    cl.sync()
    second_count = len(cl.get_resources())
    assert first_count == second_count


def test_demo_budget_status_flags_overrun_project(cl):
    cl.sync()
    cl.analyze()
    statuses = {s.project: s for s in cl.get_budget_status()}
    assert statuses["internal-tools"].forecast_exceeds_budget is True
