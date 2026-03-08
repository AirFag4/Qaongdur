FROM alpine:3.20

RUN apk add --no-cache ffmpeg busybox-extras

COPY services/mock-streamer/entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
