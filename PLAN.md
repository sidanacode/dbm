# DBM implementation plan

This plan implements [MVP specification 0001](docs/specs/0001-mvp.md). Requirement IDs in commits and tests refer to that document.

## Phase 0: repository foundation

- [x] Record the product and architecture discussion.
- [x] Create a versioned MVP specification with acceptance criteria.
- [x] Initialize a Python monorepo and local Git repository.
- [ ] Add contributor, security, license, and CI files.

## Phase 1: protocol and conflict engine

- [ ] Implement the versioned intent schema.
- [ ] Normalize database object identities.
- [ ] Detect duplicate additions, drops against modifications, concurrent alterations, and rename conflicts.
- [ ] Detect dependencies on tables proposed by another intent.
- [ ] Test every required operation and conflict category.

Exit criterion: the three-developer conflict scenario runs entirely as a pure unit test.

## Phase 2: coordinator service

- [ ] Implement SQLAlchemy persistence for projects, intents, operations, checks, leases, and audit events.
- [ ] Implement the application service layer.
- [ ] Expose the FastAPI endpoints in the specification.
- [ ] Add optional bearer-token authentication.
- [ ] Test the HTTP lifecycle using an isolated database.

Exit criterion: a client can create a project, submit intents, check them, approve a safe intent, and acquire a finalization lease.

## Phase 3: local developer workflow

- [ ] Read `.dbm.toml` configuration.
- [ ] Inspect Git branch and commit metadata.
- [ ] Inspect Alembic heads and calculate a stable graph digest.
- [ ] Implement CLI commands for project state and intent lifecycle.
- [ ] Add JSON output for coding-agent use.

Exit criterion: the example repository can submit and check an intent from the terminal.

## Phase 4: MCP interface

- [ ] Expose structured project, intent, conflict, approval, and lease tools.
- [ ] Use the same coordinator HTTP API as the CLI.
- [ ] Package the MCP server as a Docker image using Streamable HTTP.
- [ ] Add an MCP smoke test.

Exit criterion: an MCP client can reproduce the three-developer demo.

## Phase 5: open-source delivery

- [ ] Add Dockerfile and Docker Compose development environment.
- [ ] Add a GitHub Container Registry publishing workflow for tagged releases.
- [ ] Add GitHub Actions for lint, type checking, and tests.
- [ ] Add the sample project and scripted demo.
- [ ] Complete contributor documentation.
- [ ] Create the public GitHub repository and push `main`.

Exit criterion: a new contributor can clone the repository and run the demo from the README.
