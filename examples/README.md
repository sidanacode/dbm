# Examples

The `intents` directory contains version 1 payloads for the core demo:

1. `add-phone.json` is an independent safe change.
2. `rename-name.json` renames `users.name` to `users.full_name`.
3. `widen-name.json` conflicts with the active rename because it still targets `users.name`.

Start the stack with `docker compose up --build`, create a project through `POST /v1/projects`, initialize `.dbm.toml` with its ID, and submit a payload with:

```bash
uv run dbm submit examples/intents/rename-name.json
```

