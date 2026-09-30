# Specification 0002: Source-control applications and setup console

Status: Proposed

Date: 30 September 2026

Target branch: `feat/source-control-console`, after specification 0005 is merged

## 1. Purpose

Provide a web console where a team creates a DBM project, connects a repository through its source-control provider, configures its migration engine, and attaches database environments.

The console improves onboarding and visibility. The local CLI and MCP server remain the source of schema intent from developer branches.

## 2. Source-control integration

DBM must use provider applications rather than asking users for personal access tokens. GitHub uses a GitHub App. GitLab uses the provider adapter's application authorization and scoped webhook flow. Provider credentials are never stored in repository configuration.

### GitHub

The App requests the minimum repository permissions needed:

- metadata: read;
- contents: read;
- pull requests: read;
- checks: write when the repository enables DBM status checks.

The App subscribes to:

- installation and installation repository changes;
- pull request opened, synchronized, reopened, closed, and merged events;
- push events on the configured default branch;
- branch deletion events.

DBM stores the GitHub installation ID and repository identity. It creates short-lived installation tokens only when calling GitHub. It never asks a developer for a personal access token.

### GitLab

The GitLab provider requests only the scopes needed to read repository metadata and commits, read merge requests, manage DBM webhooks, and publish commit or pipeline status. It supports GitLab.com and explicitly configured self-managed instances.

DBM stores the GitLab host and provider-native project ID separately from namespace and repository names. Every webhook is associated with one configured connection and verified using that connection's secret.

## 3. Setup flow

1. The user signs in to the DBM console.
2. The user creates a project.
3. The user chooses GitHub, GitLab, or another available source-control provider.
4. The provider asks which organization, group, or repositories DBM may access.
5. DBM lists only repositories granted to that provider connection.
6. The user chooses the default branch, `alembic.ini` path, and migration directory.
7. DBM reads the accepted migration graph and displays its current heads.
8. The user may enable a required DBM pull-request or merge-request check.
9. The user attaches read-only database environments for schema verification.

## 4. Database environment onboarding

Schema inspection access is read-only. The console supports either:

- a connection string encrypted by the coordinator; or
- a reference to a supported external secret manager.

The browser sends credentials only over TLS. API and MCP responses never return the stored secret. Logs, audit events, errors, and telemetry must redact connection strings.

The environment form is generated from the selected database provider's configuration schema. The PostgreSQL form captures:

- environment name;
- PostgreSQL host, port, database, and TLS mode;
- username and secret input or secret reference;
- a “Test connection” action;
- an explicit read-only confirmation.

DBM validates the inspection connection as described by specification 0003. Migration credentials are separate and are available only to the isolated deployment runner described by specification 0004.

## 5. Console views

The first console includes:

- project setup and repository connection;
- accepted Alembic heads and graph digest;
- active intents with status and branch provenance;
- structured conflict and dependency findings;
- active and expired finalization leases;
- source-control webhook delivery status;
- configured environments with secret values hidden.

## 6. Security requirements

- Sign and verify every provider-application authorization callback state.
- Verify every webhook with the provider connection's secret before processing it.
- Store application private keys and client secrets outside the application database.
- Encrypt locally stored database credentials with a rotatable key.
- Redact credentials and tokens from logs and error responses.
- Record repository and environment configuration changes in the audit log.
- Restrict project administration to authenticated project owners.
- Prevent server-side request forgery when testing database connections.

## 7. Explicitly deferred

- automatic pull-request code mutation;
- merging pull requests;
- storing migration credentials in the browser or exposing them to agents;
- Bitbucket and Gitea application flows;
- organization billing and enterprise SSO.
