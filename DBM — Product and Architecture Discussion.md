# DBM — Product and Architecture Discussion

Date: 30 September 2026

Status: Discussion draft. This is deliberately not the implementation plan yet.

## Verdict

DBM is worth building.

The strongest version of the idea is not “another database migration tool” and not “AI that writes migrations.” It is:

> A shared, pre-merge coordination protocol for schema-change intent.

That is a real and narrow problem. Alembic knows how to represent migration branches and merge them, but it does not coordinate what developers on separate feature branches intend to change before their migration files are merged. Alembic explicitly treats migration history as a DAG and supports merge revisions; DBM should complement that behavior rather than pretend the DAG does not exist. See [Alembic: Working with Branches](https://alembic.sqlalchemy.org/en/latest/branches.html).

The core product loop is compelling:

```text
Developer changes a model
        ↓
Agent derives a structured schema intent
        ↓
DBM compares it with accepted history and active intents
        ↓
DBM returns safe, stale, dependent, or conflicting
        ↓
Agent explains; developer approves any semantic reinterpretation
        ↓
Migration is generated and validated against the latest accepted head
```

The sentence I would use to position it is:

> DBM catches cross-branch schema conflicts before migration files are created.

## What is already strong

- Alembic remains the migration engine.
- The coordinator does not require an LLM.
- Deterministic checks remain deterministic.
- The developer's existing coding agent handles explanation and semantic reasoning.
- Semantic reinterpretations require human approval.
- PostgreSQL, SQLAlchemy, and Alembic form a sensible first vertical.
- The proposed three-developer demo proves the central value without needing a dashboard or production deployment.

The safety principle is excellent and should remain prominent:

```text
AI reasons.
DBM verifies.
Developer approves.
Alembic executes.
```

## The most important architectural correction

DBM should serialize coordination, not prematurely assign permanent Alembic revisions.

The original example reserves this sequence:

```text
41 → 42 → 43
```

That is easy to understand, but Git merge order can change. A pull request expected to become `42` may be delayed while another is merged first. A reservation can also be abandoned, expire, or be regenerated after a rebase. Alembic revision identifiers are not naturally a globally allocated integer sequence either.

A safer model is:

1. An intent is submitted against an exact base consisting of:
   - the Git commit SHA;
   - the current Alembic heads;
   - a digest of the migration graph;
   - optionally, a digest of the inferred schema.
2. DBM checks the intent against:
   - changes accepted since that base;
   - active intents that overlap or create dependencies.
3. DBM may grant a short-lived finalization lease.
4. Before generating the migration, the client refreshes the default branch.
5. The final migration ID and `down_revision` are created from the actual, current graph.
6. The pull request and eventual merge determine accepted order.

This gives DBM optimistic concurrency control without making the coordinator compete with Git.

## Make the sources of truth hierarchical

The proposal currently describes Git, DBM, and the database as three sources of truth. They contain three kinds of truth, but they should not have equal authority.

The hierarchy should be:

```text
Git default branch
    Accepted migration history

DBM coordinator
    Proposed and in-flight schema work

Connected database
    Observed deployed state and drift
```

The central invariant should be:

> A migration becomes accepted only when it is merged into the configured default branch. Until then, its DBM record is advisory coordination state.

This prevents DBM from claiming that an abandoned reservation or closed pull request changed canonical history.

## Conflict detection needs a taxonomy

Returning only `SAFE` or `CONFLICT` will become limiting quickly. V1 should distinguish at least four outcomes.

### 1. Structural conflict

Two operations cannot both be applied as written.

Examples:

```text
ADD users.phone
ADD users.phone
```

```text
DROP users.name
ALTER users.name
```

### 2. Stale base

The request was created from an old migration graph, but may still be valid after refreshing.

Example:

```text
Intent base: revision A
Accepted head: revision C
No touched objects overlap
```

This is not automatically a conflict.

### 3. Dependency or ordering requirement

Both intents are valid, but one must happen before the other.

Example:

```text
CREATE organizations
ADD users.organization_id REFERENCES organizations.id
```

### 4. Deployment-safety hazard

The schema operations are structurally compatible but unsafe in one deployment step.

Example:

```text
ADD users.organization_id NOT NULL
```

on a populated table may require expand, backfill, and contract phases.

This last category is valuable, but it should follow the core coordination proof rather than be mixed into the first conflict engine. Tools such as [Atlas migration lint](https://atlasgo.io/versioned/lint) already focus heavily on migration safety and CI analysis. DBM's differentiated wedge is cross-branch, pre-generation coordination.

## The intent format is the product contract

The JSON operation model will become more important than the REST endpoints. It should be explicit enough for deterministic comparison and portable enough for future adapters.

At minimum, an intent should include:

```json
{
  "project_id": "...",
  "source": {
    "branch": "feature/profile",
    "commit_sha": "abc123",
    "migration_heads": ["41"],
    "migration_graph_digest": "sha256:..."
  },
  "operations": [
    {
      "kind": "add_column",
      "object": {
        "schema": "public",
        "table": "users",
        "column": "phone"
      },
      "after": {
        "type": "varchar",
        "nullable": true
      }
    }
  ]
}
```

The format will also need to express:

- before and after values for alterations;
- old and new identities for renames;
- schemas, quoted identifiers, and naming conventions;
- constraint and index columns, predicates, methods, and referenced objects;
- dependencies between operations;
- whether an operation was inferred or explicitly confirmed;
- provenance: model diff, migration diff, manual input, or agent submission.

I recommend versioning this protocol from the beginning, for example `intent_schema_version: 1`.

## The coordinator should not generate migrations in the first proof

For the first complete demo, ownership should be:

```text
Local adapter
    Reads Git, Alembic, and SQLAlchemy state
    Derives intent
    Generates the migration with Alembic
    Validates the result

Shared coordinator
    Stores intents
    Detects overlap, staleness, and dependencies
    Grants short-lived finalization leases
    Records lifecycle and audit events
```

Keeping generation local avoids sending repository code to the coordinator and preserves the developer's normal Alembic environment, imports, metadata configuration, and custom migration hooks.

## Database connections should be deferred

Read-only database inspection is useful, but it is not required to prove the idea. It introduces significant work immediately:

- secret storage and rotation;
- network access and private connectivity;
- PostgreSQL permissions;
- tenancy and isolation;
- audit requirements;
- differences between repository history and deployed environments.

The first proof can use Git and Alembic state only. A later read-only environment adapter can add drift reporting and deployment awareness.

This keeps DBM distinct from broader database-governance platforms such as [Bytebase](https://www.bytebase.com/database-change-management/), which already covers review, policy, GitOps, deployment, and rollback across many databases.

## Adoption is the largest product risk

The conflict engine only works when the registry knows about relevant changes. If developers or agents can generate migrations without submitting an intent, DBM's shared state becomes incomplete.

The adoption path should therefore have three layers:

1. An Agent Skill teaches supported coding agents the intended workflow.
2. A local CLI makes the workflow usable without an agent.
3. A CI check detects migration files that lack a DBM intent reference or were generated from a stale graph.

MCP is an integration surface, not the enforcement mechanism. CI is what makes the protocol trustworthy for a team.

## Recommended proof of concept

The first end-to-end proof should contain only:

- one FastAPI coordinator;
- one PostgreSQL metadata database;
- one Python CLI;
- one Alembic graph adapter;
- one versioned intent schema;
- one deterministic conflict engine;
- one MCP server exposing the same application service layer;
- one sample SQLAlchemy/Alembic repository;
- one CI command that verifies intent provenance.

The demonstration should prove these cases:

```text
A: ADD users.phone
Result: safe

B: RENAME users.name TO users.full_name
Result: safe

C: ALTER users.name TYPE varchar(300)
Result: structural conflict with B and a rename hint

D: ADD users.timezone from an older, non-overlapping base
Result: stale but rebasable, not a semantic conflict

E: ADD users.organization_id FK
Result: depends on CREATE organizations
```

## What should remain out of the initial build

- production migration execution;
- production database credentials;
- dashboard UI;
- GitHub App installation;
- automatic PR mutation;
- multiple migration frameworks;
- multi-database support;
- hosted SaaS and billing;
- complex RBAC;
- autonomous approval of destructive changes;
- automatic AI-based rename decisions.

## Open-source direction

My default recommendation is:

- License: Apache-2.0, which is permissive and includes an explicit patent grant.
- Structure: a monorepo containing coordinator, CLI, MCP server, adapters, protocol models, tests, docs, and an example project.
- Governance initially: maintainer-led with a public roadmap, contribution guide, security policy, code of conduct, and architecture decision records.
- Packaging: Python packages first, with Docker Compose for the coordinator demo.
- Name: keep DBM as the working name, but perform a naming and package-availability check before publishing. “DBM” is broad and may be difficult to search for.

## Decisions to settle before the build plan

I recommend the following defaults:

1. Primary user: Python backend teams with roughly 5–50 developers and frequent Alembic migrations.
2. Canonical history: the default Git branch.
3. Product mode: self-hosted open-source coordinator plus local CLI/MCP integrations.
4. V1 enforcement: advisory locally, mandatory in CI for participating repositories.
5. V1 database access: none.
6. V1 merge behavior: DBM reports and guides; it does not push, merge, or rewrite branches.
7. License: Apache-2.0.

The most important question for our discussion is:

> Do you want DBM's first users to adopt it as a lightweight developer tool that prevents Alembic conflicts, or as the beginning of a broader database change-management platform?

I strongly recommend the first. It gives the project a crisp reason to exist, a realistic first release, and a clean boundary from existing governance and migration-safety products.
