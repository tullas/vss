FROM docker.io/library/ubuntu@sha256:889d056d5c6c0bfb55789ff3710681d68e50713cb562d2196dc07110599c7a6f

ARG SOURCE_DATE_EPOCH=1786957365

RUN rm --force /usr/bin/pebble \
    && test ! -e /usr/bin/pebble

LABEL org.opencontainers.image.title="VSS Ubuntu 26.04 acceptance environment"
LABEL org.opencontainers.image.description="Acceptance-only Ubuntu 26.04 derivative without the unused Pebble service manager"
LABEL org.opencontainers.image.source="https://github.com/tullas/vss"
LABEL org.opencontainers.image.url="https://github.com/tullas/vss"
LABEL org.opencontainers.image.licenses="NOASSERTION"
LABEL org.opencontainers.image.version="26.04-2026-08-17-no-pebble-r1"
LABEL dev.vss.upstream.source="docker.io/library/ubuntu@sha256:889d056d5c6c0bfb55789ff3710681d68e50713cb562d2196dc07110599c7a6f"
LABEL dev.vss.removed.component="/usr/bin/pebble"
