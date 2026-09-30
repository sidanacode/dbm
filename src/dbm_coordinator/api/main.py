"""FastAPI application for the DBM coordinator."""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from dbm_coordinator.api.schemas import (
    IntentRead,
    LeaseRead,
    ProjectCreate,
    ProjectRead,
    ProjectStateUpdate,
)
from dbm_coordinator.database import Database
from dbm_coordinator.domain import CheckResult, IntentSubmission
from dbm_coordinator.service import CoordinatorService, ServiceError
from dbm_coordinator.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    database = Database(runtime_settings.database_url)
    bearer = HTTPBearer(auto_error=False)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> Any:
        database.create_all()
        yield

    app = FastAPI(
        title="DBM Coordinator",
        version="0.1.0",
        description="Pre-merge coordination for database migration intent.",
        lifespan=lifespan,
    )
    app.state.database = database
    app.state.settings = runtime_settings

    def get_session() -> Iterator[Session]:
        yield from database.sessions()

    def require_auth(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> None:
        expected = runtime_settings.api_token
        if expected is None:
            return
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise ServiceError("unauthorized", "A bearer token is required.", 401)
        if credentials.credentials != expected:
            raise ServiceError("unauthorized", "The bearer token is invalid.", 401)

    SessionDependency = Annotated[Session, Depends(get_session)]
    AuthDependency = Annotated[None, Depends(require_auth)]

    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/projects", response_model=ProjectRead, status_code=201)
    def create_project(
        body: ProjectCreate, session: SessionDependency, _: AuthDependency
    ) -> ProjectRead:
        project = CoordinatorService(session).create_project(**body.model_dump())
        return ProjectRead.model_validate(project, from_attributes=True)

    @app.get("/v1/projects/{project_id}/state", response_model=ProjectRead)
    def get_project(project_id: str, session: SessionDependency, _: AuthDependency) -> ProjectRead:
        project = CoordinatorService(session).get_project(project_id)
        return ProjectRead.model_validate(project, from_attributes=True)

    @app.put("/v1/projects/{project_id}/state", response_model=ProjectRead)
    def update_project(
        project_id: str,
        body: ProjectStateUpdate,
        session: SessionDependency,
        _: AuthDependency,
    ) -> ProjectRead:
        project = CoordinatorService(session).update_project_state(project_id, **body.model_dump())
        return ProjectRead.model_validate(project, from_attributes=True)

    @app.post("/v1/projects/{project_id}/intents", response_model=IntentRead, status_code=201)
    def submit_intent(
        project_id: str,
        body: IntentSubmission,
        session: SessionDependency,
        _: AuthDependency,
    ) -> IntentRead:
        service = CoordinatorService(session)
        intent = service.submit_intent(project_id, body)
        return IntentRead.model_validate(service.intent_payload(intent))

    @app.get("/v1/projects/{project_id}/intents", response_model=list[IntentRead])
    def list_intents(
        project_id: str, session: SessionDependency, _: AuthDependency
    ) -> list[IntentRead]:
        service = CoordinatorService(session)
        return [
            IntentRead.model_validate(service.intent_payload(intent))
            for intent in service.list_intents(project_id)
        ]

    @app.get("/v1/intents/{intent_id}", response_model=IntentRead)
    def get_intent(intent_id: str, session: SessionDependency, _: AuthDependency) -> IntentRead:
        service = CoordinatorService(session)
        return IntentRead.model_validate(service.intent_payload(service.get_intent(intent_id)))

    @app.post("/v1/intents/{intent_id}/check", response_model=CheckResult)
    def check_intent(intent_id: str, session: SessionDependency, _: AuthDependency) -> CheckResult:
        return CoordinatorService(session).check_intent(intent_id)

    @app.post("/v1/intents/{intent_id}/approve", response_model=IntentRead)
    def approve_intent(intent_id: str, session: SessionDependency, _: AuthDependency) -> IntentRead:
        service = CoordinatorService(session)
        return IntentRead.model_validate(service.intent_payload(service.approve_intent(intent_id)))

    @app.post("/v1/intents/{intent_id}/cancel", response_model=IntentRead)
    def cancel_intent(intent_id: str, session: SessionDependency, _: AuthDependency) -> IntentRead:
        service = CoordinatorService(session)
        return IntentRead.model_validate(service.intent_payload(service.cancel_intent(intent_id)))

    @app.post("/v1/intents/{intent_id}/leases", response_model=LeaseRead, status_code=201)
    def acquire_lease(intent_id: str, session: SessionDependency, _: AuthDependency) -> LeaseRead:
        lease = CoordinatorService(session, runtime_settings.lease_ttl_seconds).acquire_lease(
            intent_id
        )
        return LeaseRead.model_validate(lease, from_attributes=True)

    @app.post("/v1/leases/{lease_id}/release", response_model=LeaseRead)
    def release_lease(lease_id: str, session: SessionDependency, _: AuthDependency) -> LeaseRead:
        lease = CoordinatorService(session).release_lease(lease_id)
        return LeaseRead.model_validate(lease, from_attributes=True)

    return app


app = create_app()


def run() -> None:
    uvicorn.run("dbm_coordinator.api.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
