# Specification 0005: Provider architecture

Status: Accepted for implementation

Date: 30 September 2026

Target branch: `feat/provider-architecture`

## 1. Purpose

Keep DBM's coordination model independent of any one database, source-control host, CI system, or migration engine. Integrations are capability-based providers with versioned manifests and stable identifiers.

"Compatible" means DBM can add an integration without changing its domain protocol. It does not mean every provider has identical database semantics or is fully implemented on day one. The API must report availability honestly.

## 2. Provider kinds

- `database`: catalog inspection, fingerprinting, shadow validation, locks, and deployment semantics;
- `source_control`: repository metadata, commits, merge requests, webhooks, and status checks;
- `ci`: identity exchange, artifact handoff, approvals, and job status;
- `migration`: graph inspection, planning, execution, and result reporting.

## 3. Manifest contract

Every provider declares:

- a stable lowercase identifier and provider kind;
- display name and adapter version;
- lifecycle status: `available`, `preview`, or `planned`;
- currently implemented capabilities;
- planned capabilities that callers must not invoke yet;
- aliases used only during configuration resolution.

Unknown capabilities are preserved so third-party providers can extend DBM without a core release.

## 4. Extension contract

Python packages can publish a provider through the `dbm.providers.v1` entry-point group. DBM validates manifests, rejects duplicate identifiers and aliases, and never silently replaces a built-in provider.

Provider execution remains behind DBM's security boundaries. Installing a provider is an administrator action; repository users cannot cause arbitrary packages to be installed.

## 5. Initial catalog

The built-in catalog describes:

- databases: PostgreSQL, MySQL, MariaDB, SQLite, Microsoft SQL Server, and Oracle;
- source control: local Git, GitHub, GitLab, Bitbucket, and Gitea;
- CI: GitHub Actions, GitLab CI/CD, Jenkins, CircleCI, Buildkite, and generic CI;
- migration engines: Alembic.

Only capabilities marked `available` may be used. PostgreSQL, local Git, and Alembic begin as the reference adapters. GitHub/GitLab and other databases move from `planned` to `preview` or `available` as their acceptance suites pass.

## 6. Functional requirements

### REQ-PROVIDER-001: discoverable catalog

The HTTP API, CLI, and MCP server expose the same provider catalog and allow filtering by kind.

### REQ-PROVIDER-002: alias resolution

Configuration can resolve common aliases such as `postgres`, `mariadb`, `mssql`, `github-actions`, and `gitlab-ci` to a canonical provider ID.

### REQ-PROVIDER-003: no capability guessing

Calling code must check a provider capability. A planned provider or missing capability produces a stable, machine-readable error rather than attempting a best-effort operation.

### REQ-PROVIDER-004: third-party registration

An installed Python package can register a validated provider manifest through `dbm.providers.v1` without modifying DBM core.

### REQ-PROVIDER-005: dialect-aware behavior

Database providers own dialect-specific quoting, catalog queries, read-only enforcement, locks, shadow lifecycle, and transactional-DDL behavior. DBM core does not pretend those semantics are universal.

### REQ-PROVIDER-006: host-neutral repository identity

The DBM domain stores source-control provider ID, host, namespace, repository name, and provider-native ID separately. GitHub installation IDs and GitLab project IDs remain provider data.

## 7. Acceptance scenarios

### AC-PROVIDER-001: catalog consistency

The API, CLI, and MCP surfaces return canonical provider IDs and the same lifecycle/capability information.

### AC-PROVIDER-002: honest GitLab state

Before the GitLab adapter is implemented, DBM reports it as planned and rejects GitLab-only operations with `provider_unavailable`.

### AC-PROVIDER-003: duplicate plugin

An entry-point plugin that attempts to replace `postgresql` or reuse one of its aliases is rejected.

### AC-PROVIDER-004: future database

A third-party CockroachDB provider can register its own manifest and capabilities without changing the intent protocol or conflict engine.

## 8. Compatibility policy

- Provider manifest schema `1` follows semantic versioning.
- Removing or renaming a capability requires a major manifest version.
- Provider-specific fields live in namespaced configuration objects.
- The public catalog never treats `planned` as usable.
- Each provider needs its own integration test matrix before being marked `available`.

