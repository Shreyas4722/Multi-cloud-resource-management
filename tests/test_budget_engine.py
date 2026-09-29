"""Budget engine: threshold-crossing and linear-forecast logic."""

from __future__ import annotations

from datetime import date

from cloudlens.budget.engine import compute_budget_status
from cloudlens.config import BudgetConfig
from cloudlens.models import CostRecord


def _cost(project: str, day: date, amount: float) -> CostRecord:
    return CostRecord(
        provider="aws", account_id="1", resource_id=None, service="EC2", project=project, date=day, amount=amount
    )


def test_threshold_crossed_matches_percent_used():
    budgets = [BudgetConfig(project="p1", monthly_limit=100, alert_thresholds=[50, 80, 100])]
    costs = [_cost("p1", date(2026, 6, 1), 60)]
    status = compute_budget_status(budgets, costs, as_of=date(2026, 6, 1))[0]
    assert status.percent_used == 60.0
    assert [a.threshold_crossed for a in status.alerts] == [50]


def test_no_alerts_when_under_lowest_threshold():
    budgets = [BudgetConfig(project="p1", monthly_limit=100, alert_thresholds=[50, 80, 100])]
    costs = [_cost("p1", date(2026, 6, 1), 10)]
    status = compute_budget_status(budgets, costs, as_of=date(2026, 6, 1))[0]
    assert status.alerts == []


def test_multiple_thresholds_crossed_at_once():
    budgets = [BudgetConfig(project="p1", monthly_limit=100, alert_thresholds=[50, 80, 100])]
    costs = [_cost("p1", date(2026, 6, 1), 150)]
    status = compute_budget_status(budgets, costs, as_of=date(2026, 6, 1))[0]
    assert [a.threshold_crossed for a in status.alerts] == [50, 80, 100]


def test_forecast_flags_projected_overrun():
    # June has 30 days; on day 1, $50 spent -> forecast = 50/1*30 = 1500, well over the $300 limit.
    budgets = [BudgetConfig(project="p1", monthly_limit=300, alert_thresholds=[50, 80, 100])]
    costs = [_cost("p1", date(2026, 6, 1), 50)]
    status = compute_budget_status(budgets, costs, as_of=date(2026, 6, 1))[0]
    assert status.forecast_exceeds_budget is True
    assert status.forecast_month_end == 1500.0


def test_forecast_does_not_flag_when_on_track():
    # 10 days in, $5/day -> forecast = 50/10*30 = 150, under the $300 limit.
    budgets = [BudgetConfig(project="p1", monthly_limit=300, alert_thresholds=[50, 80, 100])]
    costs = [_cost("p1", date(2026, 6, d), 5) for d in range(1, 11)]
    status = compute_budget_status(budgets, costs, as_of=date(2026, 6, 10))[0]
    assert status.forecast_exceeds_budget is False


def test_costs_outside_current_month_are_excluded():
    budgets = [BudgetConfig(project="p1", monthly_limit=100, alert_thresholds=[50, 80, 100])]
    costs = [_cost("p1", date(2026, 5, 15), 1000)]  # previous month, should not count
    status = compute_budget_status(budgets, costs, as_of=date(2026, 6, 1))[0]
    assert status.spent == 0.0


def test_costs_for_other_projects_are_excluded():
    budgets = [BudgetConfig(project="p1", monthly_limit=100, alert_thresholds=[50, 80, 100])]
    costs = [_cost("other-project", date(2026, 6, 1), 1000)]
    status = compute_budget_status(budgets, costs, as_of=date(2026, 6, 1))[0]
    assert status.spent == 0.0
