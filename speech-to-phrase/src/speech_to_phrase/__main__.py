"""Wyoming server."""

import argparse
import asyncio
import logging
from functools import partial
from pathlib import Path

from wyoming.server import AsyncServer

from .const import Settings
from .event_handler import SpeechToPhraseEventHandler
from .hass_api import get_exposed_things
from .models import MODELS
from .train import train

_LOGGER = logging.getLogger()


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="stdio://", help="unix:// or tcp://")
    parser.add_argument(
        "--train-dir", required=True, help="Directory to write trained model files"
    )
    parser.add_argument(
        "--tools-dir", required=True, help="Directory with kaldi, openfst, etc."
    )
    parser.add_argument(
        "--models-dir", required=True, help="Directory with speech models"
    )
    # Home Assistant
    parser.add_argument(
        "--hass-token", required=True, help="Long-lived access token for Home Assistant"
    )
    parser.add_argument(
        "--hass-websocket-uri",
        default="ws://homeassistant.local:8123/api/websocket",
        help="URI of Home Assistant websocket API",
    )
    # Audio
    parser.add_argument("--volume-multiplier", type=float, default=1.0)
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    settings = Settings(
        models_dir=Path(args.models_dir),
        train_dir=Path(args.train_dir),
        tools_dir=Path(args.tools_dir),
    )

    # Train
    _LOGGER.info("Training started")

    _LOGGER.debug(
        "Getting exposed things from Home Assistant (%s)", args.hass_websocket_uri
    )
    things = await get_exposed_things(
        token=args.hass_token, uri=args.hass_websocket_uri
    )
    _LOGGER.debug(
        "Got %s entities, %s area(s), %s floor(s), %s trigger sentence(s)",
        len(things.entities),
        len(things.areas),
        len(things.floors),
        len(things.trigger_sentences),
    )

    for model in MODELS.values():
        model_dir = settings.models_dir / model.id
        if not model_dir.exists():
            continue

        _LOGGER.debug("Training speech model: %s", model.id)
        await train(model, settings, things)

    _LOGGER.info("Training completed successfully")

    # Run server
    wyoming_server = AsyncServer.from_uri(args.uri)

    _LOGGER.info("Ready")

    try:
        await wyoming_server.run(
            partial(SpeechToPhraseEventHandler, settings, args.volume_multiplier)
        )
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
