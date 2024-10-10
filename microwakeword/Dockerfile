ARG BUILD_FROM
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install microWakeWord
WORKDIR /usr/src
ENV WYOMING_MICROWAKEWORD_VERSION=1.0.0

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        netcat-traditional \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
    \
    && python3 -m venv .venv \
    && .venv/bin/pip3 install --no-cache-dir -U \
        setuptools \
        wheel \
    && .venv/bin/pip3 install --no-cache-dir \
        --extra-index-url https://www.piwheels.org/simple \
        "wyoming-microwakeword @ https://github.com/rhasspy/wyoming-microwakeword/archive/refs/tags/${WYOMING_MICROWAKEWORD_VERSION}.tar.gz" \
    \
    && apt-get remove --yes build-essential \
    && apt-get autoclean \
    && apt-get purge \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY rootfs /

HEALTHCHECK --start-period=10m \
    CMD echo '{ "type": "describe" }' \
        | nc -w 1 localhost 10400 \
        | grep -iq "microwakeword" \
        || exit 1
