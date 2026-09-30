# Specification 0003: Read-only schema verification

Status: Proposed

Date: 30 September 2026

Target branch: `feat/schema-verification`, after specification 0001 is merged

## 1. Purpose

Allow DBM to inspect the actual PostgreSQL schema and Alembic revision of configured environments without granting permission to alter those databases. Compare observed state with accepted Git history and candidate migration assumptions.

Read-only inspection reduces uncertainty but cannot guarantee that a later deployment will have no conflict. DBM reports which checks ran, the schema fingerprint they used, and when the observation occurred.

## 2. Verification model

```text
Real environment, read-only
    observe catalog, constraints, and alembic_version
                    |
                    v
Intent precondition verification
    confirm referenced objects and expected before-state
                    |
                    v
Disposable shadow PostgreSQL
    reconstruct schema and apply candidate migration
                    |
                    v
Result comparison
    expected schema vs generated schema
```

The real environment is never used as the shadow database.

## 3. Functional requirements

### REQ-ENV-001: environment configuration

A project administrator can configure named PostgreSQL environments such as development, staging, and production. API responses expose connection metadata but never return passwords or complete connection strings.

### REQ-ENV-002: secret storage

The coordinator stores either an external secret reference or an encrypted connection secret. Local encryption requires a rotatable master key provided outside the application database.

### REQ-ENV-003: connection validation

DBM tests DNS, TCP, TLS, authentication, PostgreSQL version, database identity, and catalog-read access. It rejects a connection when the DBM session cannot enforce read-only transactions.

### REQ-INSPECT-001: catalog inspection

DBM reads PostgreSQL catalogs to capture schemas, tables, columns, defaults, generated expressions, nullability, constraints, indexes, enum and domain types, and the configured Alembic version table.

### REQ-INSPECT-002: schema fingerprint

DBM normalizes the observed catalog and computes a deterministic SHA-256 fingerprint. Every result records the fingerprint, environment, database identity, PostgreSQL version, and observation time.

### REQ-DRIFT-001: drift comparison

DBM compares the environment's Alembic revision and schema fingerprint with accepted repository state. It reports behind, ahead, divergent, and unknown states separately.

### REQ-VERIFY-001: intent preconditions

Before approval or finalization, DBM verifies that every referenced object exists and matches declared `before` values. Missing or mismatched objects produce stable finding codes.

### REQ-VERIFY-002: time-of-check protection

A verified result expires. Finalization must recheck when the observed fingerprint changes or the configured verification window has elapsed.

### REQ-SHADOW-001: disposable migration validation

DBM creates an isolated PostgreSQL shadow database, reconstructs the accepted schema, applies the candidate Alembic migration, and captures the resulting schema fingerprint. DBM destroys the shadow database after the run.

### REQ-SHADOW-002: real data limitations

When a constraint depends on existing data, schema-only validation reports that data compatibility remains unverified. A later sanitized-clone mode may validate those constraints using representative data.

## 4. Security requirements

- Force read-only transactions for every real-environment inspection.
- Recommend and verify a dedicated PostgreSQL role with catalog and table read access only.
- Never send connection secrets to MCP clients, coding agents, logs, traces, or audit payloads.
- Block private-network destinations unless the deployment administrator explicitly allows the network range.
- Prevent DNS rebinding and other server-side request forgery during connection tests.
- Set short connection, statement, and lock timeouts.
- Cap catalog result sizes and cancel abandoned inspections.
- Run shadow databases on an isolated network with no route to real environments.

## 5. Verification outcomes

- `verified`: selected deterministic checks passed against the recorded fingerprint.
- `drifted`: repository and environment state differ.
- `precondition_failed`: the candidate assumes an object state that does not exist.
- `shadow_failed`: the migration did not apply to the disposable database.
- `partially_verified`: schema checks passed, but data-dependent behavior was not proven.
- `unavailable`: the environment could not be inspected safely.

## 6. Acceptance scenarios

### AC-ENV-001: secret redaction

After configuring an environment, no API, MCP, log, or audit response contains its password or complete connection string.

### AC-ENV-002: read-only enforcement

A connection test proves the inspection transaction is read-only before DBM reads schema metadata.

### AC-VERIFY-001: renamed environment column

Given an intent that alters `users.name` and an observed schema containing only `users.full_name`, verification returns `precondition_failed` with the missing identity and observed rename context when available.

### AC-SHADOW-001: invalid candidate

Given a migration that references a missing column, applying it to the disposable shadow database fails without modifying the real environment.

### AC-DRIFT-001: environment behind Git

Given accepted Git head `m12` and environment revision `m10`, DBM reports `behind` and does not describe the environment as migration-ready.

## 7. Explicitly deferred

- application writes through inspection credentials;
- storing production data in DBM;
- automatic repair of schema drift;
- long-lived database tunnels managed by DBM;
- database engines other than PostgreSQL.

