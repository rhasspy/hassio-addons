#!/usr/bin/env bash

APP_DIR='/app'

cd "${APP_DIR}"

.venv/bin/python3 -m larynx serve \
        --model 'voice/tts/es-css10_tts-v1.pth.tar' \
        --vocoder-model 'voice/vocoder/es-css10_vocoder-v1.pth.tar' \
        --cache-dir '/cache'
