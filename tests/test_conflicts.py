from dbm_coordinator.conflicts import check_intent
from dbm_coordinator.domain import (
    CheckableIntent,
    CheckStatus,
    FindingCode,
    ObjectRef,
    OperationKind,
    SchemaOperation,
)

DIGEST = "sha256:accepted"


def ref(
    table: str,
    column: str | None = None,
    name: str | None = None,
    schema: str = "public",
) -> ObjectRef:
    return ObjectRef(
        schema_name=schema,
        table_name=table,
        column_name=column,
        object_name=name,
    )


def intent(intent_id: str, *operations: SchemaOperation, digest: str = DIGEST) -> CheckableIntent:
    return CheckableIntent(
        id=intent_id,
        migration_graph_digest=digest,
        operations=list(operations),
    )


def operation(kind: OperationKind, object_ref: ObjectRef, **kwargs: object) -> SchemaOperation:
    return SchemaOperation(kind=kind, object=object_ref, **kwargs)


def test_ac_001_rename_conflict_returns_new_identity() -> None:
    rename = operation(
        OperationKind.RENAME_COLUMN,
        ref("users", "name"),
        new_object=ref("users", "full_name"),
    )
    alter = operation(OperationKind.ALTER_COLUMN, ref("users", "name"))

    result = check_intent(intent("candidate", alter), [intent("rename-intent", rename)], DIGEST)

    assert result.status == CheckStatus.CONFLICT
    assert result.findings[0].code == FindingCode.OBJECT_RENAMED
    assert result.findings[0].related_intent_id == "rename-intent"
    assert result.findings[0].new_object == ref("users", "full_name")


def test_ac_002_independent_changes_are_safe() -> None:
    phone = operation(OperationKind.ADD_COLUMN, ref("users", "phone"))
    reference = operation(OperationKind.ADD_COLUMN, ref("orders", "reference"))

    result = check_intent(intent("candidate", reference), [intent("other", phone)], DIGEST)

    assert result.status == CheckStatus.SAFE
    assert result.findings == []


def test_ac_003_non_overlapping_stale_intent_is_stale() -> None:
    timezone = operation(OperationKind.ADD_COLUMN, ref("users", "timezone"))

    result = check_intent(intent("candidate", timezone, digest="sha256:old"), [], DIGEST)

    assert result.status == CheckStatus.STALE
    assert result.findings[0].code == FindingCode.STALE_BASE


def test_ac_004_foreign_key_depends_on_pending_table() -> None:
    create_orgs = operation(OperationKind.ADD_TABLE, ref("organizations"))
    add_fk = operation(
        OperationKind.ADD_FOREIGN_KEY,
        ref("users", name="fk_users_organization"),
        references=ref("organizations", "id"),
    )

    result = check_intent(intent("candidate", add_fk), [intent("create-orgs", create_orgs)], DIGEST)

    assert result.status == CheckStatus.DEPENDENT
    assert result.findings[0].code == FindingCode.REQUIRES_PENDING_OBJECT
    assert result.findings[0].related_intent_id == "create-orgs"


def test_duplicate_column_add_conflicts() -> None:
    add_phone = operation(OperationKind.ADD_COLUMN, ref("users", "phone"))
    result = check_intent(intent("candidate", add_phone), [intent("other", add_phone)], DIGEST)
    assert result.status == CheckStatus.CONFLICT
    assert result.findings[0].code == FindingCode.DUPLICATE_ADD


def test_drop_table_conflicts_with_column_change() -> None:
    drop_users = operation(OperationKind.DROP_TABLE, ref("users"))
    add_phone = operation(OperationKind.ADD_COLUMN, ref("users", "phone"))
    result = check_intent(intent("candidate", add_phone), [intent("other", drop_users)], DIGEST)
    assert result.status == CheckStatus.CONFLICT
    assert result.findings[0].code == FindingCode.TABLE_DROPPED


def test_drop_column_conflicts_with_alter() -> None:
    drop_name = operation(OperationKind.DROP_COLUMN, ref("users", "name"))
    alter_name = operation(OperationKind.ALTER_COLUMN, ref("users", "name"))
    result = check_intent(intent("candidate", alter_name), [intent("other", drop_name)], DIGEST)
    assert result.status == CheckStatus.CONFLICT
    assert result.findings[0].code == FindingCode.OBJECT_DROPPED


def test_concurrent_alter_conflicts() -> None:
    alter_name = operation(OperationKind.ALTER_COLUMN, ref("users", "name"))
    result = check_intent(intent("candidate", alter_name), [intent("other", alter_name)], DIGEST)
    assert result.status == CheckStatus.CONFLICT
    assert result.findings[0].code == FindingCode.CONCURRENT_ALTER


def test_incompatible_renames_conflict() -> None:
    rename_full = operation(
        OperationKind.RENAME_COLUMN,
        ref("users", "name"),
        new_object=ref("users", "full_name"),
    )
    rename_display = operation(
        OperationKind.RENAME_COLUMN,
        ref("users", "name"),
        new_object=ref("users", "display_name"),
    )
    result = check_intent(
        intent("candidate", rename_display), [intent("other", rename_full)], DIGEST
    )
    assert result.status == CheckStatus.CONFLICT
    assert result.findings[0].code == FindingCode.CONCURRENT_RENAME


def test_duplicate_index_add_conflicts() -> None:
    add_index = operation(OperationKind.ADD_INDEX, ref("users", name="ix_users_email"))
    result = check_intent(intent("candidate", add_index), [intent("other", add_index)], DIGEST)
    assert result.status == CheckStatus.CONFLICT
    assert result.findings[0].code == FindingCode.DUPLICATE_ADD


def test_conflict_has_priority_over_stale() -> None:
    alter_name = operation(OperationKind.ALTER_COLUMN, ref("users", "name"))
    result = check_intent(
        intent("candidate", alter_name, digest="sha256:old"),
        [intent("other", alter_name)],
        DIGEST,
    )
    assert result.status == CheckStatus.CONFLICT
    assert {finding.code for finding in result.findings} == {
        FindingCode.STALE_BASE,
        FindingCode.CONCURRENT_ALTER,
    }
