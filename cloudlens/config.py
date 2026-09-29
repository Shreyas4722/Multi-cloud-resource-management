"""Configuration models and loader for `config.yaml`.

Everything that varies between environments -- which providers are enabled,
where their data comes from, rule thresholds, budgets, and so on -- lives in
one YAML file and is validated into these Pydantic models.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ColumnMapping(BaseModel):
    """Maps a provider's CSV export column names to cloudlens's internal fields."""

    cost: dict[str, str] = Field(default_factory=dict)
    """Keys: date, amount, service, resource_id, project, currency."""
    inventory: dict[str, str] = Field(default_factory=dict)
    """Keys: id, type, region, state, size, tags, created_at, account_id."""


class AWSProviderConfig(BaseModel):
    enabled: bool = False
    regions: list[str] = Field(default_factory=lambda: ["us-east-1"])
    cost_source: str = "csv"
    """Either "csv" (AWS Cost and Usage Report) or "cost_explorer"."""
    cur_csv_path: str | None = None
    account_id: str = "unknown"


class CSVProviderConfig(BaseModel):
    """Shared shape for Azure and GCP, which are both CSV-driven."""

    enabled: bool = False
    cost_csv_path: str | None = None
    inventory_csv_path: str | None = None
    account_id: str = "unknown"
    column_mapping: ColumnMapping = Field(default_factory=ColumnMapping)


class DemoProviderConfig(BaseModel):
    enabled: bool = True
    seed: int = 42
    resource_count: int = 72


class ProvidersConfig(BaseModel):
    aws: AWSProviderConfig = Field(default_factory=AWSProviderConfig)
    azure: CSVProviderConfig = Field(default_factory=CSVProviderConfig)
    gcp: CSVProviderConfig = Field(default_factory=CSVProviderConfig)
    demo: DemoProviderConfig = Field(default_factory=DemoProviderConfig)


class RuleConfig(BaseModel):
    """Generic per-rule settings: whether it's enabled, plus any thresholds."""

    enabled: bool = True
    params: dict[str, float] = Field(default_factory=dict)


class DatabaseConfig(BaseModel):
    path: str = "cloudlens.db"


class BudgetConfig(BaseModel):
    project: str
    monthly_limit: float
    alert_thresholds: list[int] = Field(default_factory=lambda: [50, 80, 100])


class CloudLensConfig(BaseModel):
    """Top-level configuration, loaded from `config.yaml`."""

    demo_mode: bool = True
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    rules: dict[str, RuleConfig] = Field(default_factory=dict)
    required_tags: list[str] = Field(default_factory=lambda: ["project", "owner", "environment"])
    budgets: list[BudgetConfig] = Field(default_factory=list)
    webhook_url: str | None = None

    def rule_config(self, rule_id: str) -> RuleConfig:
        """Return the config for a rule, or defaults (enabled, no params) if unset."""
        return self.rules.get(rule_id, RuleConfig())


def load_config(config_path: str | Path) -> CloudLensConfig:
    """Load and validate `config.yaml` from `config_path`."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. Run `cloudlens init` to create one "
            f"from config.example.yaml."
        )
    with path.open() as f:
        raw = yaml.safe_load(f) or {}
    return CloudLensConfig.model_validate(raw)
