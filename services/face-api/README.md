# face-api

FastAPI sidecar that boots the local InspireFace runtime and exposes crop-level face embeddings to `services/vision`.

## Why It Is Separate

- the sibling `../InspireFace` checkout contains Python wrappers and resource packs, but not a ready-to-import Linux runtime inside `services/vision`
- the first startup needs a local CMake build of `libInspireFace.so`
- keeping that build in a sidecar avoids bloating the main `vision` image and lets the face stage degrade cleanly when the runtime is still bootstrapping

## Runtime Shape

- mounts the local sibling `../InspireFace` repo at `/mnt/inspireface`
- uses the `Megatron` resource pack from `/mnt/inspireface/test_res/pack/Megatron`
- compiles `libInspireFace.so` into a persistent Docker volume on first start
- installs the Python wrapper into that same persistent runtime volume
- serves `GET /api/v1/face/status`
- serves `POST /api/v1/face/embed`

## Usage

```bash
cp .env.example .env
make face-up
```

Or run the full stack that needs it:

```bash
cp .env.example .env
make vision-up
```

## Current Limitation

- the first startup can take several minutes because the sidecar compiles InspireFace from source before the HTTP service becomes available
