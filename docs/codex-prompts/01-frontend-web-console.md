# Codex Prompt: Frontend Web Console

You are Codex building the first user-facing application for a video management system with vision AI. Build a polished React operator console first, with realistic mocked data and clean integration boundaries for the backend that will arrive later.

## Product Context

This is not a generic admin dashboard. It is a security and operations console for:

- live camera monitoring
- AI detections and alerts
- incident review
- playback and evidence export
- future in-app agent chat

The UI should feel intentional, high-density, and premium.

## Stack

Use:

- React
- Vite
- TypeScript
- Tailwind CSS
- `shadcn/ui`
- TanStack Query
- TanStack Table
- React Hook Form
- Zod

Use a route-based app structure and keep the data layer behind typed API adapters.

## Visual Direction

Avoid the look of a default SaaS template.

Design direction:

- dark operations-console theme
- warm charcoal surfaces, muted stone panels, restrained cyan for live state
- amber only for attention states, red only for critical alarms
- expressive typography such as Space Grotesk or IBM Plex Sans, plus a monospace companion for timestamps and IDs
- large video surfaces
- dense but readable tables
- subtle motion on page load and panel transitions

## Required Pages

Build these pages with mocked but realistic data:

1. Overview dashboard
2. Live monitoring
3. Alerts and events
4. Incident detail
5. Playback and search
6. Devices and camera inventory

Also reserve a persistent right-side area or slide-over for future agent chat.

## Required Components

Create reusable components for:

- app shell and side navigation
- site and camera switcher
- live video tile
- camera grid layouts for 1, 4, 9, and 16 streams
- alert rail
- filter bar
- incident summary card
- evidence clip panel
- health status badges
- empty states and loading states
- command palette

## Data and Integration Rules

- Use mocked API responses or `msw` so the app looks alive before the real backend exists.
- Create a typed API layer instead of coupling components directly to mock JSON.
- Create a WebSocket abstraction for future real-time events, even if it is mocked initially.
- Keep model overlays, detections, and timelines as data-driven components.

## UX Requirements

- Operators must be able to scan the UI quickly.
- Support keyboard shortcuts for major navigation and camera-grid changes.
- Make the live monitoring view the visual center of the product.
- Tables must support filtering, sorting, and dense rows.
- Playback/search must include a timeline layout, even if backed by placeholder data initially.
- Make the layout work on desktop first, but ensure it still loads and navigates on mobile.

## Deliverables

- A working `apps/web` app scaffold
- The complete page shell and navigation
- Mock-backed pages for the required workflows
- Shared UI primitives in `packages/ui`
- Clear API boundary types in `packages/types` or `packages/api-client`

## Acceptance Criteria

- The app looks like a serious operations product rather than a default template.
- The codebase is ready to swap mocks for real APIs without rewriting page components.
- The design system is coherent across dashboard, video, tables, incidents, and future chat.
- The live-monitoring page is compelling enough for a demo even before backend integration.

