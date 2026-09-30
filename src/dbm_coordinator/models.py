"""Persistence models for coordinator metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dbm_coordinator.database import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    default_branch: Mapped[str] = mapped_column(String(200), default="main")
    current_heads: Mapped[list[str]] = mapped_column(JSON, default=list)
    graph_digest: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    intents: Mapped[list[IntentModel]] = relationship(back_populates="project")


class IntentModel(Base):
    __tablename__ = "intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    protocol_version: Mapped[int] = mapped_column(default=1)
    title: Mapped[str] = mapped_column(String(200))
    branch: Mapped[str] = mapped_column(String(300))
    commit_sha: Mapped[str] = mapped_column(String(100))
    base_heads: Mapped[list[str]] = mapped_column(JSON)
    graph_digest: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), index=True)
    latest_check_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    project: Mapped[ProjectModel] = relationship(back_populates="intents")
    operations: Mapped[list[MigrationOperationModel]] = relationship(
        back_populates="intent",
        cascade="all, delete-orphan",
        order_by="MigrationOperationModel.position",
    )
    checks: Mapped[list[IntentCheckModel]] = relationship(
        back_populates="intent", cascade="all, delete-orphan"
    )


class MigrationOperationModel(Base):
    __tablename__ = "migration_operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    intent_id: Mapped[str] = mapped_column(ForeignKey("intents.id"), index=True)
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(String(40))
    object_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    new_object_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    references_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    intent: Mapped[IntentModel] = relationship(back_populates="operations")


class IntentCheckModel(Base):
    __tablename__ = "intent_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    intent_id: Mapped[str] = mapped_column(ForeignKey("intents.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    findings_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    intent: Mapped[IntentModel] = relationship(back_populates="checks")


class RevisionLeaseModel(Base):
    __tablename__ = "revision_leases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("intents.id"), index=True)
    state: Mapped[str] = mapped_column(String(20), index=True)
    graph_digest: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    released_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_revision_leases_project_state", "project_id", "state"),)


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    intent_id: Mapped[str | None] = mapped_column(ForeignKey("intents.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    actor: Mapped[str] = mapped_column(Text, default="api")
