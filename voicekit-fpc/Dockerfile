ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        python3

COPY ./server.py /app/server.py

EXPOSE 11223

ENTRYPOINT ["python3", "/app/server.py", "--output-dir", "/share/voicekit-fpc"]
