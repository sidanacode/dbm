# DBM — AI-Assisted Database Migration Coordinator

## 1. Idea

**DBM** is a coordination layer on top of database migration tools such as Alembic.

Its purpose is to solve a problem that appears when multiple developers work on different feature branches and independently create database migrations.

Instead of every developer generating migrations in isolation, DBM maintains a shared view of:

- the current accepted migration head
- pending migration intents from all developers
- the actual database schema
- migrations that have been approved, merged, rejected, or abandoned
- conflicts between concurrent schema changes

DBM does **not replace Alembic**.

Alembic remains responsible for creating and executing migrations.

DBM coordinates **what should become a migration and in what order**.

---

# 2. Core Problem

Assume the current Alembic head is:

```text
M10
```

Developer A creates:

```text
M10 → M11_A
ADD users.phone
```

Developer B independently creates:

```text
M10 → M11_B
RENAME users.name → users.full_name
```

This creates:

```text
        M11_A
       /
M10
       \
        M11_B
```

Alembic supports this migration DAG, but developers now have to resolve the migration history themselves.

The problem becomes more difficult when migrations are semantically related.

Example:

```text
Developer A:
RENAME users.name → users.full_name

Developer B:
ALTER users.name VARCHAR(100) → VARCHAR(300)
```

Both migrations can be valid independently, but they conflict logically.

DBM exists to coordinate these changes **before they become conflicting migration files**.

---

# 3. Core Principle

Developers should submit their **database change intent** to DBM before creating the final migration.

```text
Developer changes code
        ↓
Coding assistant detects schema change
        ↓
Submit intent to DBM
        ↓
DBM checks team-wide migration state
        ↓
Safe / stale / conflict
        ↓
Developer verifies proposed solution
        ↓
Alembic migration generated
```

DBM serializes migration history while allowing developers to continue working concurrently.

---

# 4. User Experience

The developer should continue using their existing coding assistant:

- Codex
- Cursor
- Claude Code
- other MCP-compatible coding agents

The user should not need a separate AI account or API key specifically for DBM.

Example:

```text
Developer:
Add a phone field to User.
```

The coding agent modifies:

```python
class User(Base):
    ...

    phone: Mapped[str | None]
```

Before creating an Alembic migration, the agent calls DBM.

DBM checks:

```text
Current head: 41

Pending requests:
#100 ADD orders.reference
#101 ADD users.avatar_url
```

The new request:

```text
ADD users.phone
```

does not conflict.

DBM responds:

```text
SAFE

Base revision: 41
No conflicting migration intents.
```

The coding assistant tells the user:

```text
DBM checked the schema change.

+ users.phone VARCHAR(...)

No migration conflicts were found.

Generate the Alembic migration?
```

The developer approves.

DBM reserves the migration sequence and creates/validates the migration.

---

# 5. Conflict Example

Suppose another developer already submitted:

```text
RENAME users.name → users.full_name
```

A developer working on an older branch submits:

```text
ALTER users.name VARCHAR(100) → VARCHAR(300)
```

DBM responds:

```text
CONFLICT

Referenced object:
users.name

Pending migration:
users.name → users.full_name
```

The developer's coding assistant can inspect:

- DBM conflict information
- the local Git diff
- SQLAlchemy models
- application code
- tests

The AI may conclude:

```text
Your feature appears to modify the same logical field.

The field has been renamed from:

users.name

to:

users.full_name

I propose rebasing your change to:

ALTER users.full_name VARCHAR(300)
```

The developer must approve this semantic interpretation.

After approval:

```text
M41
 ↓
M42 rename name → full_name
 ↓
M43 alter full_name → VARCHAR(300)
```

---

# 6. Architecture

```text
                     Developer
                         │
                         ▼
              Coding Assistant
         Codex / Cursor / Claude
                         │
                       MCP
                         │
                         ▼
                DBM MCP Client
                         │
                         ▼
              DBM Coordinator API
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             ▼             ▼
       PostgreSQL      Alembic       Database
      DBM metadata     history       inspection
           │
           ▼
       Git metadata
```

---

# 7. Major Components

## 7.1 DBM Coordinator

A shared server deployed for the team.

Suggested V1 stack:

```text
FastAPI
PostgreSQL
SQLAlchemy
Pydantic
```

Responsibilities:

- projects
- environments
- migration requests
- current authoritative head
- pending intents
- conflict detection
- migration reservations
- request lifecycle
- authentication

The coordinator itself does **not require an LLM**.

---

# 8. AI Architecture

DBM should not depend on OpenAI, Anthropic, or another LLM API.

Instead:

```text
Codex
Cursor
Claude
   │
   │ reasoning
   ▼
DBM MCP tools
```

The developer's own coding assistant provides intelligence.

DBM provides structured facts and safe operations.

---

# 9. Responsibilities

## Deterministic DBM Logic

DBM should handle these without AI:

```text
current revision
migration graph
pending requests
stale base detection
revision reservation
schema diff
table/column overlap
constraint overlap
migration validation
locking
request lifecycle
```

Example:

```python
if request.base_revision != current_head:
    request_is_stale = True
```

No AI is needed.

---

## AI Responsibilities

AI is used when understanding **developer intent** requires semantic reasoning.

Examples:

### Rename recognition

Mechanical diff:

```text
DROP first_name
ADD given_name
```

AI recognizes:

```text
first_name was probably renamed to given_name
```

Developer confirms.

---

### Semantic conflict

DBM reports:

```text
users.name no longer exists.

Migration #42 renamed:
users.name → users.full_name
```

AI determines whether the developer's change should now target:

```text
users.full_name
```

Developer confirms.

---

### Migration ordering

Requests:

```text
CREATE organizations

ADD users.organization_id

SET users.organization_id NOT NULL
```

AI can suggest:

```text
1. create organizations
2. add nullable FK
3. deploy/backfill application data
4. make FK NOT NULL
```

---

# 10. Safety Principle

The fundamental rule:

```text
AI reasons.
DBM verifies.
Developer approves.
Alembic executes.
```

AI should never be responsible for locking, revision ordering, schema truth, or migration correctness.

---

# 11. DBM Project

A team creates:

```text
Project:
Grofii

Repository:
github.com/team/grofii

Migration framework:
Alembic

Current accepted revision:
41
```

Then connects environments.

Example:

```text
Development
Staging
Production
```

---

# 12. Database Connections

DB connections belong to the **DBM project**, not individual developers.

```text
Coding assistant
      │
      ▼
DBM
      │
 encrypted credentials
      │
      ▼
Database
```

The coding assistant never receives the database password.

DBM exposes operations such as:

```text
inspect_schema
get_database_revision
check_schema_drift
validate_migration
```

For V1, attached databases should preferably be **read-only**.

DBM can inspect:

```text
tables
columns
types
indexes
constraints
foreign keys
alembic_version
```

but should not directly alter production.

---

# 13. Three Sources of Truth

DBM combines three different kinds of information.

## Git / Alembic truth

```text
What migrations exist?
```

## DBM truth

```text
What migrations are developers currently planning?
```

## Database truth

```text
What actually exists in this database?
```

Example:

```text
Git Alembic head:
52

Staging alembic_version:
50
```

DBM can report:

```text
Staging is two migrations behind repository head.
```

---

# 14. Migration Intent

Instead of immediately generating an Alembic file, DBM stores a structured intent.

Example:

```json
{
  "project": "grofii",
  "branch": "feature/profile",
  "commit": "abc123",
  "base_revision": "41",
  "operations": [
    {
      "type": "add_column",
      "table": "users",
      "column": "phone",
      "nullable": true
    }
  ]
}
```

This becomes the fundamental DBM object.

---

# 15. Request Lifecycle

Suggested lifecycle:

```text
DRAFT
  ↓
SUBMITTED
  ↓
CHECKING
  ↓
SAFE / CONFLICT
  ↓
APPROVED
  ↓
RESERVED
  ↓
GENERATED
  ↓
MERGED
```

Additional terminal states:

```text
REJECTED
CANCELLED
SUPERSEDED
```

---

# 16. Migration Serialization

Suppose:

```text
Current head = 41
```

Developer A submits:

```text
ADD users.phone
```

DBM reserves:

```text
41 → 42
```

Developer B submitted from revision 41 as well.

Instead of allowing:

```text
        42_A
       /
41
       \
        42_B
```

DBM rebases B against the new authoritative sequence:

```text
41
 ↓
42 A
 ↓
43 B
```

This is effectively optimistic concurrency control for migrations.

---

# 17. DBM and Git

DBM should **not continuously clone and inspect every remote branch**.

Instead, each developer's local DBM integration extracts their intent and submits it.

```text
local branch
    ↓
local DBM/MCP
    ↓
structured intent
    ↓
shared coordinator
```

Git is useful for:

```text
branch identity
commit SHA
local diff
eventual PR/merge lifecycle
```

Later GitHub/GitLab integrations can automatically detect:

```text
PR merged
PR closed
branch deleted
```

and update DBM request status.

---

# 18. MCP Interface

Potential tools:

```text
dbm.get_project_state

dbm.inspect_schema

dbm.get_current_head

dbm.submit_intent

dbm.check_intent

dbm.get_pending_intents

dbm.get_conflict_context

dbm.update_intent

dbm.approve_intent

dbm.reserve_revision

dbm.generate_migration

dbm.validate_migration

dbm.cancel_intent
```

The MCP API should expose structured operations rather than giant AI-oriented commands.

---

# 19. Agent Skill

Alongside MCP, DBM can provide an Agent Skill.

Its purpose is to teach coding assistants how DBM should be used.

Conceptual instructions:

```text
When SQLAlchemy models or Alembic migrations change:

1. Inspect DBM project state.
2. Determine the developer's schema intent.
3. Submit/check the intent with DBM.
4. Never generate an Alembic migration before checking DBM.
5. If DBM reports a deterministic conflict, explain it.
6. If semantic reasoning is required, inspect relevant repository code.
7. Propose a resolution.
8. Obtain developer approval for semantic reinterpretations.
9. Submit the resolved intent.
10. Allow DBM/Alembic to generate and validate the migration.
```

---

# 20. V1 Scope

Do not attempt everything initially.

V1 should support:

```text
PostgreSQL
SQLAlchemy
Alembic
Git
FastAPI coordinator
PostgreSQL coordinator database
MCP interface
```

Supported schema operations:

```text
ADD TABLE
ADD COLUMN
DROP COLUMN
ALTER COLUMN
RENAME COLUMN
ADD INDEX
DROP INDEX
ADD FOREIGN KEY
DROP FOREIGN KEY
```

---

# 21. V1 Conflict Detection

Start with deterministic conflict detection.

Examples:

```text
ADD same table/column
DROP object another request modifies
ALTER same column
RENAME object another request references
DROP table with pending table operations
conflicting FK operations
conflicting index operations
```

Return structured conflicts.

Example:

```json
{
  "status": "conflict",
  "type": "object_renamed",
  "object": "users.name",
  "related_request_id": 101,
  "new_object": "users.full_name"
}
```

The coding agent handles explanation and semantic reasoning.

---

# 22. Weekend MVP

## Phase 1 — Coordinator

Build:

```text
FastAPI application
PostgreSQL database
```

Models:

```text
Project
Environment
MigrationRequest
MigrationOperation
RevisionReservation
```

Endpoints:

```text
POST /projects

GET /projects/{id}/state

POST /projects/{id}/intents

GET /projects/{id}/intents

POST /intents/{id}/check

POST /intents/{id}/approve

POST /intents/{id}/cancel
```

---

## Phase 2 — Local CLI

Create:

```bash
dbm init
dbm status
dbm check
dbm submit
```

Configuration:

```text
.dbm.toml
```

Example:

```toml
project_id = "grofii"
server = "https://dbm.example.com"

[alembic]
config = "alembic.ini"
```

---

## Phase 3 — Alembic Inspection

Read:

```text
current head
heads
revision history
```

Convert Alembic migration changes into DBM operations.

---

## Phase 4 — Conflict Engine

Implement deterministic operation overlap.

Example:

```python
ADD users.phone
```

against:

```python
ADD users.avatar
```

Result:

```text
SAFE
```

But:

```python
ALTER users.name
```

against:

```python
RENAME users.name → users.full_name
```

Result:

```text
CONFLICT
```

---

## Phase 5 — MCP

Expose the coordinator through MCP.

Allow coding agents to call:

```text
get_project_state
submit_intent
check_intent
get_conflict
approve_intent
```

---

## Phase 6 — Agent Skill

Create:

```text
dbm/
└── SKILL.md
```

Test with one coding assistant first.

Once the protocol works, test portability with others.

---

# 23. Weekend Success Criteria

The MVP is successful if we can run this demo:

```text
Developer A
    ↓
submits:
ADD users.phone
    ↓
SAFE
```

Then:

```text
Developer B
    ↓
submits:
RENAME users.name → users.full_name
    ↓
SAFE
```

Then:

```text
Developer C
    ↓
submits:
ALTER users.name VARCHAR(300)
    ↓
CONFLICT
```

And DBM returns:

```text
users.name is affected by another pending migration.

Request #2:
users.name → users.full_name
```

The coding assistant then explains the conflict and proposes updating Developer C's intent.

If that entire flow works through MCP, we have proven the central idea.

---

# 24. What We Should NOT Build This Weekend

Avoid:

```text
production migration execution
multi-database support
Kubernetes
GitHub App
GitLab integration
complex RBAC
billing
dashboard UI
LLM API integration
automatic destructive migration approval
distributed worker architecture
```

They are distractions before the coordination model has been proven.

---

# 25. Long-Term Product

Eventually:

```text
                 DBM Cloud
                    │
      ┌─────────────┼─────────────┐
      │             │             │
    Codex         Cursor       Claude
      │             │             │
      └──────────── MCP ──────────┘
                    │
             Migration intents
                    │
        ┌───────────┴────────────┐
        │                        │
 migration coordination    DB environments
        │                        │
 Alembic / Flyway / etc    schema verification
```

Potential future migration frameworks:

```text
Alembic
Django migrations
Prisma
Drizzle
Flyway
Liquibase
Rails ActiveRecord
```

The core DBM protocol does not need to depend permanently on Alembic.

Alembic can simply be the first adapter.

---

# 26. Product Definition

DBM is:

> **A collaborative database migration coordinator that lets developers and coding agents submit schema-change intent, detects conflicts across concurrent feature work, serializes migration history, and uses the developer's existing AI coding assistant to resolve semantic conflicts safely.**

Shorter:

> **DBM is a traffic controller for database migrations.**

Core principle:

```text
Developers work concurrently.

Database evolution remains coordinated.
```