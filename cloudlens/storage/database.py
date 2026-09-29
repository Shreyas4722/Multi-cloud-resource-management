"""SQLAlchemy 2.0 ORM models and engine/session setup for the SQLite store."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ResourceORM(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    account_id: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String, index=True)
    instance_size: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    hourly_cost: Mapped[float] = mapped_column(Float, default=0.0)
    project: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    attached: Mapped[bool | None] = mapped_column(nullable=True)
    attached_to: Mapped[str | None] = mapped_column(String, nullable=True)


class CostRecordORM(Base):
    __tablename__ = "cost_records"

    # Surrogate key derived from the natural key so re-syncing the same day's
    # cost for the same resource/service updates the row instead of duplicating.
    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    account_id: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    service: Mapped[str] = mapped_column(String)
    project: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="USD")


class RecommendationORM(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    resource_id: Mapped[str] = mapped_column(String, index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    rule_id: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    current_monthly_cost: Mapped[float] = mapped_column(Float)
    estimated_monthly_saving: Mapped[float] = mapped_column(Float)
    suggested_action: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class BudgetAlertORM(Base):
    __tablename__ = "budget_alerts"

    # Surrogate key: one alert row per (project, month, threshold_crossed).
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project: Mapped[str] = mapped_column(String, index=True)
    month: Mapped[str] = mapped_column(String, index=True)
    spent: Mapped[float] = mapped_column(Float)
    limit: Mapped[float] = mapped_column(Float)
    percent_used: Mapped[float] = mapped_column(Float)
    threshold_crossed: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)


def make_engine(db_path: str | Path):
    """Create a SQLAlchemy engine for the SQLite file at `db_path`, creating
    parent directories and tables as needed."""
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker) -> Iterator[Session]:
    """Provide a transactional session, committing on success and rolling
    back on error."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
