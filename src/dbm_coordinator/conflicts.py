"""Pure deterministic conflict detection for DBM intents."""

from __future__ import annotations

from collections.abc import Iterable

from dbm_coordinator.domain import (
    CheckableIntent,
    CheckFinding,
    CheckResult,
    CheckStatus,
    FindingCode,
    FindingSeverity,
    ObjectRef,
    OperationKind,
    SchemaOperation,
)


def check_intent(
    candidate: CheckableIntent,
    active_intents: Iterable[CheckableIntent],
    accepted_graph_digest: str,
) -> CheckResult:
    """Compare a candidate with accepted state and active team intent."""

    findings: list[CheckFinding] = []
    if candidate.migration_graph_digest != accepted_graph_digest:
        findings.append(
            CheckFinding(
                severity=FindingSeverity.STALE,
                code=FindingCode.STALE_BASE,
                message="The intent was created from a different accepted migration graph.",
                operation_index=0,
                object=candidate.operations[0].object,
            )
        )

    for active in active_intents:
        if active.id == candidate.id:
            continue
        for index, operation in enumerate(candidate.operations):
            for active_operation in active.operations:
                finding = _compare_operations(
                    operation=operation,
                    other=active_operation,
                    operation_index=index,
                    related_intent_id=active.id,
                )
                if finding is not None:
                    findings.append(finding)

    findings = _deduplicate(findings)
    if any(item.severity == FindingSeverity.CONFLICT for item in findings):
        status = CheckStatus.CONFLICT
    elif any(item.severity == FindingSeverity.DEPENDENCY for item in findings):
        status = CheckStatus.DEPENDENT
    elif any(item.severity == FindingSeverity.STALE for item in findings):
        status = CheckStatus.STALE
    else:
        status = CheckStatus.SAFE
    return CheckResult(status=status, findings=findings)


def _compare_operations(
    operation: SchemaOperation,
    other: SchemaOperation,
    operation_index: int,
    related_intent_id: str,
) -> CheckFinding | None:
    dependency = _dependency_finding(operation, other, operation_index, related_intent_id)
    if dependency:
        return dependency

    if operation.object.table_key != other.object.table_key:
        return None

    if operation.kind == OperationKind.DROP_TABLE or other.kind == OperationKind.DROP_TABLE:
        dropped = operation if operation.kind == OperationKind.DROP_TABLE else other
        return _finding(
            FindingCode.TABLE_DROPPED,
            f"Table {dropped.object.path} is dropped by overlapping intent.",
            operation_index,
            related_intent_id,
            dropped.object,
        )

    if operation.kind == OperationKind.ADD_TABLE and other.kind == OperationKind.ADD_TABLE:
        return _duplicate(operation, operation_index, related_intent_id)

    rename = _rename_conflict(operation, other, operation_index, related_intent_id)
    if rename:
        return rename

    if _same_column(operation, other):
        if operation.kind == OperationKind.DROP_COLUMN or other.kind == OperationKind.DROP_COLUMN:
            return _finding(
                FindingCode.OBJECT_DROPPED,
                f"Column {operation.object.path} is dropped by overlapping intent.",
                operation_index,
                related_intent_id,
                operation.object,
            )
        if operation.kind == OperationKind.ADD_COLUMN and other.kind == OperationKind.ADD_COLUMN:
            return _duplicate(operation, operation_index, related_intent_id)
        if (
            operation.kind == OperationKind.ALTER_COLUMN
            and other.kind == OperationKind.ALTER_COLUMN
        ):
            return _finding(
                FindingCode.CONCURRENT_ALTER,
                f"Column {operation.object.path} is altered by more than one intent.",
                operation_index,
                related_intent_id,
                operation.object,
            )
        if {operation.kind, other.kind} == {
            OperationKind.ADD_COLUMN,
            OperationKind.ALTER_COLUMN,
        }:
            return _dependency(
                operation,
                operation_index,
                related_intent_id,
                f"Column {operation.object.path} must be added before it can be altered.",
            )

    if _same_named_object(operation, other):
        if operation.kind in {OperationKind.ADD_INDEX, OperationKind.ADD_FOREIGN_KEY} and (
            other.kind == operation.kind
        ):
            return _duplicate(operation, operation_index, related_intent_id)
        if operation.kind in {OperationKind.DROP_INDEX, OperationKind.DROP_FOREIGN_KEY} or (
            other.kind in {OperationKind.DROP_INDEX, OperationKind.DROP_FOREIGN_KEY}
        ):
            return _finding(
                FindingCode.OBJECT_DROPPED,
                f"Object {operation.object.path} is dropped by overlapping intent.",
                operation_index,
                related_intent_id,
                operation.object,
            )
    return None


def _rename_conflict(
    operation: SchemaOperation,
    other: SchemaOperation,
    operation_index: int,
    related_intent_id: str,
) -> CheckFinding | None:
    if operation.kind == OperationKind.RENAME_COLUMN and other.kind == OperationKind.RENAME_COLUMN:
        if operation.object.column_name != other.object.column_name:
            return None
        if operation.new_object == other.new_object:
            return _finding(
                FindingCode.DUPLICATE_ADD,
                f"The same rename of {operation.object.path} is proposed twice.",
                operation_index,
                related_intent_id,
                operation.object,
                operation.new_object,
            )
        return _finding(
            FindingCode.CONCURRENT_RENAME,
            f"Column {operation.object.path} has incompatible rename targets.",
            operation_index,
            related_intent_id,
            operation.object,
            operation.new_object,
        )

    if other.kind == OperationKind.RENAME_COLUMN and _references_column(operation, other.object):
        return _finding(
            FindingCode.OBJECT_RENAMED,
            f"Column {other.object.path} is renamed by another active intent.",
            operation_index,
            related_intent_id,
            other.object,
            other.new_object,
        )
    if operation.kind == OperationKind.RENAME_COLUMN and _references_column(
        other, operation.object
    ):
        return _finding(
            FindingCode.OBJECT_RENAMED,
            f"Column {operation.object.path} is also referenced by another active intent.",
            operation_index,
            related_intent_id,
            operation.object,
            operation.new_object,
        )
    return None


def _dependency_finding(
    operation: SchemaOperation,
    other: SchemaOperation,
    operation_index: int,
    related_intent_id: str,
) -> CheckFinding | None:
    if operation.kind != OperationKind.ADD_FOREIGN_KEY or operation.references is None:
        return None
    if other.kind != OperationKind.ADD_TABLE:
        return None
    if operation.references.table_key != other.object.table_key:
        return None
    return _dependency(
        operation,
        operation_index,
        related_intent_id,
        f"Foreign key {operation.object.path} requires pending table {other.object.path}.",
    )


def _same_column(left: SchemaOperation, right: SchemaOperation) -> bool:
    return bool(
        left.object.column_name
        and right.object.column_name
        and left.object.column_name == right.object.column_name
    )


def _same_named_object(left: SchemaOperation, right: SchemaOperation) -> bool:
    return bool(
        left.object.object_name
        and right.object.object_name
        and left.object.object_name == right.object.object_name
    )


def _references_column(operation: SchemaOperation, object_ref: ObjectRef) -> bool:
    if operation.object.table_key != object_ref.table_key:
        return False
    if operation.object.column_name == object_ref.column_name:
        return True
    return bool(operation.references and operation.references.path == object_ref.path)


def _duplicate(
    operation: SchemaOperation, operation_index: int, related_intent_id: str
) -> CheckFinding:
    return _finding(
        FindingCode.DUPLICATE_ADD,
        f"Object {operation.object.path} is added by more than one intent.",
        operation_index,
        related_intent_id,
        operation.object,
    )


def _dependency(
    operation: SchemaOperation,
    operation_index: int,
    related_intent_id: str,
    message: str,
) -> CheckFinding:
    return CheckFinding(
        severity=FindingSeverity.DEPENDENCY,
        code=FindingCode.REQUIRES_PENDING_OBJECT,
        message=message,
        operation_index=operation_index,
        related_intent_id=related_intent_id,
        object=operation.object,
    )


def _finding(
    code: FindingCode,
    message: str,
    operation_index: int,
    related_intent_id: str,
    object_ref: ObjectRef,
    new_object: ObjectRef | None = None,
) -> CheckFinding:
    return CheckFinding(
        severity=FindingSeverity.CONFLICT,
        code=code,
        message=message,
        operation_index=operation_index,
        related_intent_id=related_intent_id,
        object=object_ref,
        new_object=new_object,
    )


def _deduplicate(findings: list[CheckFinding]) -> list[CheckFinding]:
    unique: dict[tuple[object, ...], CheckFinding] = {}
    for finding in findings:
        key = (
            finding.severity,
            finding.code,
            finding.operation_index,
            finding.related_intent_id,
            finding.object.path,
            finding.new_object.path if finding.new_object else None,
        )
        unique[key] = finding
    return list(unique.values())
