#!/usr/bin/env bash

APP_DIR='/app'

cd "${APP_DIR}"

.venv/bin/python3 -m larynx serve \
        --model 'voice/tts/de-thorsten_tts-v1.pth.tar' \
        --vocoder-model 'voice/vocoder/de-thorsten_vocoder-v1.pth.tar' \
        --cache-dir '/cache'
