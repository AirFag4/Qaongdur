# Runtime Model Assets

Current Qaongdur local runtime uses three non-repo model assets that should stay outside Git.

## Active Models

| Component | Model | Runtime location | Persistence |
| --- | --- | --- | --- |
| detector | `yolo26n.pt` | `vision` container: `/app/yolo26n.pt` | baked into the built image |
| crop text and image embedding | `MobileCLIP2-S0` | `vision` container cache: `/root/.cache/huggingface/hub/models--timm--MobileCLIP2-S0-OpenCLIP/.../open_clip_model.safetensors` | cached after first semantic load |
| face embedding | `Megatron` | `face-api` runtime volume: `/runtime/resources/pack/Megatron` | persisted in the Docker runtime volume |

## Backup Guidance

- keep machine-local backups in a sibling folder outside this repo, for example `../model-weight-backups/`
- do not commit model weights, runtime packs, or large cache blobs into this repository
- refresh the backup whenever the configured detector, MobileCLIP variant, or face pack changes
- if you want a faster cold restore, back up both the weight file and a small manifest that records the model name and original runtime path

## Why This Matters

- the first `face-api` startup may need to rehydrate the `Megatron` pack into the runtime volume
- the first semantic crop-search request loads `MobileCLIP2-S0` lazily, so missing cache can add download or restore time
- rebuilding the `vision` image still restores `yolo26n.pt`, but keeping a local copy makes it easier to compare or pin detector revisions outside Docker
