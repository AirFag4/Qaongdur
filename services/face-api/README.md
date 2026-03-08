# face-api

FastAPI sidecar that boots the vendored InspireFace runtime and exposes crop-level face embeddings to `services/vision`.

## Why It Is Separate

- the vendored `third_party/InspireFace` submodule contains the Python wrappers and model-download scripts, but not a ready-to-import Linux runtime inside `services/vision`
- the first startup needs a local CMake build of `libInspireFace.so`
- the released `Megatron` model pack is fetched into the persistent runtime volume on first start if it is not already present under the vendored repo
- keeping that build in a sidecar avoids bloating the main `vision` image and lets the face stage degrade cleanly when the runtime is still bootstrapping

## Runtime Shape

- copies the vendored `third_party/InspireFace` submodule into the image at `/opt/third_party/InspireFace`
- hydrates the `Megatron` resource pack into `/runtime/resources/pack/Megatron`
- compiles `libInspireFace.so` into a persistent Docker volume on first start
- installs the Python wrapper into that same persistent runtime volume
- serves `GET /api/v1/face/status`
- serves `POST /api/v1/face/embed`

## Usage

```bash
git submodule update --init --recursive
cp .env.example .env
make face-up
```

Or run the full stack that needs it:

```bash
git submodule update --init --recursive
cp .env.example .env
make vision-up
```

## Current Limitation

- the first startup can take several minutes because the sidecar compiles InspireFace from source before the HTTP service becomes available
- the first startup also downloads the `Megatron` model pack into the runtime volume when the vendored repo does not already include it
- clones that skipped `--recurse-submodules` must initialize `third_party/InspireFace` before the image can build
