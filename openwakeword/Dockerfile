ARG BUILD_FROM
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install openWakeWord
WORKDIR /usr/src
ARG OPENWAKEWORD_LIB_VERSION

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        netcat-traditional \
        python3 \
        python3-pip \
        python3-venv \
    \
    && python3 -m venv ./venv \
    && ./venv/bin/pip3 install --no-cache-dir -U \
        setuptools \
        wheel \
    && ./venv/bin/pip3 install --no-cache-dir \
        "wyoming-openwakeword==${OPENWAKEWORD_LIB_VERSION}" \
        'speexdsp-ns==0.1.2' \
    \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY rootfs /

HEALTHCHECK --start-period=10m \
    CMD echo '{ "type": "describe" }' \
        | nc -w 1 localhost 10400 \
        | grep -iq "openWakeWord" \
        || exit 1
