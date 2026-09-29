"""Each rule: one resource that should trigger it, one that should not."""

from __future__ import annotations

from cloudlens.models import ResourceState, ResourceType, UtilizationStats
from cloudlens.rules.idle_compute import IdleComputeRule
from cloudlens.rules.oversized_instance import OversizedInstanceRule
from cloudlens.rules.stopped_with_storage import StoppedInstanceWithStorageRule
from cloudlens.rules.unattached_storage import UnattachedStorageRule
from cloudlens.rules.untagged_resource import UntaggedResourceRule
from tests.conftest import make_context, make_resource


# -- idle_compute ------------------------------------------------------------


def test_idle_compute_triggers_on_low_cpu():
    resource = make_resource(state=ResourceState.RUNNING)
    util = UtilizationStats(resource_id=resource.id, avg_cpu=2.0, max_cpu=6.0, period_days=7)
    rec = IdleComputeRule().evaluate(resource, util, make_context(resources=[resource]))
    assert rec is not None
    assert rec.rule_id == "idle_compute"
    assert rec.estimated_monthly_saving == resource.monthly_cost


def test_idle_compute_does_not_trigger_on_healthy_cpu():
    resource = make_resource(state=ResourceState.RUNNING)
    util = UtilizationStats(resource_id=resource.id, avg_cpu=45.0, max_cpu=80.0, period_days=7)
    assert IdleComputeRule().evaluate(resource, util, make_context(resources=[resource])) is None


# -- unattached_storage --------------------------------------------------


def test_unattached_storage_triggers_when_not_attached():
    resource = make_resource(
        resource_type=ResourceType.STORAGE, state=ResourceState.UNATTACHED, attached=False, instance_size="100GB gp3"
    )
    rec = UnattachedStorageRule().evaluate(resource, None, make_context(resources=[resource]))
    assert rec is not None
    assert rec.estimated_monthly_saving == resource.monthly_cost


def test_unattached_storage_does_not_trigger_when_attached():
    resource = make_resource(
        resource_type=ResourceType.STORAGE, state=ResourceState.RUNNING, attached=True, attached_to="i-123"
    )
    assert UnattachedStorageRule().evaluate(resource, None, make_context(resources=[resource])) is None


# -- oversized_instance --------------------------------------------------


def test_oversized_instance_triggers_on_low_utilization():
    resource = make_resource(instance_size="t3.large")  # has a next_smaller in pricing.json
    util = UtilizationStats(resource_id=resource.id, avg_cpu=10.0, max_cpu=25.0, period_days=7)
    rec = OversizedInstanceRule().evaluate(resource, util, make_context(resources=[resource]))
    assert rec is not None
    assert rec.estimated_monthly_saving > 0
    assert "t3.medium" in rec.suggested_action  # next_smaller for t3.large


def test_oversized_instance_does_not_trigger_on_high_utilization():
    resource = make_resource(instance_size="t3.large")
    util = UtilizationStats(resource_id=resource.id, avg_cpu=55.0, max_cpu=90.0, period_days=7)
    assert OversizedInstanceRule().evaluate(resource, util, make_context(resources=[resource])) is None


# -- untagged_resource --------------------------------------------------


def test_untagged_resource_triggers_when_tag_missing():
    resource = make_resource(tags={"project": "web-app"})
    rec = UntaggedResourceRule().evaluate(resource, None, make_context(resources=[resource]))
    assert rec is not None
    assert rec.estimated_monthly_saving == 0.0


def test_untagged_resource_does_not_trigger_when_fully_tagged():
    resource = make_resource(tags={"project": "web-app", "owner": "alice", "environment": "production"})
    assert UntaggedResourceRule().evaluate(resource, None, make_context(resources=[resource])) is None


# -- stopped_with_storage --------------------------------------------------


def test_stopped_with_storage_triggers_when_volume_attached():
    stopped = make_resource(id="i-stopped", state=ResourceState.STOPPED, resource_type=ResourceType.COMPUTE)
    volume = make_resource(
        id="vol-1",
        resource_type=ResourceType.STORAGE,
        state=ResourceState.STOPPED,
        attached=True,
        attached_to="i-stopped",
        instance_size="100GB gp3",
        hourly_cost=0.011,
    )
    rec = StoppedInstanceWithStorageRule().evaluate(stopped, None, make_context(resources=[stopped, volume]))
    assert rec is not None
    assert rec.estimated_monthly_saving == volume.monthly_cost


def test_stopped_with_storage_does_not_trigger_without_attached_volume():
    stopped = make_resource(id="i-stopped-2", state=ResourceState.STOPPED, resource_type=ResourceType.COMPUTE)
    assert StoppedInstanceWithStorageRule().evaluate(stopped, None, make_context(resources=[stopped])) is None
