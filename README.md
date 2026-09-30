# DBM

DBM coordinates database migration intent before migration files are finalized.

Developers and coding agents submit structured schema changes to a shared coordinator. DBM compares those changes with the accepted migration graph and other active work, then reports safe changes, stale bases, dependencies, and deterministic conflicts.

DBM complements Alembic. Alembic still generates and executes migrations. Git remains the source of accepted migration history.

## Project status

DBM is an early open-source MVP under active development. The first supported stack is PostgreSQL, SQLAlchemy, Alembic, Git, FastAPI, and MCP.

## Core rule

```text
AI reasons.
DBM verifies.
Developer approves.
Alembic executes.
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run dbm-api
```

The coordinator uses `sqlite:///./dbm.db` by default for local development. Copy `.env.example` and set `DBM_DATABASE_URL` to use PostgreSQL.

See [the MVP specification](docs/specs/0001-mvp.md) and [implementation plan](PLAN.md).

## License

Apache-2.0

