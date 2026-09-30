# DBM user journey

This story follows Maya, a developer who needs to add `phone_number` to the `users` table.

## The short version

```text
Maya proposes a database change
              |
              v
Her coding agent sends structured intent through DBM's MCP server
              |
              v
DBM checks four sources of truth
  1. the real database, using read-only access
  2. accepted migrations in Git
  3. proposals from other developers and agents
  4. DBM migration jobs queued or running in CI
              |
              v
DBM returns safe, stale, dependent, conflict, or deployment_in_progress
              |
              v
Maya reviews and approves the meaning of the change
              |
              v
CI gives the concrete migration artifact to DBM
              |
              v
DBM tests it on a disposable shadow database
              |
              v
DBM locks the target, runs Alembic in its one-shot runner, and verifies the result
```

The MCP server is the doorway used by the coding agent. The coordinator stores state and makes deterministic decisions. The isolated runner is the only component allowed to change a shared database.

## 1. One-time project setup

Maya's team opens the DBM setup console and:

1. connects its GitHub or GitLab repository;
2. tells DBM where `alembic.ini` and the migrations directory live;
3. connects staging and production with dedicated read-only inspection credentials;
4. configures a separate migration identity that only the DBM runner can obtain;
5. adds the DBM check to the pull-request or merge-request pipeline.

The browser, MCP server, and coding agent never receive the migration credential.

## 2. Maya proposes a change

Maya tells her coding agent:

> Add an optional phone number to users.

Before generating an Alembic file, the agent creates this intent:

```json
{
  "kind": "add_column",
  "object": {
    "schema_name": "public",
    "table_name": "users",
    "column_name": "phone_number"
  },
  "after": {
    "type": "varchar(32)",
    "nullable": true
  }
}
```

The agent sends it to the DBM MCP server. This records what Maya means to do before a migration revision is created.

## 3. DBM gathers current truth

DBM now checks four things.

### The real database

Using a read-only connection, DBM observes the current tables, columns, constraints, indexes, schema fingerprint, and Alembic revision. The check cannot alter data or schema.

### Accepted Git history

The source-control provider reads the default branch and its accepted Alembic graph. This answers: “What has the team agreed should exist?”

### Other proposals

The coordinator compares Maya's intent with active intents from every connected branch, developer, and coding agent.

### Running migration work

The CI provider tells DBM about migration artifacts and deployments that DBM has queued or is currently running. An arbitrary job that bypasses DBM is not considered trusted migration work and will later appear as schema drift.

## 4. Maya gets a deterministic answer

DBM returns one primary result plus exact findings.

### Safe

No accepted, proposed, observed, or running change overlaps `users.phone_number`.

```text
SAFE
users.phone_number can be added on the observed schema.
Checked schema fingerprint: sha256:...
```

### Stale

Maya's branch started from an old Alembic graph. She needs to update her branch and ask DBM to check again.

### Dependent

Another proposal creates something Maya needs. For example, her foreign key depends on a new `organizations` table from another branch.

### Conflict

Another developer is already adding `users.phone_number`, or the real database disagrees with Maya's declared starting state. DBM identifies the exact object and related intent.

### Deployment in progress

A DBM runner is already changing this environment. DBM waits for it to finish, observes the new schema fingerprint, and checks Maya's proposal again. It does not make a decision using an outdated snapshot.

These results come from rules and observed state, not an LLM guess. An AI may explain the findings or suggest options, but it cannot change the result or approve a semantic decision for Maya.

## 5. Maya approves the meaning

If the result is safe, Maya confirms that an optional `varchar(32)` column is what she intended.

If DBM found that `phone` already exists and the agent suggests renaming it to `phone_number`, Maya must explicitly approve that reinterpretation. DBM never treats “add” and “rename” as equivalent on its own.

## When many developers work concurrently

DBM allows proposal checks to run concurrently, but serializes finalization and deployment.

Suppose Alice and Bob both begin from Alembic head `m10`:

1. both intents record `m10` and the same accepted graph digest;
2. DBM compares each intent with the other, so overlapping changes can conflict before either migration file exists;
3. only one intent can hold the project finalization lease at a time;
4. when Alice merges `m11`, DBM advances the accepted graph and invalidates Bob's result against `m10`;
5. Bob updates his branch, DBM checks it again against `m11`, and only then may it receive a new green result;
6. required CI checks are tied to the exact commit SHA, graph digest, and observed schema fingerprint, so an old green result cannot be reused.

GitHub merge queues and GitLab merge trains can ask DBM to check the synthetic commit that would result from each merge. This prevents two independently green changes from producing a surprising combined graph.

Deployments use a separate queue and lock per environment. Staging and production may make progress independently, but two schema-changing jobs never run concurrently against the same environment. After acquiring the lock, DBM re-observes the database; if its fingerprint changed while the job waited, DBM checks again or stops.

## 6. The migration is generated and reviewed

The agent acquires a short finalization lease, generates the Alembic revision, reviews its `upgrade` and `downgrade`, runs project tests, and releases the lease.

The lease prevents two agents from finalizing migrations from the same accepted graph at the same time. It does not permanently reserve an Alembic revision number.

## 7. CI verifies the concrete migration

When Maya opens a pull request or merge request, CI sends DBM an immutable artifact containing:

- the repository and commit SHA;
- the Alembic graph digest and target revision;
- the migration files and their content digest;
- Maya's accepted intent.

DBM reconstructs the accepted schema in a disposable shadow database and applies the artifact there. It compares the result with the approved intent and publishes a required check back to GitHub or GitLab.

The real staging or production database is not changed during this step.

## 8. DBM performs the migration

After merge and any required environment approval, CI asks DBM to deploy the exact accepted artifact.

DBM then:

1. verifies the artifact digest and source commit;
2. acquires a DBM environment lock and a database-native lock;
3. re-reads the real schema with the read-only identity;
4. blocks if the schema changed after approval;
5. starts a one-shot runner with a short-lived migration credential;
6. has that runner invoke Alembic for the approved target revision;
7. observes the database again and verifies its revision and fingerprint;
8. stores an immutable deployment receipt;
9. destroys the runner and releases the locks.

No official CI workflow runs `alembic upgrade` directly. Alembic remains the execution engine, but DBM is the only migration authority.

## 9. What Maya sees at the end

```text
DEPLOYED
Environment: production
Artifact: sha256:...
From revision: 4ac12e
To revision: 8bd771
Observed schema: sha256:...
Intent: add public.users.phone_number varchar(32) nullable
Receipt: dep_01...
```

Maya can answer who proposed the change, who approved it, which code produced it, what DBM checked, what ran, and what the real database looked like afterward.

## Responsibility boundary

| Component | Responsibility |
| --- | --- |
| Developer | Proposes the product meaning and approves semantic choices |
| Coding agent | Converts the request into structured intent and migration code |
| MCP server | Gives agents a safe, structured interface to DBM |
| Coordinator | Stores truth, compares state, enforces policy, and authorizes work |
| Read-only inspector | Observes the real database without changing it |
| CI provider | Proves job/repository identity and delivers trusted artifacts |
| Shadow validator | Tests the concrete migration away from real environments |
| One-shot runner | Temporarily receives DDL access and invokes Alembic |
| Alembic | Executes the migration operations selected and authorized by DBM |
