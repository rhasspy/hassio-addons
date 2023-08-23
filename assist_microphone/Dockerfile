ARG BUILD_FROM
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /usr/src
ENV PIP_BREAK_SYSTEM_PACKAGES=1

COPY requirements.txt ./
COPY hass_satellite/ ./hass_satellite/

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libasound2-plugins \
        libportaudio2 \
        ffmpeg \
        python3 \
        python3-pip \
        python3-dev \
    \
    && pip3 install --no-cache-dir -U \
        setuptools \
        wheel \
    && pip3 install --no-cache-dir \
        -r requirements.txt \
    \
    && apt-get remove --yes build-essential python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY sounds/ ./sounds/
COPY models/ ./models/

WORKDIR /
COPY rootfs /
