ARG BUILD_FROM
FROM ${BUILD_FROM}
ARG BUILD_ARCH

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install snowboy
WORKDIR /usr/src
ARG WYOMING_SNOWBOY_VERSION
ARG SNOWMAN_ENROLL_VERSION

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        netcat-traditional \
        python3 \
        python3-pip \
        python3-dev \
        python3-venv \
        build-essential \
        swig \
        libatlas-base-dev \
        curl \
    && python3 -m venv .venv \
    && .venv/bin/pip3 install --no-cache-dir -U \
        setuptools \
        wheel \
    && .venv/bin/pip3 install --no-cache-dir \
        "wyoming-snowboy @ https://github.com/rhasspy/wyoming-snowboy/archive/refs/tags/v${WYOMING_SNOWBOY_VERSION}.tar.gz" \
    && ARCH="${BUILD_ARCH}" \
    && if [[ "${BUILD_ARCH}" = "aarch64" ]]; then ARCH="arm64"; fi \
    && curl --location --output - \
        "https://github.com/rhasspy/snowman-enroll/releases/download/v${SNOWMAN_ENROLL_VERSION}/snowman_enroll-${ARCH}.tar.gz" | \
        tar -xzf - \
    && apt-get remove --yes build-essential swig \
    && apt-get autoclean \
    && apt-get purge \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY src/train.py /usr/src/
COPY rootfs /

HEALTHCHECK --start-period=10m \
    CMD echo '{ "type": "describe" }' \
        | nc -w 1 localhost 10400 \
        | grep -iq "snowboy" \
        || exit 1
