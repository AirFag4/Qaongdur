# Codex Prompt: In-App Agent Chat and OpenClaw Integration

You are Codex designing the first agent layer for the VMS product. The agent is not the whole product. It is an in-app assistant that helps operators search events, summarize incidents, and later perform controlled actions.

## Primary Goal

Create a safe, auditable in-app chat foundation that can later connect to OpenClaw without forcing the UI or auth system to be rebuilt.

## Important Product Constraints

- the agent lives inside the web app
- the agent reuses the logged-in user session
- the agent must be auditable
- the agent must not execute privileged actions silently

## Integration Direction

Build `services/agent` as an adapter-based service.

Create a provider interface so the system can support:

- a local mock provider for early UI work
- an OpenClaw-backed provider later

Do not hard-code the whole product directly to one agent framework.

## First-Scope Agent Capabilities

Support read-heavy workflows first:

- search alerts by natural language
- summarize an incident from detections and notes
- explain why an alert fired
- suggest next actions
- surface relevant cameras, clips, and operators

Delay write-heavy or destructive actions until approval and auth hooks are in place.

## Tooling Model

Design tool interfaces for:

- alert search
- incident lookup
- camera lookup
- playback lookup
- system health lookup
- note creation

All tool calls must be logged with:

- user ID
- session ID
- tool name
- request timestamp
- success or failure

## Approval Model

If the agent later requests a sensitive action, the system must support:

- explicit operator approval in the UI
- role checks on the backend
- optional step-up auth hook for high-risk actions

Build the contracts for that now, even if the first version only supports read-only tools.

## Frontend Requirements

Add a persistent chat panel pattern to the React app with:

- conversation history
- streaming assistant responses
- references to alerts, incidents, and cameras
- visible tool activity state
- an approval UI placeholder

## Backend Requirements

- store conversations and tool traces
- stream responses to the frontend
- keep provider-specific code isolated behind interfaces
- make the OpenClaw integration a module, not a product-wide dependency leak

## Deliverables

- `services/agent` scaffold
- provider interface
- mock provider
- chat session API
- frontend chat shell
- audit trail model for tool usage

## Acceptance Criteria

- the product has a usable in-app chat shell before OpenClaw is fully integrated
- provider swaps do not require rewriting the UI
- all tool usage is auditable
- the auth model remains owned by the main app and Keycloak, not by the agent itself

