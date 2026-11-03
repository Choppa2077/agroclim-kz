# syntax=docker/dockerfile:1

# Container image of agroclim.
#
#   docker build -t agroclim-kz .                         # runtime image (default target)
#   docker run --rm -p 8000:8000 agroclim-kz              # JSON API on http://localhost:8000
#   docker run --rm agroclim-kz recommend --crop wheat --precipitation 139 --humidity 55
#
# Stages:
#   build    builds the wheel and installs it into /opt/agroclim (pure Python, so it
#            runs on the build platform and is copied into images for every platform);
#   ci       the pinned toolchain (requirements-dev.txt) that Jenkins runs lint,
#            type checks and tests in;
#   runtime  the small non-root image that is pushed and deployed (last stage = default).

# Every stage uses the same base image, pinned by digest so that a rebuild gets
# the same bits; Dependabot proposes digest updates (.github/dependabot.yml).

FROM --platform=$BUILDPLATFORM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --no-deps --wheel-dir /dist . \
 && python -m pip install --no-deps --no-compile --target /opt/agroclim /dist/*.whl \
 && mkdir -p /data


FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS ci
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg
COPY requirements-dev.txt /tmp/requirements-dev.txt
RUN python -m pip install -r /tmp/requirements-dev.txt \
 && rm /tmp/requirements-dev.txt


FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS runtime
ARG VERSION=dev
ARG REVISION=unknown
ARG CREATED=unknown
LABEL org.opencontainers.image.title="agroclim" \
      org.opencontainers.image.description="Planting-date decision support for rainfed crops in Northern Kazakhstan" \
      org.opencontainers.image.url="https://github.com/Choppa2077/agroclim-kz" \
      org.opencontainers.image.source="https://github.com/Choppa2077/agroclim-kz" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.authors="Mukan Idrissov" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.created="${CREATED}"
ENV PYTHONPATH=/opt/agroclim \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# No RUN instruction in this stage: nothing executes on the target platform,
# so building the arm64 and amd64 variants needs no emulation.
COPY --from=build /opt/agroclim /opt/agroclim
COPY --from=build --chown=10001:10001 /data /data
WORKDIR /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
ENTRYPOINT ["python", "-m", "agroclim"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
