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
