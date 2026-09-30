# Security policy

## Supported versions

DBM is pre-release software. Security fixes are applied to the latest release and the `main` branch.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting feature in the repository Security tab. Include reproduction steps, affected versions, and the expected impact when possible.

The maintainers will acknowledge a complete report within seven days and coordinate disclosure after a fix is available.

## Security model

The MVP uses an optional shared bearer token. Deploy the coordinator and MCP server behind TLS and a trusted network boundary. DBM does not require application database credentials and does not execute application migrations.

