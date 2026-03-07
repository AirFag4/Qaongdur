# VMS + Vision AI + Agent AI Planning Docs

This repository currently contains Codex-ready implementation briefs for a Docker-based open-source VMS with a React frontend, Keycloak auth, a vision pipeline, and an in-app agent/chat layer.

Recommended execution order:

1. [`docs/codex-prompts/00-repo-structure.md`](docs/codex-prompts/00-repo-structure.md)
2. [`docs/codex-prompts/01-frontend-web-console.md`](docs/codex-prompts/01-frontend-web-console.md)
3. [`docs/codex-prompts/02-auth-keycloak-passkeys.md`](docs/codex-prompts/02-auth-keycloak-passkeys.md)
4. [`docs/codex-prompts/03-backend-vms-ai-platform.md`](docs/codex-prompts/03-backend-vms-ai-platform.md)
5. [`docs/codex-prompts/04-agent-chat-openclaw.md`](docs/codex-prompts/04-agent-chat-openclaw.md)
6. [`docs/codex-prompts/05-docker-open-source-platform.md`](docs/codex-prompts/05-docker-open-source-platform.md)

High-level recommendation:

- Keep this as a monorepo, not a polyrepo, for the first public versions.
- Use `apps/` for user-facing applications, `services/` for Python backend services, `packages/` for shared TypeScript code, and `infra/` for Docker, Keycloak, and media infrastructure.
- Start with a modular monolith for vision inference, then split workers only when throughput forces it.

