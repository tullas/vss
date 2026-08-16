FROM golang@sha256:e401dae1bf814e29204a8cb7915682e1780951e609ca0dd8865ee1937f510c48 AS build

ARG SOURCE_DATE_EPOCH=1784082912
ENV CGO_ENABLED=0

ADD --checksum=sha256:7e63315ced171ced2dc32482e8c2916121bdf77a63c0ef3e3124d6b5e1b2201a \
    https://github.com/versity/versitygw/archive/refs/tags/v1.7.0.tar.gz /tmp/versitygw.tar.gz
RUN mkdir /src && tar -xzf /tmp/versitygw.tar.gz -C /src --strip-components=1
WORKDIR /src/cmd/versitygw
RUN go build -trimpath -buildvcs=false \
    -ldflags '-buildid= -X=main.Build=8a3dbcf97d996ea4955426e6b8a76eb96d2cd92a -X=main.BuildTime=2026-07-15T02:35:12Z -X=main.Version=v1.7.0-vss-go1.25.13' \
    -o /out/versitygw .

FROM alpine@sha256:79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f

LABEL org.opencontainers.image.title="VSS-maintained VersityGW"
LABEL org.opencontainers.image.description="VersityGW v1.7.0 rebuilt with the patched Go 1.25.13 toolchain for bounded VSS local S3 acceptance"
LABEL org.opencontainers.image.source="https://github.com/tullas/vss"
LABEL org.opencontainers.image.url="https://github.com/tullas/vss"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.version="v1.7.0-go1.25.13-r1"
LABEL dev.vss.upstream.source="https://github.com/versity/versitygw/archive/refs/tags/v1.7.0.tar.gz"
LABEL dev.vss.go.toolchain="go1.25.13"

COPY --from=build /out/versitygw /usr/local/bin/versitygw
COPY --from=build /src/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY --from=build /src/LICENSE /usr/share/licenses/versitygw/LICENSE
RUN chmod 0755 /usr/local/bin/versitygw /usr/local/bin/docker-entrypoint.sh

USER 65532:65532
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
