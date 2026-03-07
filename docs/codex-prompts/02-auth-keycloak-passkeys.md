# Codex Prompt: Authentication with Keycloak and Passkeys

You are Codex implementing authentication and authorization for a React-based VMS platform. Use Keycloak as the identity provider and design the app so passkeys work cleanly in the browser while future chatbot actions stay inside the same authenticated session model.

## Primary Goal

Implement production-grade auth foundations for:

- web login
- role-based access control
- passkey support
- future step-up approval for sensitive agent actions

## Required Auth Model

Use:

- Keycloak as the identity provider
- OpenID Connect Authorization Code Flow with PKCE for the web app
- JWT validation on backend APIs
- realm or client roles for authorization

Use a browser-based auth flow. Do not invent a custom login system.

## Important Product Constraint

The future chatbot is in-app. It should reuse the user session that already exists in the browser application.

That means:

- the user logs into the web app through Keycloak
- the chat panel inherits the authenticated app session
- privileged chat actions require authorization checks on the backend
- especially sensitive actions can trigger step-up re-authentication

Do not design the chatbot as a separate identity system.

## Passkey Rules

Implement passkeys through Keycloak's WebAuthn passwordless capabilities.

Expected behavior:

- users can sign in to the browser app with passkeys when their environment supports it
- passkey registration can be offered through Keycloak required actions or account security flows
- passkeys are handled by the browser and Keycloak login UI, not by ad hoc chatbot message handling

Important scope rule:

- an embedded web chatbot can participate in authenticated workflows because it runs inside the logged-in app
- an external chatbot channel such as WhatsApp, Telegram, or Slack cannot directly use browser passkeys unless it hands the user off to a browser or native app that supports WebAuthn

## Suggested Authorization Model

Define at least these roles:

- `platform-admin`
- `site-admin`
- `operator`
- `reviewer`
- `viewer`

Sensitive agent actions should require both:

- role permission
- explicit user approval in the UI

For destructive or high-risk actions, leave a hook for step-up authentication.

## Backend Integration Requirements

- backends must validate Keycloak-issued tokens from JWKS or discovery metadata
- services must not trust frontend role claims without server-side validation
- audit log entries must record acting user, role, action, timestamp, and approval path

## Docker and Configuration Requirements

- provide a Dockerized Keycloak setup for local development
- add realm bootstrap artifacts under `infra/keycloak/`
- include sample clients for the web app and backend APIs
- include environment examples and local setup notes

## Deliverables

- Keycloak Docker setup
- realm bootstrap or import files
- app auth integration for the React frontend
- backend token-validation middleware
- role mapping and authorization guard examples
- passkey setup notes in project docs

## Acceptance Criteria

- a user can log into the web app through Keycloak
- backend APIs can validate issued tokens correctly
- role checks work end to end
- the design leaves a clear path for passkey login and step-up approval flows
- the in-app chatbot can rely on the same authenticated session model instead of creating a second auth stack

