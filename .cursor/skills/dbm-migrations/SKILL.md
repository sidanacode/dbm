---
name: dbm-migrations
description: Coordinates SQLAlchemy and Alembic schema changes through DBM before migration files are generated. Use when editing database models, creating or changing Alembic migrations, resolving multiple heads, or handling schema changes on a Git feature branch.
---

# DBM migration workflow

Apply this workflow when a task changes a SQLAlchemy model or Alembic migration.

## Required sequence

1. Read `.dbm.toml` and inspect the local Git and Alembic state with `dbm inspect`.
2. Inspect the code change and express it as version 1 DBM operations.
3. Call the DBM MCP tool `get_project_state`.
4. Call `submit_intent` before generating an Alembic migration.
5. Call `check_intent` and handle its structured outcome.
6. Explain conflicts and dependencies using the related intent IDs and object identities DBM returns.
7. Ask the developer to approve any semantic reinterpretation, including rename mapping.
8. Call `approve_intent` only after explicit developer approval when interpretation is required.
9. Before final migration generation, refresh the default Git branch and accepted project state.
10. Call `acquire_finalization_lease`. Do not generate the migration if the lease fails.
11. Generate the migration with the repository's existing Alembic workflow.
12. Review the generated upgrade and downgrade operations. Run repository tests.
13. Call `release_finalization_lease` after generation and validation, including when generation fails.

## Outcome handling

### `safe`

The intent does not overlap accepted or active work. Continue to developer approval and finalization.

### `stale`

Refresh the default branch and inspect the Alembic graph again. Do not describe a stale result as a semantic conflict.

### `dependent`

Explain which active intent must land first. Keep the application work, but delay final migration generation until the dependency is accepted.

### `conflict`

Do not generate a migration. Inspect the related intent and local code, then propose a concrete resolution. The developer must approve changes that reinterpret their requested schema intent.

## Safety rules

- Treat Git's configured default branch as accepted migration history.
- Treat DBM records as proposed work until Git reports a merge.
- Never invent an accepted head or permanent revision number.
- Never bypass a failed or occupied finalization lease.
- Never expose database credentials to the coding agent.
- Never let AI approval substitute for developer approval.
- Never run `alembic upgrade` directly against a shared environment. Deployment goes through the DBM CI runner once the repository enables specification 0004.

## Version 1 operation names

Use only:

```text
add_table
drop_table
add_column
drop_column
alter_column
rename_column
add_index
drop_index
add_foreign_key
drop_foreign_key
```

Include schema and table names for every object. Include `column_name` for column operations and `object_name` for indexes and foreign keys. A rename requires `new_object`; adding a foreign key requires `references`.
