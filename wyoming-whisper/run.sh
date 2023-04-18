#!/usr/bin/with-contenv bashio

cd /app
.venv/bin/python3 src/faster-whisper/bin/faster_whisper_server.py \
    data/tiny-int8/ \
    --uri 'tcp://0.0.0.0:10300' "$@"
