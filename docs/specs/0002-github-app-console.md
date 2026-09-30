# Specification 0002: GitHub App and setup console

Status: Proposed

Date: 30 September 2026

Target branch: `feat/github-app-console`, after specification 0001 is merged

## 1. Purpose

Provide a web console where a team creates a DBM project, installs a GitHub App on selected repositories, configures its Alembic location, and attaches database environments.

The console improves onboarding and visibility. The local CLI and MCP server remain the source of schema intent from developer branches.

## 2. GitHub integration

DBM must use a GitHub App rather than personal access tokens.

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

## 3. Setup flow

1. The user signs in to the DBM console.
2. The user creates a project.
3. The user chooses “Install GitHub App.”
4. GitHub asks which organization and repositories the App may access.
5. DBM lists only repositories granted to that installation.
6. The user chooses the default branch, `alembic.ini` path, and migration directory.
7. DBM reads the accepted migration graph and displays its current heads.
8. The user may enable a required DBM pull-request check.
9. The user attaches read-only database environments for schema verification.

## 4. Database environment onboarding

Schema inspection access is read-only. The console supports either:

- a connection string encrypted by the coordinator; or
- a reference to a supported external secret manager.

The browser sends credentials only over TLS. API and MCP responses never return the stored secret. Logs, audit events, errors, and telemetry must redact connection strings.

The initial environment form captures:

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
- GitHub webhook delivery status;
- configured environments with secret values hidden.

## 6. Security requirements

- Sign and verify the GitHub App installation callback state.
- Verify every webhook with the GitHub webhook secret before processing it.
- Store installation private keys outside the application database.
- Encrypt locally stored database credentials with a rotatable key.
- Redact credentials and tokens from logs and error responses.
- Record repository and environment configuration changes in the audit log.
- Restrict project administration to authenticated project owners.
- Prevent server-side request forgery when testing database connections.

## 7. Explicitly deferred

- automatic pull-request code mutation;
- merging pull requests;
- storing migration credentials in the browser or exposing them to agents;
- GitLab and Bitbucket integrations;
- organization billing and enterprise SSO.
