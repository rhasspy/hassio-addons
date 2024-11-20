ARG BUILD_FROM
FROM ${BUILD_FROM}
ARG BUILD_ARCH

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install rhasspy-speech
WORKDIR /usr/src
ARG RHASSPY_SPEECH_VERSION
ARG WYOMING_RHASSPY_SPEECH_VERSION

RUN mkdir -p ./tools

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        netcat-traditional \
        python3 \
        python3-pip \
        python3-dev \
        python3-venv \
        build-essential \
        curl \
        libopenblas0 \
        libencode-perl \
    && ARCH="${BUILD_ARCH}" \
    && if [[ "${BUILD_ARCH}" = "aarch64" ]]; then ARCH="arm64"; fi \
    && curl --location --output - \
        "https://huggingface.co/datasets/rhasspy/rhasspy-speech/resolve/main/tools/rhasspy-speech_${ARCH}.tar.gz?download=true" | \
        tar -C ./tools -xzf - \
    && python3 -m venv .venv \
    && .venv/bin/pip3 install --no-cache-dir -U \
        setuptools \
        wheel \
    && .venv/bin/pip3 install --no-cache-dir \
        "rhasspy-speech @ https://github.com/rhasspy/rhasspy-speech/archive/refs/tags/v${RHASSPY_SPEECH_VERSION}.tar.gz" \
        "wyoming-rhasspy-speech @ https://github.com/rhasspy/wyoming-rhasspy-speech/archive/refs/tags/v${WYOMING_RHASSPY_SPEECH_VERSION}.tar.gz" \
    && apt-get remove --yes build-essential \
    && apt-get autoclean \
    && apt-get purge \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY rootfs /

HEALTHCHECK --start-period=10m \
    CMD echo '{ "type": "describe" }' \
        | nc -w 1 localhost 10300 \
        | grep -iq "rhasspy-speech" \
        || exit 1
