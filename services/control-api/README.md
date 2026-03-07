# control-api

FastAPI scaffold for the Qaongdur control plane with Keycloak token validation, role-based authorization dependencies, and audit-log examples for agent approvals.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Start Keycloak with the realm import in `infra/docker/compose.auth.yml`.
3. Run the API with `uv run qaongdur-control-api` from this directory.

Alternative development command:

```bash
uv run uvicorn control_api.main:app --app-dir src --reload
```

## Current Endpoints

- `GET /healthz`: unauthenticated health check
- `GET /api/v1/auth/me`: validates a Keycloak bearer token via OIDC discovery + JWKS
- `GET /api/v1/auth/allowed-actions`: example role expansion for frontend capability hints
- `POST /api/v1/agent/actions/evidence-export`: role + approval-path example
- `POST /api/v1/agent/actions/purge-evidence`: platform-admin + step-up hook example

## Notes

- Tokens are validated against the realm discovery metadata and JWKS, not trusted from frontend claims alone.
- Expected audience defaults to `qaongdur-control-api`.
- Destructive actions check the `acr` claim so the frontend can trigger a re-authentication flow before retrying.
