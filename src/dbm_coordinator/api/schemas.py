"""HTTP request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from dbm_coordinator.domain import IntentSource, IntentStatus, SchemaOperation


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(ApiModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    name: str = Field(min_length=1, max_length=200)
    default_branch: str = Field(default="main", min_length=1, max_length=200)
    current_heads: list[str] = Field(min_length=1)
    graph_digest: str = Field(min_length=1)


class ProjectStateUpdate(ApiModel):
    current_heads: list[str] = Field(min_length=1)
    graph_digest: str = Field(min_length=1)


class ProjectRead(ApiModel):
    id: str
    slug: str
    name: str
    default_branch: str
    current_heads: list[str]
    graph_digest: str
    created_at: datetime
    updated_at: datetime


class IntentRead(ApiModel):
    id: str
    project_id: str
    protocol_version: int
    title: str
    source: IntentSource
    operations: list[SchemaOperation]
    status: IntentStatus
    latest_check_status: str | None
    created_at: datetime
    updated_at: datetime


class LeaseRead(ApiModel):
    id: str
    project_id: str
    intent_id: str
    state: str
    graph_digest: str
    expires_at: datetime
    created_at: datetime
    released_at: datetime | None


class ErrorBody(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorBody
