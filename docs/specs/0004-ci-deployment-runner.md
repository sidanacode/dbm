# Specification 0004: CI-controlled migration deployment

Status: Proposed

Date: 30 September 2026

Target branch: `feat/deployment-runner`, after specifications 0002 and 0003

## 1. Purpose

Make DBM the only supported entry point for deploying application database migrations. DBM authorizes and orchestrates each deployment; Alembic executes migration code inside an isolated, one-shot DBM runner.

The always-on coordinator never holds production DDL credentials and never executes migration code in its own process.

## 2. CI workflow

### Pull request

1. The local agent or CLI submits intent.
2. DBM checks active work and accepted history.
3. CI sends the candidate migration artifact to DBM.
4. DBM verifies provenance, lints the migration, and applies it to a shadow database.
5. The GitHub App publishes a required check with structured findings.

### Merge and release

1. A default-branch push updates accepted migration state.
2. CI asks DBM to build an immutable migration artifact.
3. The artifact records repository, commit SHA, migration graph digest, package digest, and target heads.
4. DBM signs the artifact or stores it in an immutable trusted registry.

### Environment deployment

1. CI requests deployment of an exact artifact to an exact environment.
2. DBM evaluates environment policy and required approvals.
3. DBM acquires a coordinator deployment lock and the database provider's native lock.
4. DBM rechecks the real environment using read-only inspection.
5. A one-shot runner receives a short-lived migration credential.
6. The runner invokes Alembic for the approved target.
7. DBM verifies the final revision and schema fingerprint.
8. DBM writes an immutable deployment receipt and releases both locks.

## 3. Functional requirements

### REQ-ARTIFACT-001: immutable provenance

Every migration artifact is tied to an accepted Git commit, migration graph digest, target heads, and content digest. Deployment rejects modified or unaccepted artifacts.

### REQ-PLAN-001: explicit deployment plan

Before execution, DBM records the current environment revision, ordered revisions to apply, target revision, verification result, approvals, and expected post-deployment fingerprint.

### REQ-LOCK-001: environment serialization

Only one deployment can target an environment at a time. DBM uses both a coordinator lock and a database-provider lock to defend against multiple runners. When an engine has no safe native advisory lock, the provider must declare its alternative serialization guarantee before deployment can be enabled.

### REQ-CREDENTIAL-001: separate migration identity

Migration credentials are separate from read-only inspection credentials. They are issued or retrieved only for the one-shot runner and are never returned to agents, browsers, logs, or the coordinator API.

### REQ-RUNNER-001: isolated execution

The runner uses the application artifact's exact Python environment and Alembic configuration. It has no inbound network endpoint, accepts one signed job, emits structured events, and terminates after completion.

### REQ-VERIFY-001: post-deployment verification

A deployment succeeds only after the environment reports the target Alembic revision and the expected schema fingerprint or an explicitly approved equivalent fingerprint.

### REQ-RECEIPT-001: immutable receipt

Every attempt records artifact digest, environment, actor, approvals, start and finish times, applied revisions, verification fingerprints, runner identity, and final status.

### REQ-CI-001: required source-control checks

The source-control provider publishes separate plan and verification checks on pull requests or merge requests. Branch protection can require them before merge.

### REQ-CI-002: deployment command

CI uses `dbm deploy --artifact DIGEST --environment NAME`. Direct `alembic upgrade` is absent from official workflows and production migration credentials are unavailable outside the DBM runner.

### REQ-CI-003: check identity and invalidation

Every green check is bound to an exact source commit, accepted migration-graph digest, intent version, and observed schema fingerprint. A new default-branch merge or changed environment fingerprint invalidates results derived from the previous state.

### REQ-CI-004: merge-queue support

Source-control providers can check GitHub merge-queue and GitLab merge-train commits. DBM evaluates the combined candidate graph rather than assuming individually safe branches remain safe together.

### REQ-QUEUE-001: ordered environment queue

DBM may verify jobs concurrently but executes at most one migration job per environment. Artifacts deploy in an order compatible with accepted Git ancestry and Alembic dependencies. A job with a missing predecessor remains blocked.

### REQ-RECOVERY-001: interrupted deployment

DBM inspects the Alembic version table and schema after interruption before retrying. It never assumes an interrupted revision rolled back when migration code may have used non-transactional operations.

## 4. Safety policy

- Production requires an accepted artifact and fresh schema verification.
- Destructive or data-dependent changes may require additional approvals.
- DBM does not automatically run Alembic downgrades in production.
- Recovery prefers a reviewed forward migration.
- The runner uses statement and lock timeouts defined by environment policy.
- Logs redact secrets and SQL parameters classified as sensitive.
- The coordinator can revoke a queued deployment before execution.
- A running deployment cannot be reported as cancelled until the runner confirms termination and DBM reinspects the database.

## 5. Acceptance scenarios

### AC-DEPLOY-001: normal CI deployment

Given an accepted, verified artifact and an idle staging environment, DBM applies its revisions, verifies the target state, and produces a successful receipt.

### AC-DEPLOY-002: modified artifact

Given an artifact whose content digest differs from the accepted record, DBM rejects the deployment before credentials are issued.

### AC-DEPLOY-003: environment drift

Given a production schema fingerprint that changed after approval, DBM blocks deployment and requires a new verification result.

### AC-DEPLOY-004: concurrent request

Given an active staging deployment, a second deployment request remains queued or fails with `environment_locked` without invoking Alembic.

### AC-DEPLOY-005: interrupted non-transactional revision

Given a terminated runner during a non-transactional revision, DBM marks the attempt `recovery_required`, inspects the database, and does not retry automatically.

## 6. Operational enforcement

DBM becomes the sole migration path through controls rather than a claim:

- only the DBM runner identity receives DDL permissions;
- CI workflows call DBM and never call Alembic directly;
- branch protection requires DBM checks;
- deployment environments allow only signed DBM runner jobs;
- audit alerts identify out-of-band changes through schema drift.

## 7. Explicitly deferred

- automatic production rollback;
- data backfill workers;
- zero-downtime policy generation;
- automatic conversion between database engines;
- migration frameworks other than Alembic until their providers implement the execution contract.
