"""Budget engine: month-to-date spend, threshold alerts, and end-of-month forecast."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from cloudlens.config import BudgetConfig
from cloudlens.models import BudgetAlert, CostRecord


@dataclass
class BudgetStatus:
    """Full picture of a project's budget for the current month."""

    project: str
    month: str
    monthly_limit: float
    spent: float
    percent_used: float
    forecast_month_end: float
    forecast_exceeds_budget: bool
    alerts: list[BudgetAlert] = field(default_factory=list)


def compute_budget_status(
    budgets: list[BudgetConfig],
    costs: list[CostRecord],
    as_of: date | None = None,
) -> list[BudgetStatus]:
    """Compute month-to-date spend, threshold alerts and a linear forecast
    for every configured budget.

    The forecast is a simple linear projection: (spend so far / days elapsed
    this month) * days in month.
    """
    as_of = as_of or datetime.now(timezone.utc).date()
    month_key = f"{as_of.year:04d}-{as_of.month:02d}"
    days_in_month = calendar.monthrange(as_of.year, as_of.month)[1]
    days_elapsed = as_of.day

    statuses: list[BudgetStatus] = []
    for budget in budgets:
        month_costs = [
            c
            for c in costs
            if c.project == budget.project and c.date.year == as_of.year and c.date.month == as_of.month
        ]
        spent = sum(c.amount for c in month_costs)
        percent_used = (spent / budget.monthly_limit * 100) if budget.monthly_limit else 0.0
        forecast = (spent / days_elapsed * days_in_month) if days_elapsed else spent
        forecast_exceeds = forecast > budget.monthly_limit

        alerts = [
            BudgetAlert(
                project=budget.project,
                month=month_key,
                spent=round(spent, 2),
                limit=budget.monthly_limit,
                percent_used=round(percent_used, 2),
                threshold_crossed=threshold,
                created_at=datetime.now(timezone.utc),
            )
            for threshold in sorted(budget.alert_thresholds)
            if percent_used >= threshold
        ]

        statuses.append(
            BudgetStatus(
                project=budget.project,
                month=month_key,
                monthly_limit=budget.monthly_limit,
                spent=round(spent, 2),
                percent_used=round(percent_used, 2),
                forecast_month_end=round(forecast, 2),
                forecast_exceeds_budget=forecast_exceeds,
                alerts=alerts,
            )
        )
    return statuses
