FROM alpine:3.22

RUN apk add --no-cache coreutils findutils bash

COPY services/recording-pruner/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
