#!/usr/bin/with-contenv bashio

cd /app
mkdir -p config/data/handle/home_assistant/
echo "${SUPERVISOR_TOKEN}" > config/data/handle/home_assistant/token

script/http_server --debug --server asr faster-whisper --server tts larynx2
