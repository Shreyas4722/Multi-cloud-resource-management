"""Repository layer: translates between Pydantic models and ORM rows.

Every read/write to the database goes through these functions. Callers
(the rules/budget engines, the public API) never touch SQLAlchemy directly.

Upsert strategy:
- Resources and cost records are upserted by their natural key, so repeated
  syncs update existing rows instead of creating duplicates.
- Recommendations are fully replaced on every `analyze()` run: they are a
  derived, point-in-time view of the current resource set, so a full replace
  is both simpler and avoids leaving stale recommendations behind for
  resources that no longer trigger a rule.
- Budget alerts are upserted by (project, month, threshold_crossed), so
  crossing a new threshold within the same month adds a row without
  disturbing alerts already raised for thresholds crossed earlier that month.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cloudlens.models import (
    BudgetAlert,
    CostRecord,
    Recommendation,
    Resource,
    ResourceState,
    ResourceType,
    Severity,
)
from cloudlens.storage.database import (
    BudgetAlertORM,
    CostRecordORM,
    RecommendationORM,
    ResourceORM,
)


def _cost_record_key(c: CostRecord) -> str:
    return f"{c.provider}:{c.account_id}:{c.resource_id}:{c.service}:{c.date.isoformat()}"


def _alert_key(a: BudgetAlert) -> str:
    return f"{a.project}:{a.month}:{a.threshold_crossed}"


# -- writes -----------------------------------------------------------------


def upsert_resources(session: Session, resources: list[Resource]) -> None:
    for r in resources:
        session.merge(
            ResourceORM(
                id=r.id,
                provider=r.provider,
                account_id=r.account_id,
                region=r.region,
                resource_type=r.resource_type.value,
                instance_size=r.instance_size,
                state=r.state.value,
                tags=r.tags,
                created_at=r.created_at,
                hourly_cost=r.hourly_cost,
                project=r.project,
                attached=r.attached,
                attached_to=r.attached_to,
            )
        )


def upsert_costs(session: Session, costs: list[CostRecord]) -> None:
    for c in costs:
        session.merge(
            CostRecordORM(
                id=_cost_record_key(c),
                provider=c.provider,
                account_id=c.account_id,
                resource_id=c.resource_id,
                service=c.service,
                project=c.project,
                date=c.date,
                amount=c.amount,
                currency=c.currency,
            )
        )


def replace_recommendations(session: Session, recommendations: list[Recommendation]) -> None:
    session.execute(delete(RecommendationORM))
    for rec in recommendations:
        session.add(
            RecommendationORM(
                id=rec.id,
                resource_id=rec.resource_id,
                provider=rec.provider,
                rule_id=rec.rule_id,
                severity=rec.severity.value,
                title=rec.title,
                description=rec.description,
                current_monthly_cost=rec.current_monthly_cost,
                estimated_monthly_saving=rec.estimated_monthly_saving,
                suggested_action=rec.suggested_action,
                created_at=rec.created_at,
            )
        )


def upsert_alerts(session: Session, alerts: list[BudgetAlert]) -> None:
    for a in alerts:
        session.merge(
            BudgetAlertORM(
                id=_alert_key(a),
                project=a.project,
                month=a.month,
                spent=a.spent,
                limit=a.limit,
                percent_used=a.percent_used,
                threshold_crossed=a.threshold_crossed,
                created_at=a.created_at,
            )
        )


# -- reads --------------------------------------------------------------


def list_resources(
    session: Session,
    provider: str | None = None,
    resource_type: ResourceType | None = None,
) -> list[Resource]:
    stmt = select(ResourceORM)
    if provider:
        stmt = stmt.where(ResourceORM.provider == provider)
    if resource_type:
        stmt = stmt.where(ResourceORM.resource_type == resource_type.value)
    rows = session.execute(stmt).scalars().all()
    return [
        Resource(
            id=row.id,
            provider=row.provider,
            account_id=row.account_id,
            region=row.region,
            resource_type=ResourceType(row.resource_type),
            instance_size=row.instance_size,
            state=ResourceState(row.state),
            tags=row.tags or {},
            created_at=row.created_at,
            hourly_cost=row.hourly_cost,
            project=row.project,
            attached=row.attached,
            attached_to=row.attached_to,
        )
        for row in rows
    ]


def list_costs(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = None,
) -> list[CostRecord]:
    stmt = select(CostRecordORM)
    if start_date:
        stmt = stmt.where(CostRecordORM.date >= start_date)
    if end_date:
        stmt = stmt.where(CostRecordORM.date <= end_date)
    if provider:
        stmt = stmt.where(CostRecordORM.provider == provider)
    rows = session.execute(stmt).scalars().all()
    return [
        CostRecord(
            provider=row.provider,
            account_id=row.account_id,
            resource_id=row.resource_id,
            service=row.service,
            project=row.project,
            date=row.date,
            amount=row.amount,
            currency=row.currency,
        )
        for row in rows
    ]


def list_recommendations(
    session: Session,
    provider: str | None = None,
    min_saving: float = 0.0,
    rule_id: str | None = None,
    severity: Severity | None = None,
) -> list[Recommendation]:
    stmt = select(RecommendationORM)
    if provider:
        stmt = stmt.where(RecommendationORM.provider == provider)
    if rule_id:
        stmt = stmt.where(RecommendationORM.rule_id == rule_id)
    if severity:
        stmt = stmt.where(RecommendationORM.severity == severity.value)
    if min_saving:
        stmt = stmt.where(RecommendationORM.estimated_monthly_saving >= min_saving)
    rows = session.execute(stmt).scalars().all()
    return [
        Recommendation(
            id=row.id,
            resource_id=row.resource_id,
            provider=row.provider,
            rule_id=row.rule_id,
            severity=Severity(row.severity),
            title=row.title,
            description=row.description,
            current_monthly_cost=row.current_monthly_cost,
            estimated_monthly_saving=row.estimated_monthly_saving,
            suggested_action=row.suggested_action,
            created_at=row.created_at,
        )
        for row in rows
    ]


def list_budget_alerts(session: Session, project: str | None = None, month: str | None = None) -> list[BudgetAlert]:
    stmt = select(BudgetAlertORM)
    if project:
        stmt = stmt.where(BudgetAlertORM.project == project)
    if month:
        stmt = stmt.where(BudgetAlertORM.month == month)
    rows = session.execute(stmt).scalars().all()
    return [
        BudgetAlert(
            project=row.project,
            month=row.month,
            spent=row.spent,
            limit=row.limit,
            percent_used=row.percent_used,
            threshold_crossed=row.threshold_crossed,
            created_at=row.created_at,
        )
        for row in rows
    ]
