"""Audio utilities."""

import array
import wave
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Union

from pyring_buffer import RingBuffer
from pysilero_vad import SileroVoiceActivityDetector

from .const import CHANNELS, RATE, WIDTH

SECONDS_BEFORE_SPEECH = 0.5
VAD_THRESHOLD = 0.5


async def vad_audio_stream(
    audio_stream: AsyncIterable[bytes], vad: SileroVoiceActivityDetector
) -> AsyncIterable[bytes]:
    """Stream audio after speech is detected."""
    vad.reset()

    # Keep some audio before speech is detected
    before_speech = RingBuffer(int(SECONDS_BEFORE_SPEECH * RATE * WIDTH * CHANNELS))

    vad_buffer = bytes()
    in_speech = False
    async for chunk in audio_stream:
        vad_buffer += chunk
        if len(vad_buffer) < vad.chunk_bytes():
            continue

        vad_buffer_idx = 0
        while (vad_buffer_idx + vad.chunk_bytes()) < len(vad_buffer):
            vad_chunk = vad_buffer[vad_buffer_idx : vad_buffer_idx + vad.chunk_bytes()]
            vad_buffer_idx += vad.chunk_bytes()

            if (not in_speech) and (vad.process_chunk(vad_chunk) > VAD_THRESHOLD):
                in_speech = True
                yield before_speech.getvalue()

            if in_speech:
                yield vad_chunk
            else:
                before_speech.put(vad_chunk)

        vad_buffer = vad_buffer[vad_buffer_idx:]


async def wav_audio_stream(
    wav_path: Union[str, Path], vad: SileroVoiceActivityDetector
) -> AsyncIterable[bytes]:
    """Stream WAV audio after speech is detected."""
    vad.reset()

    # Keep some audio before speech is detected
    before_speech = RingBuffer(int(SECONDS_BEFORE_SPEECH * RATE * WIDTH * CHANNELS))

    with wave.open(str(wav_path), "rb") as wav_file:
        assert wav_file.getframerate() == RATE
        assert wav_file.getsampwidth() == WIDTH
        assert wav_file.getnchannels() == CHANNELS

        in_speech = False
        while True:
            chunk = wav_file.readframes(vad.chunk_samples())
            if not chunk:
                break

            if (not in_speech) and (vad.process_chunk(chunk) > VAD_THRESHOLD):
                in_speech = True
                yield before_speech.getvalue()

            if in_speech:
                yield chunk
            else:
                before_speech.put(chunk)


def multiply_volume(chunk: bytes, volume_multiplier: float) -> bytes:
    """Multiplies 16-bit PCM samples by a constant."""
    return array.array(
        "h",
        (int(_clamp(value * volume_multiplier)) for value in array.array("h", chunk)),
    ).tobytes()


def _clamp(val: float) -> float:
    """Clamp to signed 16-bit."""
    return max(-32768, min(32767, val))
