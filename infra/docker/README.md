# docker

Local Docker assets for auth and future platform services.

## Auth Stack

This directory now includes `compose.auth.yml`, which boots:

- Postgres for Keycloak state
- Keycloak with realm import enabled

## Usage

```bash
cp infra/docker/.env.example infra/docker/.env
docker compose --env-file infra/docker/.env -f infra/docker/compose.auth.yml up -d
```

Default endpoints:

- Keycloak: `http://localhost:8080`
- Keycloak Postgres: `localhost:5433`

The compose file imports `../keycloak/import/qaongdur-dev-realm.json` automatically on first boot.
