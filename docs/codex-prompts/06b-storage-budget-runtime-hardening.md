# Codex Prompt: Storage Budget, Runtime Hardening, and Crop Search Verification

This hardening slice is now effectively complete and should be read as a handoff note before broader `06` work continues.

You are Codex hardening Qaongdur before the broader identity, map, and ROI work in `06-vision-investigation-identity-search-roi.md` continues.

This slice originally existed because the runtime had two concrete problems:

- the media stack currently behaves like it has two separate `10 GB` limits, one for recordings and one for crop artifacts, instead of one shared budget
- the vision API can fail to bind on lower-spec machines when the embedding runtime initializes at startup

## Goal

Capture the completed hardening state and the remaining follow-ups before continuing deeper `06` feature work.

## Progress Update

- shared media storage budget and Settings-page visibility for the `80/20` split have been implemented
- crop search has been verified with face-first image search plus text/image query merging
- MobileCLIP no longer initializes during vision-service startup; it now loads on the first semantic-search request instead
- crop image search now queries Qdrant across the current web-filtered track window when vector storage is available
- the crop page now supports drag-and-drop image queries, face detected/aligned query previews, and face-review panels in track detail
- source-frame bbox overlays now render against the true frame aspect ratio instead of the outer letterboxed container
- live Docker verification now confirms semantic text search is active with `searchModes=["text"]` once `vision` becomes healthy
- runtime model assets for detector, MobileCLIP, and Megatron are now documented for out-of-Git backup in `docs/model-assets.md`
- remaining gap: some live `vision/status` responses still omit `embedding.state` and `embedding.detail`, so the web runtime hint can lag behind reality

## Completed Outcomes

1. Use a shared media storage budget for the local stack.
2. Split the default `10 GB` budget as:
   - `80%` for playback / recordings
   - `20%` for crop and investigation artifacts
3. Show that budget split clearly on the Settings page.
4. Keep the repo default safe for semantic search by lazily loading MobileCLIP instead of binding it at startup.
5. Verify that crop search still works through the running stack after the storage/runtime changes.

## Current Runtime Direction

The local dev default should be:

- shared total media budget: `10 GB`
- recordings: `8 GB`
- crop artifacts: `2 GB`
- vision embeddings: enabled locally by default again, with MobileCLIP loaded on first semantic request instead of at app bind time

The repo default should stay easy to understand for new developers:

- one total budget variable
- explicit percentage split
- settings page reflects the resolved values

## Remaining Follow-Ups

- fix the `vision/status` embedding serializer mismatch so the runtime hint always reflects the real semantic-search path
- reduce `face-api` timeout failures under heavier processing load
- decide whether detector initialization should also move to a lazy or warmable path
- keep writable settings UI out of scope for this historical slice

## Verification Snapshot

Verified after implementation:

1. bring up the affected runtime services
2. confirm `vision` becomes healthy
3. confirm the Settings page backend payload includes the resolved storage split
4. confirm crop search works again through the running API path
5. confirm live text search returns `searchModes=["text"]` once the runtime is warm
6. state the remaining degraded path explicitly: `vision/status` embedding fields can still be incomplete

## Exit Criteria

This hardening slice is done when:

- the storage budget is clearly shared and split `80/20`
- the Settings page exposes the split and the current embedding state
- the local runtime no longer blocks the crop page because of eager embedding initialization
- crop search is verified against the running stack

Status:

- met, with the remaining status-payload caveat called out above

Continue broader `06` work only after this slice is stable.

## Follow-On Job Plan

After this hardening slice, the next implementation pass should focus on:

1. Fix the `vision/status` embedding state/detail contract gap so UI hints match real semantic-search readiness.
2. ROI-aware filtering and saved investigation pivots on top of the current crop/face review flow.
3. Face-search recovery paths for older tracks that were processed before Qdrant or face-sidecar availability stabilized.
4. Operator actions on top of the new face-debug previews:
   - mark a face as review-worthy
   - group repeated matches into subject/identity lists
   - attach audit notes to future face-match decisions
