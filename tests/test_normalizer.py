"""Normalizer mapping tests for each provider."""

from __future__ import annotations

from cloudlens.models import ResourceState, ResourceType
from cloudlens.normalizer import normalize_resource_type, normalize_state


def test_aws_resource_type_mapping():
    assert normalize_resource_type("aws", "EC2") == ResourceType.COMPUTE
    assert normalize_resource_type("aws", "EBS") == ResourceType.STORAGE
    assert normalize_resource_type("aws", "RDS") == ResourceType.DATABASE


def test_azure_resource_type_mapping():
    assert normalize_resource_type("azure", "Virtual Machines") == ResourceType.COMPUTE
    assert normalize_resource_type("azure", "Managed Disks") == ResourceType.STORAGE
    assert normalize_resource_type("azure", "SQL Database") == ResourceType.DATABASE


def test_gcp_resource_type_mapping():
    assert normalize_resource_type("gcp", "Compute Engine") == ResourceType.COMPUTE
    assert normalize_resource_type("gcp", "Persistent Disk") == ResourceType.STORAGE
    assert normalize_resource_type("gcp", "Cloud SQL") == ResourceType.DATABASE


def test_unmapped_type_falls_back_to_other():
    assert normalize_resource_type("aws", "Lambda") == ResourceType.OTHER
    assert normalize_resource_type("unknown-provider", "anything") == ResourceType.OTHER


def test_resource_type_mapping_is_case_insensitive():
    assert normalize_resource_type("aws", "ec2") == ResourceType.COMPUTE
    assert normalize_resource_type("azure", "VIRTUAL MACHINES") == ResourceType.COMPUTE


def test_state_mapping_per_provider():
    assert normalize_state("aws", "running") == ResourceState.RUNNING
    assert normalize_state("aws", "available") == ResourceState.UNATTACHED
    assert normalize_state("azure", "VM deallocated") == ResourceState.STOPPED
    assert normalize_state("gcp", "terminated") == ResourceState.STOPPED


def test_unmapped_state_falls_back_to_unknown():
    assert normalize_state("aws", "some-new-state") == ResourceState.UNKNOWN
