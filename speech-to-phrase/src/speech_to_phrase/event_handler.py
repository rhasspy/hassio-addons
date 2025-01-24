"""Wyoming event handler."""

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterable
from typing import Optional

from pysilero_vad import SileroVoiceActivityDetector
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler

from .audio import multiply_volume, vad_audio_stream
from .const import CHANNELS, RATE, WIDTH, Language, Settings
from .models import MODELS, Model
from .transcribe import transcribe

_LOGGER = logging.getLogger()

DEFAULT_MODEL = MODELS[Language.ENGLISH]
INFO = Info(
    asr=[
        AsrProgram(
            name="speech-to-phrase",
            attribution=Attribution(
                name="The Home Assistant Authors",
                url="http://github.com/OHF-voice/speech-to-phrase",
            ),
            description="Fast but limited speech-to-text",
            installed=True,
            version="0.0.1",
            models=[
                AsrModel(
                    name=model.id,
                    description=model.description,
                    languages=[language],
                    attribution=Attribution(name=model.author, url=model.url),
                    installed=True,
                    version=model.version,
                )
                for language, model in MODELS.items()
            ],
        )
    ]
)


class SpeechToPhraseEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        settings: Settings,
        volume_multiplier: float,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.settings = settings
        self.volume_multiplier = volume_multiplier

        self.client_id = str(time.monotonic_ns())
        self.converter = AudioChunkConverter(rate=RATE, width=WIDTH, channels=CHANNELS)
        self.vad = SileroVoiceActivityDetector()

        self.audio_queue: "asyncio.Queue[Optional[bytes]]" = asyncio.Queue()
        self.transcribe_task: Optional[asyncio.Task] = None
        self.model = DEFAULT_MODEL

    async def handle_event(self, event: Event) -> bool:
        if AudioChunk.is_type(event.type):
            # Add audio chunk to queue
            chunk = AudioChunk.from_event(event)
            chunk = self.converter.convert(chunk)
            await self.audio_queue.put(chunk.audio)
            return True

        if Transcribe.is_type(event.type):
            # Select model
            self.model = DEFAULT_MODEL

            transcribe_event = Transcribe.from_event(event)

            model: Optional[Model]
            if transcribe_event.name:
                for model in MODELS.values():
                    if model.id == transcribe_event.name:
                        self.model = model
                        _LOGGER.debug("Selected model by name: %s", model.id)
                        break

            elif transcribe_event.language:
                model = MODELS.get(transcribe_event.language)
                if model is None:
                    language_family = re.split(r"[-_]", transcribe_event.language)[0]
                    model = MODELS.get(language_family)

                if model is not None:
                    self.model = model
                    _LOGGER.debug("Selected model by language: %s", model.id)

        if AudioStart.is_type(event.type):
            # Begin transcription
            if self.transcribe_task is not None:
                self.transcribe_task.cancel()
                self.transcribe_task = None

            self.audio_queue = asyncio.Queue()
            self.transcribe_task = asyncio.create_task(
                transcribe(
                    self.model,
                    self.settings,
                    vad_audio_stream(self._audio_stream(), self.vad),
                )
            )
            return True

        if AudioStop.is_type(event.type):
            # End transcription
            assert self.transcribe_task is not None

            start_time = time.monotonic()
            await self.audio_queue.put(None)  # end stream
            text = await self.transcribe_task

            _LOGGER.debug(
                "Got transcription in %s second(s): %s",
                time.monotonic() - start_time,
                text,
            )
            self.transcribe_task = None

            await self.write_event(Transcript(text=text).event())

            return True

        if Describe.is_type(event.type):
            await self.write_event(INFO.event())
            return True

        _LOGGER.debug("Unexpected event: type=%s, data=%s", event.type, event.data)

        return True

    async def disconnect(self) -> None:
        """Handle disconnection"""

    async def _audio_stream(self) -> AsyncIterable[bytes]:
        while True:
            chunk = await self.audio_queue.get()
            if chunk is None:
                break

            if self.volume_multiplier != 1.0:
                chunk = multiply_volume(chunk, self.volume_multiplier)

            yield chunk
