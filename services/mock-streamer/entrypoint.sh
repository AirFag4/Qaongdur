#!/bin/sh
set -eu

target_url="${MOCK_STREAM_TARGET_URL:-rtsp://mediamtx:8554/mock-demo}"
width="${MOCK_STREAM_WIDTH:-1280}"
height="${MOCK_STREAM_HEIGHT:-720}"
fps="${MOCK_STREAM_FPS:-15}"
bitrate="${MOCK_STREAM_BITRATE:-2500k}"
gop_size=$((fps * 2))

echo "Waiting for MediaMTX at ${target_url}..."
until nc -z mediamtx 8554; do
  sleep 1
done

while true; do
  echo "Publishing mock stream to ${target_url}"
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
  echo "Mock stream exited; retrying in 2s"
  sleep 2
done
