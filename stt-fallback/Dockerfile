ARG BUILD_FROM
FROM ${BUILD_FROM}
ARG BUILD_ARCH

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install
WORKDIR /usr/src
ENV PIP_BREAK_SYSTEM_PACKAGES=1

COPY requirements.txt src/stt_fallback.py ./

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        netcat-traditional \
        python3 \
        python3-pip \
    && pip3 install --no-cache-dir -U \
        setuptools \
        wheel \
    && pip3 install --no-cache-dir -r ./requirements.txt \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY rootfs /

HEALTHCHECK --start-period=10m \
    CMD echo '{ "type": "describe" }' \
        | nc -w 1 localhost 10300 \
        | grep -iq "stt-fallback" \
        || exit 1
