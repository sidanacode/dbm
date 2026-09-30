# DBM implementation plan

This plan implements [MVP specification 0001](docs/specs/0001-mvp.md). Requirement IDs in commits and tests refer to that document.

## Phase 0: repository foundation

- [x] Record the product and architecture discussion.
- [x] Create a versioned MVP specification with acceptance criteria.
- [x] Initialize a Python monorepo and local Git repository.
- [x] Add contributor, security, license, and CI files.

## Phase 1: protocol and conflict engine

- [x] Implement the versioned intent schema.
- [x] Normalize database object identities.
- [x] Detect duplicate additions, drops against modifications, concurrent alterations, and rename conflicts.
- [x] Detect dependencies on tables proposed by another intent.
- [x] Test every required operation and conflict category.

Exit criterion: the three-developer conflict scenario runs entirely as a pure unit test.

## Phase 2: coordinator service

- [x] Implement SQLAlchemy persistence for projects, intents, operations, checks, leases, and audit events.
- [x] Implement the application service layer.
- [x] Expose the FastAPI endpoints in the specification.
- [x] Add optional bearer-token authentication.
- [x] Test the HTTP lifecycle using an isolated database.

Exit criterion: a client can create a project, submit intents, check them, approve a safe intent, and acquire a finalization lease.

## Phase 3: local developer workflow

- [x] Read `.dbm.toml` configuration.
- [x] Inspect Git branch and commit metadata.
- [x] Inspect Alembic heads and calculate a stable graph digest.
- [x] Implement CLI commands for project state and intent lifecycle.
- [x] Add JSON output for coding-agent use.

Exit criterion: the example repository can submit and check an intent from the terminal.

## Phase 4: MCP interface

- [x] Expose structured project, intent, conflict, approval, and lease tools.
- [x] Use the same coordinator HTTP API as the CLI.
- [x] Package the MCP server as a Docker image using Streamable HTTP.
- [x] Add an MCP smoke test.

Exit criterion: an MCP client can reproduce the three-developer demo.

## Phase 5: open-source delivery

- [x] Add Dockerfile and Docker Compose development environment.
- [x] Add a GitHub Container Registry publishing workflow for tagged releases.
- [x] Add GitHub Actions for lint, type checking, and tests.
- [x] Add example intent payloads and a documented demo.
- [x] Complete contributor documentation and the portable Agent Skill.
- [x] Create the public GitHub repository and push `main`.

Exit criterion: a new contributor can clone the repository and run the demo from the README.

## Follow-on specifications

- [ ] Specification 0002: GitHub App and setup console on `feat/github-app-console`.
- [ ] Specification 0003: read-only schema verification and shadow validation on `feat/schema-verification`.
- [ ] Specification 0004: CI-controlled migration deployment on `feat/deployment-runner`.
