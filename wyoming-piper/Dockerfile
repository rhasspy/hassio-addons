FROM python:3.9-bullseye as build

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
      python3-dev python3-venv build-essential

WORKDIR /app

COPY src/ ./src/

# Install faster-whisper
RUN python3 -m venv .venv && \
    .venv/bin/pip3 install --upgrade pip && \
    .venv/bin/pip3 install --upgrade wheel setuptools

RUN .venv/bin/pip3 install src/wyoming-0.0.1.tar.gz

# -----------------------------------------------------------------------------

FROM python:3.9-slim-bullseye
ARG TARGETARCH
ARG TARGETVARIANT

COPY --from=build /app/.venv/ /app/.venv/

ADD dist/piper_${TARGETARCH}${TARGETVARIANT}.tar.gz /app/

COPY data/ /app/data/
COPY src/piper_server.py /app/src/
RUN mv /app/piper/* /app/src/

COPY run.sh /app/
RUN chmod a+x /app/run.sh

# TCP
EXPOSE 10200

ENTRYPOINT ["bash", "/app/run.sh"]
