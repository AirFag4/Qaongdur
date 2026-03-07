# Authentication Guide

This repo now includes the auth foundation from `docs/codex-prompts/02-auth-keycloak-passkeys.md`:

- Keycloak as the identity provider
- browser login via Authorization Code Flow with PKCE
- backend JWT validation through OIDC discovery and JWKS
- realm-role based authorization
- passkey registration and future step-up hooks

This auth stack is also the first slice of the future `core` container runtime. The next milestone should build the rest of the `core` profile around it rather than treating auth as a one-off container.

## Local Components

### Keycloak

- Compose file: `infra/docker/compose.auth.yml`
- Realm import: `infra/keycloak/import/qaongdur-dev-realm.json`
- Default realm: `qaongdur-dev`
- Browser client: `qaongdur-web`
- API audience: `qaongdur-control-api`

### Web App

- Env example: `apps/web/.env.example`
- Keycloak session bootstrap: `apps/web/src/auth`
- Authenticated UI gate: `apps/web/src/App.tsx`
- Approval and passkey actions live in the agent rail so the future chatbot stays inside the same session model

### Control API

- Env example: `services/control-api/.env.example`
- Token verifier: `services/control-api/src/control_api/auth.py`
- Audit logger: `services/control-api/src/control_api/audit.py`
- Protected endpoints: `services/control-api/src/control_api/main.py`

## Start The Stack

1. Copy `infra/docker/.env.example` to `infra/docker/.env`.
2. Run `docker compose --env-file infra/docker/.env -f infra/docker/compose.auth.yml up -d`.
3. Copy `apps/web/.env.example` to `apps/web/.env`.
4. Copy `services/control-api/.env.example` to `services/control-api/.env`.
5. Start the API from `services/control-api` with `uv run qaongdur-control-api`.
6. Start the web app from the repo root with `pnpm --filter @qaongdur/web dev`.

## Seeded Demo Users

All seeded users use the password `ChangeMe123!` for local development:

- `pat.admin`
- `sam.site`
- `olivia.operator`
- `riley.reviewer`
- `victor.viewer`

## Role Model

- `platform-admin`: global admin and destructive operations
- `site-admin`: site-scoped admin and approval flows
- `operator`: monitoring and standard response
- `reviewer`: evidence and incident approvals
- `viewer`: read-only access

Frontend role-gating is only a UX convenience. The control API validates the bearer token and checks roles again before allowing protected actions.

## Passkeys

Passkeys are deliberately handled by Keycloak's login and account flows, not by custom chat commands or frontend WebAuthn glue code.

Local path:

1. Sign in to the web app through Keycloak.
2. Use the `Register Passkey` action in the right rail.
3. Complete registration in the Keycloak flow.
4. On the next login, choose the passkey option if the browser and platform support it.

## Step-Up Hook

The app exposes a `Step-Up Reauth` action that re-runs login with a configured ACR value.

- web env: `VITE_KEYCLOAK_STEP_UP_ACR`
- API env: `QAONGDUR_KEYCLOAK_STEP_UP_ACR`

The destructive backend example endpoint refuses the request unless the token carries that expected `acr` claim.
