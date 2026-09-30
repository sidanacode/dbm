"""Built-in provider catalog.

Lifecycle and capability fields intentionally describe shipped behavior, not marketing
intent. Planned adapters remain visible so configuration UIs can explain the roadmap.
"""

from dbm_coordinator.providers.models import (
    ProviderKind,
    ProviderLifecycle,
    ProviderManifest,
)

DATABASE_PLAN = (
    "catalog.inspect",
    "schema.fingerprint",
    "transaction.read-only",
    "shadow.validate",
    "migration.deploy",
    "deployment.lock",
)

SOURCE_CONTROL_PLAN = (
    "repository.read",
    "webhook.verify",
    "change-request.read",
    "status.write",
)

CI_PLAN = (
    "job.identity",
    "artifact.handoff",
    "deployment.request",
    "status.write",
)


def builtin_manifests() -> tuple[ProviderManifest, ...]:
    return (
        ProviderManifest(
            id="postgresql",
            kind=ProviderKind.DATABASE,
            display_name="PostgreSQL",
            lifecycle=ProviderLifecycle.PREVIEW,
            capabilities=("coordinator.storage",),
            planned_capabilities=DATABASE_PLAN,
            aliases=("postgres", "pgsql"),
        ),
        *_planned_databases(),
        ProviderManifest(
            id="local-git",
            kind=ProviderKind.SOURCE_CONTROL,
            display_name="Local Git",
            lifecycle=ProviderLifecycle.AVAILABLE,
            capabilities=("repository.inspect",),
            aliases=("git",),
        ),
        *_planned_source_control(),
        *_planned_ci(),
        ProviderManifest(
            id="alembic",
            kind=ProviderKind.MIGRATION,
            display_name="Alembic",
            lifecycle=ProviderLifecycle.PREVIEW,
            capabilities=("graph.inspect",),
            planned_capabilities=("plan.build", "migration.execute"),
        ),
    )


def _planned_databases() -> tuple[ProviderManifest, ...]:
    definitions = (
        ("mysql", "MySQL", ()),
        ("mariadb", "MariaDB", ("maria",)),
        ("sqlite", "SQLite", ("sqlite3",)),
        ("sql-server", "Microsoft SQL Server", ("mssql", "sqlserver")),
        ("oracle", "Oracle Database", ("oracle-db",)),
    )
    return tuple(
        ProviderManifest(
            id=provider_id,
            kind=ProviderKind.DATABASE,
            display_name=display_name,
            lifecycle=ProviderLifecycle.PLANNED,
            planned_capabilities=DATABASE_PLAN,
            aliases=aliases,
        )
        for provider_id, display_name, aliases in definitions
    )


def _planned_source_control() -> tuple[ProviderManifest, ...]:
    definitions = (
        ("github", "GitHub", ()),
        ("gitlab", "GitLab", ()),
        ("bitbucket", "Bitbucket", ()),
        ("gitea", "Gitea", ()),
    )
    return tuple(
        ProviderManifest(
            id=provider_id,
            kind=ProviderKind.SOURCE_CONTROL,
            display_name=display_name,
            lifecycle=ProviderLifecycle.PLANNED,
            planned_capabilities=SOURCE_CONTROL_PLAN,
            aliases=aliases,
        )
        for provider_id, display_name, aliases in definitions
    )


def _planned_ci() -> tuple[ProviderManifest, ...]:
    definitions = (
        ("github-actions", "GitHub Actions", ("gha",)),
        ("gitlab-ci", "GitLab CI/CD", ("gitlab-cicd",)),
        ("jenkins", "Jenkins", ()),
        ("circleci", "CircleCI", ()),
        ("buildkite", "Buildkite", ()),
        ("generic-ci", "Generic CI", ("generic",)),
    )
    return tuple(
        ProviderManifest(
            id=provider_id,
            kind=ProviderKind.CI,
            display_name=display_name,
            lifecycle=ProviderLifecycle.PLANNED,
            planned_capabilities=CI_PLAN,
            aliases=aliases,
        )
        for provider_id, display_name, aliases in definitions
    )
