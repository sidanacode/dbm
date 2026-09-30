"""Application service layer for coordinator operations."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select  # isort: split

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from dbm_coordinator.conflicts import check_intent as run_conflict_check
from dbm_coordinator.domain import (
    CheckableIntent,
    CheckResult,
    CheckStatus,
    IntentStatus,
    IntentSubmission,
    SchemaOperation,
)
from dbm_coordinator.models import (
    AuditEventModel,
    IntentCheckModel,
    IntentModel,
    MigrationOperationModel,
    ProjectModel,
    RevisionLeaseModel,
    utc_now,
)

ACTIVE_STATUSES = {
    IntentStatus.SUBMITTED.value,
    IntentStatus.APPROVED.value,
    IntentStatus.LEASED.value,
}


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CoordinatorService:
    def __init__(self, session: Session, lease_ttl_seconds: int = 600) -> None:
        self.session = session
        self.lease_ttl_seconds = lease_ttl_seconds

    def create_project(
        self,
        *,
        slug: str,
        name: str,
        default_branch: str,
        current_heads: list[str],
        graph_digest: str,
    ) -> ProjectModel:
        project = ProjectModel(
            slug=slug,
            name=name,
            default_branch=default_branch,
            current_heads=current_heads,
            graph_digest=graph_digest,
        )
        self.session.add(project)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ServiceError(
                "project_slug_exists", f"Project slug {slug!r} already exists.", 409
            ) from exc
        self._audit(project.id, "project.created", {"slug": slug})
        self.session.commit()
        return project

    def get_project(self, project_id: str) -> ProjectModel:
        project = self.session.get(ProjectModel, project_id)
        if project is None:
            raise ServiceError("project_not_found", "Project was not found.", 404)
        return project

    def update_project_state(
        self, project_id: str, *, current_heads: list[str], graph_digest: str
    ) -> ProjectModel:
        project = self.get_project(project_id)
        old_digest = project.graph_digest
        project.current_heads = current_heads
        project.graph_digest = graph_digest
        project.updated_at = utc_now()
        self._audit(
            project.id,
            "project.state_updated",
            {"old_graph_digest": old_digest, "graph_digest": graph_digest, "heads": current_heads},
        )
        self.session.commit()
        return project

    def submit_intent(self, project_id: str, submission: IntentSubmission) -> IntentModel:
        project = self.get_project(project_id)
        intent = IntentModel(
            project_id=project.id,
            protocol_version=submission.protocol_version,
            title=submission.title,
            branch=submission.source.branch,
            commit_sha=submission.source.commit_sha,
            base_heads=submission.source.base_heads,
            graph_digest=submission.source.migration_graph_digest,
            status=IntentStatus.SUBMITTED.value,
        )
        for position, operation in enumerate(submission.operations):
            intent.operations.append(self._operation_model(position, operation))
        self.session.add(intent)
        self.session.flush()
        self._audit(
            project.id,
            "intent.submitted",
            {"operation_count": len(intent.operations)},
            intent.id,
        )
        self.session.commit()
        return self.get_intent(intent.id)

    def get_intent(self, intent_id: str) -> IntentModel:
        statement = (
            select(IntentModel)
            .where(IntentModel.id == intent_id)
            .options(selectinload(IntentModel.operations))
        )
        intent = self.session.scalar(statement)
        if intent is None:
            raise ServiceError("intent_not_found", "Intent was not found.", 404)
        return intent

    def list_intents(self, project_id: str) -> list[IntentModel]:
        self.get_project(project_id)
        statement = (
            select(IntentModel)
            .where(IntentModel.project_id == project_id)
            .options(selectinload(IntentModel.operations))
            .order_by(IntentModel.created_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def check_intent(self, intent_id: str) -> CheckResult:
        intent = self.get_intent(intent_id)
        project = self.get_project(intent.project_id)
        statement = (
            select(IntentModel)
            .where(
                IntentModel.project_id == project.id,
                IntentModel.status.in_(ACTIVE_STATUSES),
                IntentModel.id != intent.id,
            )
            .options(selectinload(IntentModel.operations))
        )
        active = list(self.session.scalars(statement).all())
        result = run_conflict_check(
            candidate=self._checkable(intent),
            active_intents=[self._checkable(item) for item in active],
            accepted_graph_digest=project.graph_digest,
        )
        intent.latest_check_status = result.status.value
        intent.checks.append(
            IntentCheckModel(
                status=result.status.value,
                findings_data=[item.model_dump(mode="json") for item in result.findings],
            )
        )
        self._audit(
            project.id,
            "intent.checked",
            {"status": result.status.value, "finding_count": len(result.findings)},
            intent.id,
        )
        self.session.commit()
        return result

    def approve_intent(self, intent_id: str) -> IntentModel:
        intent = self.get_intent(intent_id)
        if intent.status == IntentStatus.APPROVED.value:
            return intent
        if intent.status != IntentStatus.SUBMITTED.value:
            raise ServiceError(
                "invalid_intent_transition",
                f"Cannot approve an intent in {intent.status!r} state.",
                409,
            )
        result = self.check_intent(intent.id)
        intent = self.get_intent(intent.id)
        if result.status == CheckStatus.CONFLICT:
            raise ServiceError(
                "intent_has_conflicts", "A conflicting intent cannot be approved.", 409
            )
        intent.status = IntentStatus.APPROVED.value
        intent.updated_at = utc_now()
        self._audit(
            intent.project_id,
            "intent.approved",
            {"check_status": result.status},
            intent.id,
        )
        self.session.commit()
        return intent

    def cancel_intent(self, intent_id: str) -> IntentModel:
        intent = self.get_intent(intent_id)
        if intent.status in {
            IntentStatus.MERGED.value,
            IntentStatus.SUPERSEDED.value,
        }:
            raise ServiceError(
                "invalid_intent_transition",
                f"Cannot cancel an intent in {intent.status!r} state.",
                409,
            )
        if intent.status == IntentStatus.CANCELLED.value:
            return intent
        self._release_active_intent_leases(intent.id, "cancelled")
        intent.status = IntentStatus.CANCELLED.value
        intent.updated_at = utc_now()
        self._audit(intent.project_id, "intent.cancelled", {}, intent.id)
        self.session.commit()
        return intent

    def acquire_lease(self, intent_id: str) -> RevisionLeaseModel:
        intent = self.get_intent(intent_id)
        # Locking the project row serializes lease acquisition in PostgreSQL. Without
        # this, two transactions can both observe an empty lease table and proceed.
        project = self.session.scalar(
            select(ProjectModel).where(ProjectModel.id == intent.project_id).with_for_update()
        )
        if project is None:
            raise ServiceError("project_not_found", "Project was not found.", 404)
        if intent.status != IntentStatus.APPROVED.value:
            raise ServiceError(
                "intent_not_approved",
                "Only an approved intent can acquire a lease.",
                409,
            )
        if intent.graph_digest != project.graph_digest:
            raise ServiceError(
                "stale_intent",
                "Refresh the accepted migration graph before acquiring a lease.",
                409,
            )

        self._expire_leases(project.id)
        statement = select(RevisionLeaseModel).where(
            RevisionLeaseModel.project_id == project.id,
            RevisionLeaseModel.state == "active",
        )
        existing = self.session.scalar(statement)
        if existing:
            raise ServiceError(
                "project_lease_held",
                "Project already has an active finalization lease held by "
                f"intent {existing.intent_id}.",
                409,
            )

        lease = RevisionLeaseModel(
            project_id=project.id,
            intent_id=intent.id,
            state="active",
            graph_digest=project.graph_digest,
            expires_at=utc_now() + timedelta(seconds=self.lease_ttl_seconds),
        )
        self.session.add(lease)
        intent.status = IntentStatus.LEASED.value
        self.session.flush()
        self._audit(
            project.id,
            "lease.acquired",
            {"lease_id": lease.id, "expires_at": lease.expires_at.isoformat()},
            intent.id,
        )
        self.session.commit()
        return lease

    def release_lease(self, lease_id: str) -> RevisionLeaseModel:
        lease = self.session.get(RevisionLeaseModel, lease_id)
        if lease is None:
            raise ServiceError("lease_not_found", "Lease was not found.", 404)
        if lease.state != "active":
            return lease
        lease.state = "released"
        lease.released_at = utc_now()
        intent = self.get_intent(lease.intent_id)
        if intent.status == IntentStatus.LEASED.value:
            intent.status = IntentStatus.APPROVED.value
        self._audit(lease.project_id, "lease.released", {"lease_id": lease.id}, lease.intent_id)
        self.session.commit()
        return lease

    def _expire_leases(self, project_id: str) -> None:
        statement = select(RevisionLeaseModel).where(
            RevisionLeaseModel.project_id == project_id,
            RevisionLeaseModel.state == "active",
            RevisionLeaseModel.expires_at <= utc_now(),
        )
        for lease in self.session.scalars(statement):
            lease.state = "expired"
            intent = self.session.get(IntentModel, lease.intent_id)
            if intent and intent.status == IntentStatus.LEASED.value:
                intent.status = IntentStatus.APPROVED.value

    def _release_active_intent_leases(self, intent_id: str, state: str) -> None:
        statement = select(RevisionLeaseModel).where(
            RevisionLeaseModel.intent_id == intent_id,
            RevisionLeaseModel.state == "active",
        )
        for lease in self.session.scalars(statement):
            lease.state = state
            lease.released_at = utc_now()

    def _checkable(self, intent: IntentModel) -> CheckableIntent:
        return CheckableIntent(
            id=intent.id,
            migration_graph_digest=intent.graph_digest,
            operations=[self._operation_domain(item) for item in intent.operations],
        )

    @staticmethod
    def _operation_model(position: int, operation: SchemaOperation) -> MigrationOperationModel:
        return MigrationOperationModel(
            position=position,
            kind=operation.kind.value,
            object_data=operation.object.model_dump(mode="json"),
            new_object_data=(
                operation.new_object.model_dump(mode="json") if operation.new_object else None
            ),
            references_data=(
                operation.references.model_dump(mode="json") if operation.references else None
            ),
            before_data=operation.before,
            after_data=operation.after,
        )

    @staticmethod
    def _operation_domain(operation: MigrationOperationModel) -> SchemaOperation:
        return SchemaOperation.model_validate(
            {
                "kind": operation.kind,
                "object": operation.object_data,
                "new_object": operation.new_object_data,
                "references": operation.references_data,
                "before": operation.before_data,
                "after": operation.after_data,
            }
        )

    def intent_payload(self, intent: IntentModel) -> dict[str, Any]:
        return {
            "id": intent.id,
            "project_id": intent.project_id,
            "protocol_version": intent.protocol_version,
            "title": intent.title,
            "source": {
                "branch": intent.branch,
                "commit_sha": intent.commit_sha,
                "base_heads": intent.base_heads,
                "migration_graph_digest": intent.graph_digest,
            },
            "operations": [
                self._operation_domain(operation).model_dump(mode="json")
                for operation in intent.operations
            ],
            "status": intent.status,
            "latest_check_status": intent.latest_check_status,
            "created_at": intent.created_at,
            "updated_at": intent.updated_at,
        }

    def _audit(
        self,
        project_id: str,
        event_type: str,
        event_data: dict[str, Any],
        intent_id: str | None = None,
    ) -> None:
        self.session.add(
            AuditEventModel(
                project_id=project_id,
                intent_id=intent_id,
                event_type=event_type,
                event_data=event_data,
            )
        )
