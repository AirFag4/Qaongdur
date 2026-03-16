# Codex Prompt: Storage Budget, Runtime Hardening, and Crop Search Verification

You are Codex hardening Qaongdur before the broader identity, map, and ROI work in `06-vision-investigation-identity-search-roi.md` continues.

This slice exists because the current runtime still has two concrete problems:

- the media stack currently behaves like it has two separate `10 GB` limits, one for recordings and one for crop artifacts, instead of one shared budget
- the vision API can fail to bind on lower-spec machines when the embedding runtime initializes at startup

## Goal

Make the current stack operational and predictable on constrained local hardware before continuing deeper `06` feature work.

## Progress Update

- shared media storage budget and Settings-page visibility for the `80/20` split have been implemented
- crop search has been verified with face-first image search plus text/image query merging
- MobileCLIP no longer initializes during vision-service startup; it now loads on the first semantic-search request instead
- crop image search now queries Qdrant across the current web-filtered track window when vector storage is available
- the crop page now supports drag-and-drop image queries, face detected/aligned query previews, and face-review panels in track detail
- source-frame bbox overlays now render against the true frame aspect ratio instead of the outer letterboxed container

## Required Outcomes

1. Use a shared media storage budget for the local stack.
2. Split the default `10 GB` budget as:
   - `80%` for playback / recordings
   - `20%` for crop and investigation artifacts
3. Show that budget split clearly on the Settings page.
4. Keep object embeddings disabled in the local runtime config on this machine until startup-safe embedding initialization is implemented.
5. Verify that crop search still works through the running stack after the storage/runtime changes.

## Scope

Implement now:

- shared media budget config and derived recording / artifact limits
- settings API and Settings page visibility for:
  - total media budget
  - playback allocation
  - crop artifact allocation
  - current embedding enabled / disabled state
- local `.env` override to keep vision embeddings disabled on this machine
- actual runtime verification of crop search after the change

Do not implement yet:

- a full startup-safe MobileCLIP initialization redesign
- writable settings UI

## Runtime Direction

The local dev default should be:

- shared total media budget: `10 GB`
- recordings: `8 GB`
- crop artifacts: `2 GB`
- vision embeddings: disabled locally until the startup path is fixed

The repo default should stay easy to understand for new developers:

- one total budget variable
- explicit percentage split
- settings page reflects the resolved values

## Verification Requirements

After implementation:

1. bring up the affected runtime services
2. confirm `vision` becomes healthy
3. confirm the Settings page backend payload includes the resolved storage split
4. confirm crop search works again through the running API path
5. if the runtime must stay degraded, state exactly what is still degraded

## Exit Criteria

This hardening slice is done when:

- the storage budget is clearly shared and split `80/20`
- the Settings page exposes the split and the current embedding state
- the local runtime no longer blocks the crop page because of the current embedding override
- crop search is verified against the running stack

Continue broader `06` work only after this slice is stable.

## Follow-On Job Plan

After this hardening slice, the next implementation pass should focus on:

1. ROI-aware filtering and saved investigation pivots on top of the current crop/face review flow.
2. Face-search recovery paths for older tracks that were processed before Qdrant or face-sidecar availability stabilized.
3. Operator actions on top of the new face-debug previews:
   - mark a face as review-worthy
   - group repeated matches into subject/identity lists
   - attach audit notes to future face-match decisions
