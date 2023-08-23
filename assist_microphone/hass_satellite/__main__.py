#!/usr/bin/env python3
import argparse
import asyncio
import logging
import shutil
import sys
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Deque, Optional, Tuple

import sounddevice as sd

from .mic import record
from .remote import stream
from .snd import play
from .vad import (
    SileroVoiceActivityDetector,
    VoiceActivityDetector,
    WebrtcVoiceActivityDetector,
)

_LOGGER = logging.getLogger(__name__)


class MicState(str, Enum):
    NOT_RECORDING = auto()
    WAIT_FOR_VAD = auto()
    RECORDING = auto()


@dataclass
class State:
    is_running: bool = True
    mic: MicState = MicState.NOT_RECORDING


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Home Assistant server host")
    parser.add_argument("token", help="Long-lived access token")
    parser.add_argument(
        "--port", type=int, help="Port for Home Assistant server", default=8123
    )
    parser.add_argument("--api-path", default="/api")
    parser.add_argument("--pipeline", help="Name of pipeline")
    parser.add_argument(
        "--protocol",
        default="http",
        choices=("http", "https"),
        help="Home Assistant protocol",
    )
    parser.add_argument("--device", help="Name/number of microphone/sound device")
    parser.add_argument("--mic-device", help="Name/number of microphone device")
    parser.add_argument("--snd-device", help="Name/number of sound device")
    #
    parser.add_argument(
        "--awake-sound", help="Audio file to play when wake word is detected"
    )
    parser.add_argument(
        "--done-sound", help="Audio file to play when voice command is done"
    )
    parser.add_argument(
        "--volume", type=float, default=1.0, help="Playback volume (0-1)"
    )
    #
    parser.add_argument("--vad", choices=("", "webrtcvad", "silero"))
    parser.add_argument(
        "--vad-mode", type=int, default=3, choices=(0, 1, 2, 3), help="Webrtcvad mode"
    )
    parser.add_argument("--vad-model", help="Path to Silero VAD onnx model (v4)")
    parser.add_argument("--vad-threshold", type=float, default=0.5)
    parser.add_argument("--vad-trigger-level", type=int, default=3)
    parser.add_argument("--vad-buffer-chunks", type=int, default=40)
    #
    parser.add_argument("--wake-buffer-seconds", type=float, default=0)
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to the console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    if args.vad == "silero":
        assert args.vad_model, "--vad-model required for silero"

    if not shutil.which("ffmpeg"):
        _LOGGER.fatal("Please install ffmpeg")
        sys.exit(1)

    for device in sd.query_devices():
        _LOGGER.debug(device)

    args.mic_device = args.mic_device or args.device
    args.snd_device = args.snd_device or args.device

    if args.mic_device:
        try:
            args.mic_device = int(args.mic_device)
        except ValueError:
            pass
    else:
        # Default device
        args.mic_device = None

    if args.snd_device:
        try:
            args.snd_device = int(args.snd_device)
        except ValueError:
            pass
    else:
        # Default device
        args.snd_device = None

    snd_device_info = sd.query_devices(device=args.snd_device, kind="output")
    snd_sample_rate = snd_device_info["default_samplerate"]

    loop = asyncio.get_running_loop()
    audio_queue: "asyncio.Queue[Tuple[int, bytes]]" = asyncio.Queue()
    speech_detected = asyncio.Event()
    state = State(mic=MicState.WAIT_FOR_VAD)

    # Recording thread for microphone
    mic_thread = threading.Thread(
        target=_mic_proc,
        args=(args, loop, audio_queue, speech_detected, state),
        daemon=True,
    )
    mic_thread.start()

    try:
        while True:
            try:
                if args.vad:
                    _LOGGER.debug("Waiting for speech")
                    await speech_detected.wait()
                    speech_detected.clear()
                    _LOGGER.debug("Speech detected")

                with sd.RawOutputStream(
                    device=args.snd_device,
                    samplerate=snd_sample_rate,
                    channels=1,
                    dtype="int16",
                ) as snd_stream:
                    async for _timestamp, event_type, event_data in stream(
                        host=args.host,
                        token=args.token,
                        audio=audio_queue,
                        pipeline_name=args.pipeline,
                        audio_seconds_to_buffer=args.wake_buffer_seconds,
                    ):
                        _LOGGER.debug("%s %s", event_type, event_data)

                        if event_type == "wake_word-end":
                            if args.awake_sound:
                                state.mic = MicState.NOT_RECORDING
                                play(
                                    media=args.awake_sound,
                                    stream=snd_stream,
                                    sample_rate=snd_sample_rate,
                                    volume=args.volume,
                                )
                                state.mic = MicState.RECORDING
                        elif event_type == "stt-end":
                            # Stop recording until run ends
                            state.mic = MicState.NOT_RECORDING
                            if args.done_sound:
                                play(
                                    media=args.done_sound,
                                    stream=snd_stream,
                                    sample_rate=snd_sample_rate,
                                    volume=args.volume,
                                )
                        elif event_type == "tts-end":
                            # Play TTS output
                            tts_url = event_data.get("tts_output", {}).get("url")
                            if tts_url:
                                play(
                                    media=f"{args.protocol}://{args.host}:{args.port}{tts_url}",
                                    stream=snd_stream,
                                    sample_rate=snd_sample_rate,
                                    volume=args.volume,
                                )
                        elif event_type in ("run-end", "error"):
                            # Start recording for next wake word
                            state.mic = MicState.WAIT_FOR_VAD
            except Exception:
                _LOGGER.exception("Unexpected error")
                state.mic = MicState.WAIT_FOR_VAD
    finally:
        state.is_running = False
        mic_thread.join()


# -----------------------------------------------------------------------------


def _mic_proc(
    args: argparse.ArgumentParser,
    loop: asyncio.AbstractEventLoop,
    audio_queue: "asyncio.Queue[Tuple[int, bytes]]",
    speech_detected: asyncio.Event,
    state: State,
) -> None:
    try:
        vad: Optional[VoiceActivityDetector] = None
        vad_activation: int = 0
        vad_chunk_buffer: Deque[Tuple[int, bytes]] = deque(
            maxlen=args.vad_buffer_chunks
        )
        if args.vad == "webrtcvad":
            vad = WebrtcVoiceActivityDetector(mode=args.vad_mode)
            _LOGGER.debug("Using webrtcvad")
        elif args.vad == "silero":
            vad = SileroVoiceActivityDetector(args.vad_model)
            _LOGGER.debug("Using silero VAD")
        else:
            _LOGGER.debug("No VAD")

        for ts_chunk in record(args.mic_device):
            if not state.is_running:
                break

            if state.mic == MicState.WAIT_FOR_VAD:
                if vad is None:
                    # No VAD
                    state.mic = MicState.RECORDING
                else:
                    _timestamp, chunk = ts_chunk
                    vad_prob = vad(chunk)
                    if vad_prob >= args.vad_threshold:
                        vad_activation += 1
                    else:
                        vad_activation = max(0, vad_activation - 1)

                    if vad_activation >= args.vad_trigger_level:
                        state.mic = MicState.RECORDING
                        speech_detected.set()
                        vad.reset()
                        vad_activation = 0
                    else:
                        vad_chunk_buffer.append(ts_chunk)

            if state.mic == MicState.RECORDING:
                if vad_chunk_buffer:
                    for buffered_chunk in vad_chunk_buffer:
                        loop.call_soon_threadsafe(
                            audio_queue.put_nowait, buffered_chunk
                        )

                    vad_chunk_buffer.clear()

                loop.call_soon_threadsafe(audio_queue.put_nowait, ts_chunk)
    except Exception:
        _LOGGER.exception("Unexpected error in _mic_proc")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
