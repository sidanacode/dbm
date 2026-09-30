"""Versioned protocol and domain types for DBM."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown protocol fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OperationKind(StrEnum):
    ADD_TABLE = "add_table"
    DROP_TABLE = "drop_table"
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    ALTER_COLUMN = "alter_column"
    RENAME_COLUMN = "rename_column"
    ADD_INDEX = "add_index"
    DROP_INDEX = "drop_index"
    ADD_FOREIGN_KEY = "add_foreign_key"
    DROP_FOREIGN_KEY = "drop_foreign_key"


class ObjectRef(StrictModel):
    """Stable identity for a PostgreSQL schema object."""

    schema_name: str = Field(default="public", min_length=1)
    table_name: str = Field(min_length=1)
    column_name: str | None = None
    object_name: str | None = None

    @property
    def table_key(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)

    @property
    def path(self) -> str:
        base = f"{self.schema_name}.{self.table_name}"
        if self.column_name:
            return f"{base}.{self.column_name}"
        if self.object_name:
            return f"{base}#{self.object_name}"
        return base


class SchemaOperation(StrictModel):
    """One normalized schema operation in intent protocol version 1."""

    kind: OperationKind
    object: ObjectRef
    new_object: ObjectRef | None = None
    references: ObjectRef | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> SchemaOperation:
        column_kinds = {
            OperationKind.ADD_COLUMN,
            OperationKind.DROP_COLUMN,
            OperationKind.ALTER_COLUMN,
            OperationKind.RENAME_COLUMN,
        }
        named_kinds = {
            OperationKind.ADD_INDEX,
            OperationKind.DROP_INDEX,
            OperationKind.ADD_FOREIGN_KEY,
            OperationKind.DROP_FOREIGN_KEY,
        }

        if self.kind in column_kinds and not self.object.column_name:
            raise ValueError(f"{self.kind} requires object.column_name")
        if self.kind in named_kinds and not self.object.object_name:
            raise ValueError(f"{self.kind} requires object.object_name")
        if self.kind == OperationKind.RENAME_COLUMN:
            if not self.new_object or not self.new_object.column_name:
                raise ValueError("rename_column requires new_object.column_name")
            if self.object.table_key != self.new_object.table_key:
                raise ValueError("rename_column cannot move a column between tables")
        elif self.new_object is not None:
            raise ValueError("new_object is only valid for rename_column")
        if self.kind == OperationKind.ADD_FOREIGN_KEY and self.references is None:
            raise ValueError("add_foreign_key requires references")
        return self


class IntentSource(StrictModel):
    branch: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1)
    base_heads: list[str] = Field(min_length=1)
    migration_graph_digest: str = Field(min_length=1)


class IntentSubmission(StrictModel):
    protocol_version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=200)
    source: IntentSource
    operations: list[SchemaOperation] = Field(min_length=1)


class IntentStatus(StrEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    LEASED = "leased"
    MERGED = "merged"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class CheckStatus(StrEnum):
    SAFE = "safe"
    STALE = "stale"
    DEPENDENT = "dependent"
    CONFLICT = "conflict"


class FindingSeverity(StrEnum):
    STALE = "stale"
    DEPENDENCY = "dependency"
    CONFLICT = "conflict"


class FindingCode(StrEnum):
    STALE_BASE = "stale_base"
    DUPLICATE_ADD = "duplicate_add"
    TABLE_DROPPED = "table_dropped"
    OBJECT_DROPPED = "object_dropped"
    CONCURRENT_ALTER = "concurrent_alter"
    OBJECT_RENAMED = "object_renamed"
    CONCURRENT_RENAME = "concurrent_rename"
    REQUIRES_PENDING_OBJECT = "requires_pending_object"


class CheckFinding(StrictModel):
    severity: FindingSeverity
    code: FindingCode
    message: str
    operation_index: int
    related_intent_id: str | None = None
    object: ObjectRef
    new_object: ObjectRef | None = None


class CheckResult(StrictModel):
    status: CheckStatus
    findings: list[CheckFinding]


class CheckableIntent(StrictModel):
    """Minimal intent projection accepted by the pure conflict engine."""

    id: str
    migration_graph_digest: str
    operations: list[SchemaOperation]
