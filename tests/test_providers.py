import pytest

from dbm_coordinator.providers import (
    ProviderError,
    ProviderKind,
    ProviderLifecycle,
    ProviderManifest,
    create_provider_registry,
)


def test_builtin_catalog_resolves_database_aliases() -> None:
    registry = create_provider_registry()

    postgres = registry.resolve(ProviderKind.DATABASE, "postgres")
    sql_server = registry.resolve(ProviderKind.DATABASE, "mssql")

    assert postgres.id == "postgresql"
    assert postgres.lifecycle == ProviderLifecycle.PREVIEW
    assert sql_server.id == "sql-server"


def test_planned_provider_cannot_be_required() -> None:
    registry = create_provider_registry()

    with pytest.raises(ProviderError) as raised:
        registry.require(ProviderKind.SOURCE_CONTROL, "gitlab", "repository.read")

    assert raised.value.code == "provider_unavailable"


def test_missing_capability_is_not_guessed() -> None:
    registry = create_provider_registry()

    with pytest.raises(ProviderError) as raised:
        registry.require(ProviderKind.MIGRATION, "alembic", "migration.execute")

    assert raised.value.code == "capability_unavailable"


def test_plugin_cannot_replace_a_builtin_alias() -> None:
    registry = create_provider_registry()
    plugin = ProviderManifest(
        id="cockroachdb",
        kind=ProviderKind.DATABASE,
        display_name="CockroachDB",
        lifecycle=ProviderLifecycle.PREVIEW,
        capabilities=("catalog.inspect",),
        aliases=("postgres",),
    )

    with pytest.raises(ProviderError) as raised:
        registry.register(plugin)

    assert raised.value.code == "duplicate_provider_alias"


def test_third_party_provider_can_extend_the_catalog() -> None:
    registry = create_provider_registry()
    plugin = ProviderManifest(
        id="cockroachdb",
        kind=ProviderKind.DATABASE,
        display_name="CockroachDB",
        lifecycle=ProviderLifecycle.PREVIEW,
        capabilities=("catalog.inspect",),
        aliases=("cockroach",),
    )

    registry.register(plugin)

    assert (
        registry.require(ProviderKind.DATABASE, "cockroach", "catalog.inspect").id == "cockroachdb"
    )
