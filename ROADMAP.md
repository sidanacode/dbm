# DBM roadmap

## 0.1: coordination core

- Versioned intent protocol
- Deterministic conflict and dependency engine
- FastAPI coordinator with PostgreSQL metadata
- Git and Alembic inspection CLI
- Containerized MCP server
- Finalization leases and audit events
- Portable DBM Agent Skill

## 0.2: GitHub App and setup console

- GitHub App installation flow
- Repository and default-branch configuration
- Verified webhooks for pull requests and default-branch pushes
- Accepted migration-state synchronization
- Project, intent, conflict, and lease views
- Optional pull-request status check

See [specification 0002](docs/specs/0002-github-app-console.md).

## 0.3: read-only schema verification

- Encrypted PostgreSQL connection configuration
- External secret references
- Connection tests with network safeguards
- Schema and Alembic revision inspection
- Drift reporting across development, staging, and production
- Intent precondition checks against observed schemas
- Disposable shadow PostgreSQL validation

See [specification 0003](docs/specs/0003-schema-verification.md).

## 0.4: CI migration deployment

- Signed migration artifacts tied to an accepted Git SHA
- Environment approval policies and deployment locks
- One-shot Alembic runner controlled by DBM
- Short-lived migration credentials separate from inspection credentials
- Post-deployment schema verification and immutable receipts
- GitHub checks for plan, verification, and deployment status

See [specification 0004](docs/specs/0004-ci-deployment-runner.md).

## Later

- Advanced deployment-safety linting
- Expand and contract migration plans
- Additional migration frameworks
- Additional database engines
- GitLab and Bitbucket integrations
