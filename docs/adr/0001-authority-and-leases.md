# ADR 0001: Git authority and finalization leases

Status: Accepted

## Context

Feature branches can produce concurrent migration files from the same Alembic head. A coordinator can see active work, but it cannot predict Git merge order or guarantee that a reserved revision will merge.

## Decision

The configured default Git branch is the authority for accepted migration history. DBM stores proposed intent and grants expiring finalization leases. A lease serializes the act of refreshing the accepted graph and generating a final migration; it does not allocate a permanent revision identifier.

## Consequences

- Abandoned branches cannot create permanent holes in a revision sequence.
- The coordinator never competes with Git for canonical order.
- Clients must refresh project state before finalization.
- Teams may still choose Alembic merge revisions when their Git workflow requires them.

