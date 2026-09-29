"""Normalization tables and helpers.

Every provider names resource types and states differently -- AWS's "EC2" is
Azure's "Virtual Machines" is GCP's "Compute Engine". This module holds the
single, editable mapping table that converts provider-native strings into the
common `ResourceType` / `ResourceState` enums used everywhere downstream.

Provider adapters call these helpers while building `Resource` objects; the
mapping table itself never needs to change for adapters to keep working, and
adding a new provider only means adding one more entry to each table.
"""

from __future__ import annotations

from cloudlens.models import ResourceState, ResourceType

# provider -> (native type string, lowercased) -> common ResourceType
RESOURCE_TYPE_MAP: dict[str, dict[str, ResourceType]] = {
    "aws": {
        "ec2": ResourceType.COMPUTE,
        "ec2 instance": ResourceType.COMPUTE,
        "ebs": ResourceType.STORAGE,
        "ebs volume": ResourceType.STORAGE,
        "rds": ResourceType.DATABASE,
        "rds instance": ResourceType.DATABASE,
    },
    "azure": {
        "virtual machines": ResourceType.COMPUTE,
        "virtual machine": ResourceType.COMPUTE,
        "managed disks": ResourceType.STORAGE,
        "managed disk": ResourceType.STORAGE,
        "sql database": ResourceType.DATABASE,
        "azure database": ResourceType.DATABASE,
    },
    "gcp": {
        "compute engine": ResourceType.COMPUTE,
        "compute instance": ResourceType.COMPUTE,
        "persistent disk": ResourceType.STORAGE,
        "cloud storage": ResourceType.STORAGE,
        "cloud sql": ResourceType.DATABASE,
        "cloud spanner": ResourceType.DATABASE,
    },
}

# provider -> (native state string, lowercased) -> common ResourceState
RESOURCE_STATE_MAP: dict[str, dict[str, ResourceState]] = {
    "aws": {
        "running": ResourceState.RUNNING,
        "stopped": ResourceState.STOPPED,
        "available": ResourceState.UNATTACHED,
        "in-use": ResourceState.RUNNING,
    },
    "azure": {
        "vm running": ResourceState.RUNNING,
        "vm deallocated": ResourceState.STOPPED,
        "vm stopped": ResourceState.STOPPED,
        "unattached": ResourceState.UNATTACHED,
    },
    "gcp": {
        "running": ResourceState.RUNNING,
        "terminated": ResourceState.STOPPED,
        "stopped": ResourceState.STOPPED,
        "unattached": ResourceState.UNATTACHED,
    },
}


def normalize_resource_type(provider: str, native_type: str) -> ResourceType:
    """Map a provider-native resource type string to the common `ResourceType`."""
    return RESOURCE_TYPE_MAP.get(provider, {}).get(native_type.strip().lower(), ResourceType.OTHER)


def normalize_state(provider: str, native_state: str) -> ResourceState:
    """Map a provider-native state string to the common `ResourceState`."""
    return RESOURCE_STATE_MAP.get(provider, {}).get(native_state.strip().lower(), ResourceState.UNKNOWN)
