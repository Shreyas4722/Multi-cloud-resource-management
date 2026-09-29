"""Provider and rule registries.

Provider adapters and optimization rules register themselves here via
decorators. The core (`cloudlens/core.py`) discovers adapters and rules only
through these registries -- it never imports a concrete adapter or rule class
directly. This is what lets a new provider or rule be added by dropping in a
single file, with no changes to core code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Type

if TYPE_CHECKING:
    from cloudlens.providers.base import ProviderAdapter
    from cloudlens.rules.base import OptimizationRule

PROVIDER_REGISTRY: dict[str, "Type[ProviderAdapter]"] = {}
RULE_REGISTRY: dict[str, "Type[OptimizationRule]"] = {}


def register_provider(name: str) -> Callable[[Type["ProviderAdapter"]], Type["ProviderAdapter"]]:
    """Class decorator that registers a `ProviderAdapter` subclass under `name`."""

    def decorator(cls: Type["ProviderAdapter"]) -> Type["ProviderAdapter"]:
        PROVIDER_REGISTRY[name] = cls
        return cls

    return decorator


def register_rule(cls: Type["OptimizationRule"]) -> Type["OptimizationRule"]:
    """Class decorator that registers an `OptimizationRule` subclass under its `rule_id`."""
    instance = cls()
    RULE_REGISTRY[instance.rule_id] = cls
    return cls


def get_provider(name: str) -> "Type[ProviderAdapter]":
    """Look up a registered provider adapter class by name."""
    try:
        return PROVIDER_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"No provider adapter registered under {name!r}. "
            f"Known providers: {sorted(PROVIDER_REGISTRY)}"
        ) from exc


def list_providers() -> list[str]:
    """List the names of all registered provider adapters."""
    return sorted(PROVIDER_REGISTRY)


def get_rule(rule_id: str) -> "Type[OptimizationRule]":
    """Look up a registered rule class by its rule_id."""
    try:
        return RULE_REGISTRY[rule_id]
    except KeyError as exc:
        raise KeyError(
            f"No rule registered under {rule_id!r}. Known rules: {sorted(RULE_REGISTRY)}"
        ) from exc


def list_rules() -> list[str]:
    """List the rule_ids of all registered rules."""
    return sorted(RULE_REGISTRY)
