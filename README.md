# DBM

DBM coordinates database migration intent before migration files are finalized.

Developers and coding agents submit structured schema changes to a shared coordinator. DBM compares those changes with the accepted migration graph and other active work, then reports safe changes, stale bases, dependencies, and deterministic conflicts.

DBM is the migration control plane. It coordinates intent, verifies real schema state, authorizes deployment, and invokes Alembic inside an isolated runner. Git remains the source of accepted migration history; operators and CI do not invoke Alembic against shared environments directly.

## Project status

DBM is an early open-source MVP under active development. The first supported stack is PostgreSQL, SQLAlchemy, Alembic, Git, FastAPI, and MCP.

## Core rule

```text
AI reasons.
DBM verifies.
Developer approves.
DBM authorizes and orchestrates.
Alembic executes inside the DBM runner.
```

## Run the complete stack

The default Docker image runs the MCP server as a non-root user over Streamable HTTP. Docker Compose starts PostgreSQL, the coordinator API, and the MCP server:

```bash
export DBM_API_TOKEN=dev-token
docker compose up --build
```

Services:

- Coordinator API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- MCP endpoint: `http://localhost:8001/mcp`
- MCP health: `http://localhost:8001/health`

The tagged-image workflow publishes releases to GitHub Container Registry.

## Local CLI

Install the project and inspect the available commands:

```bash
uv sync --extra dev
uv run dbm --help
```

After creating a project through the API, connect a repository:

```bash
uv run dbm init \
  --project-id PROJECT_UUID \
  --server http://localhost:8000 \
  --alembic-config alembic.ini

uv run dbm inspect
uv run dbm submit examples/intents/rename-name.json
```

Set `api_token` in `.dbm.toml` when the coordinator requires authentication. This local file is ignored by Git.

## Architecture

```text
Coding agent or CLI
        |
        | structured intent
        v
MCP server container --------> Coordinator API
                                    |
                                    v
                              PostgreSQL metadata

Git default branch: accepted migration history
DBM coordinator: proposed migration work
Alembic: execution engine inside the DBM runner
```

The MCP server never receives application database credentials. Read-only inspection and CI-controlled migration execution use separate credentials and isolated services in follow-on specifications 0003 and 0004.

## Agent integration

The project skill at `.cursor/skills/dbm-migrations/SKILL.md` teaches compatible coding agents to submit and check intent before generating migrations, require developer approval for semantic changes, and acquire a finalization lease.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run dbm-api
```

The coordinator uses `sqlite:///./dbm.db` by default for local development. Copy `.env.example` and set `DBM_DATABASE_URL` to use PostgreSQL.

See the [MVP specification](docs/specs/0001-mvp.md), [implementation plan](PLAN.md), and [roadmap](ROADMAP.md). Follow-on designs cover the [GitHub App and setup console](docs/specs/0002-github-app-console.md), [read-only schema verification](docs/specs/0003-schema-verification.md), and [CI-controlled deployment runner](docs/specs/0004-ci-deployment-runner.md).

## License

Apache-2.0
