"""The `CloudLens` public API: the single entry point every consumer uses.

The CLI and the Streamlit dashboard both talk to the framework exclusively
through this class. It wires together provider adapters (via the registry),
the normalizer, storage, the rules engine and the budget engine, and never
imports a concrete provider or rule class directly.
"""

from __future__ import annotations

import importlib
import pkgutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import cloudlens.providers as _providers_package
from cloudlens.budget.engine import BudgetStatus, compute_budget_status
from cloudlens.budget.notifiers import ConsoleNotifier, Notifier, WebhookNotifier
from cloudlens.config import CloudLensConfig, load_config
from cloudlens.models import Recommendation, Resource, ResourceType, Severity
from cloudlens.providers.base import ProviderAdapter
from cloudlens.registry import get_provider, list_providers
from cloudlens.rules.engine import run_rules
from cloudlens.storage import repository as repo
from cloudlens.storage.database import make_engine, make_session_factory, session_scope

HISTORY_DAYS = 90


def _discover_providers() -> None:
    """Import every module under `cloudlens/providers/` so its
    `@register_provider` decorator runs. Dropping a new adapter file into
    this package is enough for it to register -- no import needs to be added
    here (mirrors `cloudlens.rules.engine._discover_rules`)."""
    for module_info in pkgutil.iter_modules(_providers_package.__path__):
        if module_info.name == "base":
            continue
        importlib.import_module(f"{_providers_package.__name__}.{module_info.name}")


_discover_providers()


class CloudLens:
    """The framework's single public entry point.

    ```python
    from cloudlens import CloudLens

    cl = CloudLens(config_path="config.yaml")
    cl.sync()
    cl.analyze()
    cl.get_recommendations()
    ```
    """

    def __init__(self, config_path: str | Path = "config.yaml"):
        self.config_path = config_path
        self.config: CloudLensConfig = load_config(config_path)
        self._engine = make_engine(self.config.database.path)
        self._session_factory = make_session_factory(self._engine)

    def reload_config(self) -> None:
        """Re-read `config.yaml` from disk (used after Settings-page edits)."""
        self.config = load_config(self.config_path)

    # -- provider wiring --------------------------------------------------

    def _enabled_adapters(self) -> list[ProviderAdapter]:
        """Instantiate one adapter per enabled provider, via the registry only.

        When `demo_mode` is on, only the demo provider is used regardless of
        the other providers' `enabled` flags, so the whole pipeline is
        guaranteed to run without any real credentials or CSV files.
        """
        names = ["demo"] if self.config.demo_mode else list_providers()
        adapters: list[ProviderAdapter] = []
        for name in names:
            provider_cfg = getattr(self.config.providers, name, None)
            if provider_cfg is None or not getattr(provider_cfg, "enabled", False):
                continue
            adapter_cls = get_provider(name)
            adapters.append(adapter_cls(provider_cfg))
        return adapters

    # -- public API ---------------------------------------------------------

    def sync(self) -> dict[str, int]:
        """Fetch resources and costs from every enabled provider and store them.

        Returns a small summary dict of counts per provider, useful for the
        CLI and the dashboard's "last sync" feedback.
        """
        adapters = self._enabled_adapters()
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=HISTORY_DAYS - 1)

        summary: dict[str, int] = {}
        with session_scope(self._session_factory) as session:
            for adapter in adapters:
                resources = adapter.fetch_resources()
                costs = adapter.fetch_costs(start, end)
                repo.upsert_resources(session, resources)
                repo.upsert_costs(session, costs)
                summary[adapter.name()] = len(resources)
        return summary

    def analyze(self) -> list[Recommendation]:
        """Run every enabled rule against stored resources and recompute budgets.

        Recommendations are persisted (replacing the previous set). Budget
        alerts are persisted incrementally and newly-crossed thresholds are
        sent to the configured notifiers.
        """
        idle_period_days = int(self.config.rule_config("idle_compute").params.get("period_days", 7))

        # Map each resource id to the adapter that produced it. A single
        # adapter can simulate/cover multiple `Resource.provider` values (the
        # demo adapter is registered as "demo" but produces aws/azure/gcp
        # resources), so this can't be a simple provider-name lookup.
        owner_adapter_by_id: dict[str, ProviderAdapter] = {}
        for adapter in self._enabled_adapters():
            for resource in adapter.fetch_resources():
                owner_adapter_by_id[resource.id] = adapter

        with session_scope(self._session_factory) as session:
            resources = repo.list_resources(session)

        utilization_by_resource = {}
        for resource in resources:
            if resource.resource_type != ResourceType.COMPUTE:
                continue
            adapter = owner_adapter_by_id.get(resource.id)
            if adapter is None:
                continue
            stats = adapter.fetch_utilization(resource.id, idle_period_days)
            if stats is not None:
                utilization_by_resource[resource.id] = stats

        recommendations = run_rules(resources, utilization_by_resource, self.config)

        with session_scope(self._session_factory) as session:
            repo.replace_recommendations(session, recommendations)
            all_costs = repo.list_costs(session)
            existing_alert_keys = {
                (a.project, a.month, a.threshold_crossed) for a in repo.list_budget_alerts(session)
            }
            statuses = compute_budget_status(self.config.budgets, all_costs)
            new_alerts = [
                alert
                for status in statuses
                for alert in status.alerts
                if (alert.project, alert.month, alert.threshold_crossed) not in existing_alert_keys
            ]
            repo.upsert_alerts(session, [alert for status in statuses for alert in status.alerts])

        if new_alerts:
            self._notify(new_alerts)

        return recommendations

    def _notifiers(self) -> list[Notifier]:
        notifiers: list[Notifier] = [ConsoleNotifier()]
        if self.config.webhook_url:
            notifiers.append(WebhookNotifier(self.config.webhook_url))
        return notifiers

    def _notify(self, alerts) -> None:
        for notifier in self._notifiers():
            for alert in alerts:
                notifier.notify(alert)

    def get_recommendations(
        self,
        provider: str | None = None,
        min_saving: float = 0.0,
        rule_id: str | None = None,
        severity: Severity | None = None,
    ) -> list[Recommendation]:
        """Return stored recommendations, optionally filtered."""
        with session_scope(self._session_factory) as session:
            return repo.list_recommendations(
                session, provider=provider, min_saving=min_saving, rule_id=rule_id, severity=severity
            )

    def get_resources(
        self, provider: str | None = None, resource_type: ResourceType | None = None
    ) -> list[Resource]:
        """Return stored resources, optionally filtered."""
        with session_scope(self._session_factory) as session:
            return repo.list_resources(session, provider=provider, resource_type=resource_type)

    def get_cost_summary(
        self,
        group_by: str = "provider",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Return total cost grouped by "provider", "service", "project",
        "region" or "date", sorted by total cost descending (or by date
        ascending when grouping by date)."""
        with session_scope(self._session_factory) as session:
            costs = repo.list_costs(session, start_date=start_date, end_date=end_date)
            resources = repo.list_resources(session)

        if not costs:
            return pd.DataFrame(columns=[group_by, "total_cost"])

        costs_df = pd.DataFrame([c.model_dump() for c in costs])

        if group_by == "region":
            region_by_id = {r.id: r.region for r in resources}
            costs_df["region"] = costs_df["resource_id"].map(region_by_id).fillna("unknown")
            key = "region"
        elif group_by == "date":
            key = "date"
        elif group_by in ("provider", "service", "project"):
            key = group_by
            costs_df[key] = costs_df[key].fillna("unassigned")
        else:
            raise ValueError(f"Unsupported group_by: {group_by!r}")

        grouped = costs_df.groupby(key, as_index=False)["amount"].sum().rename(columns={"amount": "total_cost"})
        if group_by == "date":
            grouped = grouped.sort_values("date")
        else:
            grouped = grouped.sort_values("total_cost", ascending=False)
        return grouped.reset_index(drop=True)

    def get_budget_status(self) -> list[BudgetStatus]:
        """Return live budget status (spend, forecast, alerts) per project."""
        with session_scope(self._session_factory) as session:
            costs = repo.list_costs(session)
        return compute_budget_status(self.config.budgets, costs)

    def total_potential_savings(self) -> float:
        """Sum of estimated monthly savings across all stored recommendations."""
        with session_scope(self._session_factory) as session:
            recs = repo.list_recommendations(session)
        return round(sum(r.estimated_monthly_saving for r in recs), 2)
