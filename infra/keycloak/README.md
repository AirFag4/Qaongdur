# keycloak

Realm bootstrap assets for Qaongdur authentication.

This is the first always-on infrastructure service in the planned `core` Compose runtime. Follow-up platform work should add the rest of the shared stack around this service instead of returning to a host-only default path.

## Included Bootstrap

- `import/qaongdur-dev-realm.json`
  - realm: `qaongdur-dev`
  - browser client: `qaongdur-web`
  - API audience client: `qaongdur-control-api`
  - platform roles: `platform-admin`, `site-admin`, `operator`, `reviewer`, `viewer`
  - seeded demo users for each role profile

## Admin Console

When Keycloak is running locally, use:

- URL: `http://localhost:8080/admin/`
- realm for the app: `qaongdur-dev`
- bootstrap admin credentials: read from the repo root `.env`

Adding a user for the VMS app means adding that user to the `qaongdur-dev` realm and
assigning the appropriate realm roles.

Recommended local sequence:

1. Open `Users`.
2. Create the user.
3. Set a password in `Credentials`.
4. Assign realm roles in `Role mapping`.

The app currently trusts Keycloak as the source of truth for user identities and roles.

## Passkeys

The realm import sets WebAuthn relying-party defaults, but the full passwordless browser flow still needs to be enabled in the Keycloak admin console for your local environment.

Recommended local sequence:

1. Copy `.env.example` to `.env` at the repo root.
2. Start Keycloak with `make docker-auth-up` or boot the full stack with `make docker-up`.
3. Open the admin console and inspect the imported `qaongdur-dev` realm.
4. Enable WebAuthn passwordless in the browser authentication flow.
5. Let users register passkeys through the Keycloak account or the in-app `webauthn-register-passwordless` action.
6. If you want destructive actions to require step-up, map your chosen ACR value to the stronger login flow and keep it aligned with `VITE_KEYCLOAK_STEP_UP_ACR` and `QAONGDUR_KEYCLOAK_STEP_UP_ACR`.

The web app intentionally delegates passkey UX to Keycloak instead of handling WebAuthn directly in app code.

## Current App Login Flow

The frontend uses `check-sso` on load, not forced redirect.

That means a typical local login looks like this:

1. open `http://localhost:5173`
2. see the app auth screen when no browser session exists yet
3. click `Continue To Keycloak`
4. complete login in Keycloak
