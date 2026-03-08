#!/bin/sh
set -eu

target_base_url="${MOCK_STREAM_TARGET_BASE_URL:-rtsp://mediamtx:8554}"
video_dir="${MOCK_STREAM_VIDEO_DIR:-/mock-videos}"
path_prefix="${MOCK_STREAM_PATH_PREFIX:-mock-video}"
synthetic_path="${MOCK_STREAM_SYNTHETIC_PATH:-mock-demo}"
width="${MOCK_STREAM_WIDTH:-1280}"
height="${MOCK_STREAM_HEIGHT:-720}"
fps="${MOCK_STREAM_FPS:-15}"
bitrate="${MOCK_STREAM_BITRATE:-2500k}"
preset="${MOCK_STREAM_PRESET:-ultrafast}"
gop_size=$((fps * 2))

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

publish_synthetic() {
  target_url="${target_base_url%/}/${synthetic_path}"

  while true; do
    echo "Publishing fallback synthetic stream to ${target_url}"
    ffmpeg \
      -hide_banner \
      -loglevel warning \
      -re \
      -f lavfi \
      -i "testsrc2=size=${width}x${height}:rate=${fps}" \
      -an \
      -c:v libx264 \
      -preset veryfast \
      -tune zerolatency \
      -pix_fmt yuv420p \
      -g "${gop_size}" \
      -keyint_min "${fps}" \
      -sc_threshold 0 \
      -b:v "${bitrate}" \
      -rtsp_transport tcp \
      -f rtsp \
      "${target_url}"
    echo "Synthetic stream exited; retrying in 2s"
    sleep 2
  done
}

publish_file_loop() {
  file_path="$1"
  file_name="$(basename "$file_path")"
  stem="${file_name%.*}"
  slug="$(slugify "$stem")"
  if [ -z "$slug" ]; then
    echo "Skipping file with empty slug: ${file_name}"
    return 0
  fi

  target_url="${target_base_url%/}/${path_prefix}-${slug}"

  while true; do
    echo "Publishing ${file_name} to ${target_url}"
    ffmpeg \
      -hide_banner \
      -loglevel warning \
      -fflags +genpts \
      -stream_loop -1 \
      -re \
      -i "${file_path}" \
      -an \
      -vf "fps=${fps},scale=${width}:${height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:black" \
      -c:v libx264 \
      -preset "${preset}" \
      -tune zerolatency \
      -pix_fmt yuv420p \
      -r "${fps}" \
      -g "${gop_size}" \
      -keyint_min "${fps}" \
      -sc_threshold 0 \
      -b:v "${bitrate}" \
      -rtsp_transport tcp \
      -f rtsp \
      "${target_url}"
    echo "Publisher for ${file_name} exited; retrying in 2s"
    sleep 2
  done
}

echo "Waiting for MediaMTX at ${target_base_url}..."
until nc -z mediamtx 8554; do
  sleep 1
done

publishers_started=0
if [ -d "${video_dir}" ]; then
  for file_path in "${video_dir}"/*.mp4; do
    if [ ! -f "${file_path}" ]; then
      continue
    fi
    publish_file_loop "${file_path}" &
    publishers_started=$((publishers_started + 1))
  done
fi

if [ "${publishers_started}" -eq 0 ]; then
  echo "No mock videos found in ${video_dir}; falling back to a synthetic stream."
  publish_synthetic &
fi

wait
