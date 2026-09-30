# Contributing to DBM

Thank you for helping improve DBM.

## Development workflow

1. Open an issue for significant behavior changes.
2. Create a topic branch from `main`, such as `feat/conflict-rule` or `fix/lease-expiry`.
3. Install the project with `uv sync --extra dev`.
4. Add or update tests that reference the relevant requirement in `docs/specs`.
5. Run `uv run ruff check .`, `uv run mypy`, and `uv run pytest`.
6. Open a focused pull request against `main`.

Do not commit secrets, database credentials, generated virtual environments, or local `.dbm.toml` files.

## Design expectations

- Keep the conflict engine deterministic and independent of LLM services.
- Preserve Git as the authority for accepted migration history.
- Prefer stable machine-readable error and finding codes.
- Add an architecture decision record for choices that change a project invariant.
- Maintain backward compatibility within a published intent protocol version.

## Commit messages

Use concise imperative messages. Conventional prefixes such as `feat:`, `fix:`, `docs:`, and `test:` are encouraged.

