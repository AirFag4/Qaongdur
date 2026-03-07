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
- Core runtime file: `infra/docker/compose.core.yml`
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

1. Copy `.env.example` to `.env`.
2. Run `make docker-up` from the repo root.

Current browser flow:

1. Open `http://localhost:5173`.
2. The app checks for an existing Keycloak browser session.
3. If you are not signed in yet, the app shows its auth screen.
4. Click `Continue To Keycloak` to start login.

Auth-only bootstrap remains available with `make docker-auth-up`.

If Keycloak was already running from an older realm import, reset the Keycloak Postgres volume before expecting real backend auth to work:

```bash
docker compose --env-file .env -f infra/docker/compose.core.yml down
docker volume rm docker_keycloak-postgres-data
make docker-up
```

Host-based inner loop is still available:

1. Copy `apps/web/.env.example` to `apps/web/.env`.
2. Copy `services/control-api/.env.example` to `services/control-api/.env`.
3. Start the API from `services/control-api` with `uv run qaongdur-control-api`.
4. Start the web app from the repo root with `pnpm --filter @qaongdur/web dev`.

Current limitation:

- auth and approval endpoints are real
- camera onboarding, camera inventory, device inventory, live HLS, overview metrics, and playback search now come from the real `control-api`
- alerts and incidents still use placeholder backend responses until the full alert-to-incident path is implemented

## Seeded Demo Users

All seeded users use the password `ChangeMe123!` for local development:

- `pat.admin`
- `sam.site`
- `olivia.operator`
- `riley.reviewer`
- `victor.viewer`

## Add Or Manage Users

The VMS app does not keep a separate local user table yet. A user who exists in the
Keycloak realm `qaongdur-dev` can log into the app.

Admin console path:

1. Open `http://localhost:8080/admin/`.
2. Sign in with the bootstrap admin account from the repo root `.env`.
3. Select the `qaongdur-dev` realm.

To add a user:

1. Open `Users`.
2. Click `Add user`.
3. Fill username, email, first name, and last name.
4. Enable the user and save.
5. Open `Credentials` and set a password.
6. Open `Role mapping` and assign realm roles such as `viewer`, `operator`, `reviewer`, `site-admin`, or `platform-admin`.

Notes:

- `viewer` is the minimum useful role for basic read access.
- editing `infra/keycloak/import/qaongdur-dev-realm.json` does not update an already-running realm unless you recreate the Keycloak data store and re-import from scratch
- for a running local system, use the admin console to add users rather than editing the realm JSON
- if your local realm was created before the built-in client scopes were added to the import, recreate the Keycloak data store so `qaongdur-web` receives full access-token claims like `sub`, `realm_access`, and `preferred_username`

## Login Methods

Current local login methods for `qaongdur-web`:

- username + password
- email + password
- passkey after WebAuthn passwordless is enabled in Keycloak and the user registers one

Self-registration is currently disabled in the imported realm.

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
