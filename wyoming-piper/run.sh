#!/usr/bin/with-contenv bashio

cd /app
.venv/bin/python3 src/piper_server.py \
    data/en-us-ryan-low.onnx \
    --uri 'tcp://0.0.0.0:10200' "$@"
