#!/usr/bin/env python3

import argparse
import asyncio
import logging
import time
import re
from dataclasses import dataclass, field
from functools import partial
from typing import List, Optional, Set, Dict, Union, Tuple

import aiohttp
from wyoming.asr import Transcript, Transcribe
from wyoming.audio import AudioChunk, AudioStop
from wyoming.client import AsyncClient
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncServer

_LOGGER = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"


@dataclass
class STTEntity:
    entity_id: str
    supported_languages: Set[str]

    _supported_lang_map: Dict[Tuple[str, Union[str, None]], str] = field(
        default_factory=dict
    )
    _language_map: Dict[str, str] = field(default_factory=dict)

    def get_best_language(self, language: str) -> Optional[str]:
        language = language.strip()

        if language in self.supported_languages:
            return language

        best_language = self._language_map.get(language)
        if best_language is not None:
            return best_language

        if not self._supported_lang_map:
            # {(family, region): language}
            for supported_lang in self.supported_languages:
                supported_lang_parts = re.split(r"[-_]", supported_lang)
                supported_lang_family = supported_lang_parts[0].lower()
                supported_lang_region = (
                    supported_lang_parts[1].upper()
                    if len(supported_lang_parts) > 1
                    else None
                )

                self._supported_lang_map[
                    (supported_lang_family, supported_lang_region)
                ] = supported_lang

        language_parts = re.split(r"[-_]", language)
        lang_family = language_parts[0].lower()
        lang_region = language_parts[1].upper() if len(language_parts) > 1 else None

        # Exact match
        best_language = self._supported_lang_map.get((lang_family, lang_region))

        if best_language is None:
            # Special cases
            if (lang_family == "en") and (lang_region is None):
                best_language = self._supported_lang_map.get(("en", "US"))

        if best_language is None:
            # Family only
            best_language = self._supported_lang_map.get((lang_family, None))

        if best_language is not None:
            self._language_map[language] = best_language
            return best_language

        return None


async def get_entity_info_with_retries(
    session: aiohttp.ClientSession,
    url: str,
    headers: Dict[str, str],
    max_attempts: int = 8,
    delay_seconds: int = 5,
) -> Optional[Dict]:
    """
    Gets entities and retries on 404
    """
    for attempt in range(1, max_attempts + 1):
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()

                if resp.status == 404:
                    _LOGGER.warning(
                        "Entity not found (404) at %s — attempt %d/%d",
                        url,
                        attempt,
                        max_attempts,
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(delay_seconds)
                        continue
                    _LOGGER.warning(
                        "Giving up after %d attempts for %s (404)", max_attempts, url
                    )
                    return None

                _LOGGER.warning("Failed to get entity info: %s, status=%s", url, resp.status)
                return None
        except Exception:
            _LOGGER.exception("Error fetching entity info from %s", url)
            return None

    return None


async def main() -> None:
    """Runs fallback ASR server."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True, help="unix:// or tcp://")
    parser.add_argument(
        "--hass-token", required=True, help="Long-lived access token for Home Assistant"
    )
    parser.add_argument(
        "--hass-http-uri",
        default="http://homeassistant.local:8123/api",
        help="URI of Home Assistant HTTP API",
    )
    parser.add_argument(
        "stt_entity_id",
        nargs="+",
        help="Ids of speech-to-text entities in fallback order",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    # Get STT entity info
    entities: List[STTEntity] = []
    headers = {"Authorization": f"Bearer {args.hass_token}"}
    async with aiohttp.ClientSession() as session:
        for entity_id in args.stt_entity_id:
            _LOGGER.debug("Getting info for STT entity: %s", entity_id)

            info = await get_entity_info_with_retries(session, f"{args.hass_http_uri}/stt/{entity_id}", headers)

            if info is None:
                continue

            # Check required audio format
            if (
                (16000 not in info["sample_rates"])
                or (16 not in info["bit_rates"])
                or (1 not in info["channels"])
                or ("wav" not in info["formats"])
                or ("pcm" not in info["codecs"])
            ):
                _LOGGER.warning(
                    "Skipping '%s': 16Khz 16-bit mono PCM is not supported",
                    entity_id,
                )
                _LOGGER.warning("%s: %s", entity_id, info)
                continue

            entities.append(
                STTEntity(
                    entity_id=entity_id,
                    supported_languages=set(info["languages"]),
                )
            )

    _LOGGER.debug("Entities: %s", entities)

    server = AsyncServer.from_uri(args.uri)
    _LOGGER.info("Ready")

    try:
        await server.run(
            partial(FallbackEventHandler, entities, args.hass_token, args.hass_http_uri)
        )
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


class FallbackEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        entities: List[STTEntity],
        hass_token: str,
        hass_http_uri: str,
        *args,
        **kwargs,
    ) -> None:
        """Initialize event handler."""
        super().__init__(*args, **kwargs)

        self.entities = entities
        self.hass_token = hass_token
        self.hass_http_uri = hass_http_uri
        self.client_id = str(time.monotonic_ns())

        self._language = DEFAULT_LANGUAGE

        self._audio_queue: asyncio.Queue[Union[bytes, None]] = asyncio.Queue()
        self._target_write_task: Optional[asyncio.Task] = None
        self._saved_audio_chunks: List[bytes] = []
        self._session: Optional[aiohttp.ClientSession] = None

        self._info_event: Optional[Event] = None

    async def handle_event(self, event: Event) -> bool:
        """Handle Wyoming event."""
        try:
            if Describe.is_type(event.type):
                await self._write_info()
                return True

            if AudioChunk.is_type(event.type):
                if self._target_write_task is None:
                    # First target
                    self._target_write_task = asyncio.create_task(
                        self._write_audio(target_idx=0)
                    )

                chunk = AudioChunk.from_event(event)
                self._audio_queue.put_nowait(chunk.audio)
                self._saved_audio_chunks.append(chunk.audio)
            elif AudioStop.is_type(event.type):
                self._audio_queue.put_nowait(None)
                if self._target_write_task is not None:
                    await self._target_write_task

                # Reset
                self._target_write_task = None
                self._language = DEFAULT_LANGUAGE
                self._saved_audio_chunks = []
                self._audio_queue = asyncio.Queue()

                if self._session is not None:
                    await self._session.close()
                    self._session = None
            elif Transcribe.is_type(event.type):
                transcribe = Transcribe.from_event(event)
                self._language = transcribe.language or DEFAULT_LANGUAGE

        except Exception:
            _LOGGER.exception("Error handling event")

        return True

    async def _write_audio(self, target_idx: int):
        if target_idx >= len(self.entities):
            await self._write_empty_transcript()
            return

        target_entity = self.entities[target_idx]
        target_language = target_entity.get_best_language(self._language)
        while target_language is None:
            # Find the next target that supports the desired language
            target_idx += 1
            if target_idx >= len(self.entities):
                # No targets support language
                await self._write_empty_transcript()
                return

            target_entity = self.entities[target_idx]
            target_language = target_entity.get_best_language(self._language)

        _LOGGER.debug(
            "Trying entity %s with language %s",
            target_entity.entity_id,
            target_language,
        )

        headers = {
            "Authorization": f"Bearer {self.hass_token}",
            "Content-Type": "audio/wav",
            "X-Speech-Content": f"language={target_language};format=wav;codec=pcm;bit_rate=16;sample_rate=16000;channel=1",
        }

        async def audio_stream():
            while True:
                chunk = await self._audio_queue.get()
                if chunk is None:
                    break

                yield chunk

        transcript = ""

        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()

            async with self._session.post(
                f"{self.hass_http_uri}/stt/{target_entity.entity_id}",
                headers=headers,
                data=audio_stream(),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    _LOGGER.debug("Result from %s: %s", target_entity.entity_id, result)
                    transcript = result.get("text", "").strip()
        except Exception:
            _LOGGER.exception("Error writing audio")
        finally:
            if transcript:
                _LOGGER.debug("Transcript: %s", transcript)
                await self.write_event(Transcript(text=transcript).event())
            else:
                # Fall back
                self._audio_queue = asyncio.Queue()
                for chunk in self._saved_audio_chunks:
                    # Refill audio queue for next target
                    self._audio_queue.put_nowait(chunk)

                self._audio_queue.put_nowait(None)

                # Next target
                await self._write_audio(target_idx + 1)

    async def _write_empty_transcript(self) -> None:
        await self.write_event(Transcript(text="").event())

    async def _write_info(self) -> None:
        if self._info_event is not None:
            await self.write_event(self._info_event)
            return

        supported_langs: Set[str] = set()

        for entity in self.entities:
            supported_langs.update(entity.supported_languages)

        info = Info(
            asr=[
                AsrProgram(
                    name="stt-fallback",
                    attribution=Attribution(
                        name="The Home Assistant Authors",
                        url="http://github.com/OHF-voice",
                    ),
                    description="Automatic fallback for Home Assistant speech-to-text",
                    installed=True,
                    version="1.0.0",
                    models=[
                        AsrModel(
                            name="fallback",
                            attribution=Attribution(
                                name="The Home Assistant Authors",
                                url="http://github.com/OHF-voice",
                            ),
                            installed=True,
                            description="Fallback model",
                            version=None,
                            languages=list(sorted(supported_langs)),
                        )
                    ],
                )
            ]
        )

        self._info_event = info.event()
        await self.write_event(self._info_event)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
