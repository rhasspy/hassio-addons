"""Home Assistant API."""

import logging
from dataclasses import dataclass, field
from typing import List

import aiohttp

_LOGGER = logging.getLogger(__name__)


@dataclass
class Entity:
    names: List[str]
    domain: str


@dataclass
class Area:
    names: List[str]


@dataclass
class Floor:
    names: List[str]


@dataclass
class Things:
    entities: List[Entity] = field(default_factory=list)
    areas: List[Area] = field(default_factory=list)
    floors: List[Floor] = field(default_factory=list)
    trigger_sentences: List[str] = field(default_factory=list)


async def get_exposed_things(token: str, uri: str) -> Things:
    """Use HA websocket API to get exposed entities/areas/floors."""
    things = Things()

    current_id = 0

    def next_id() -> int:
        nonlocal current_id
        current_id += 1
        return current_id

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(uri) as websocket:
            # Authenticate
            msg = await websocket.receive_json()
            assert msg["type"] == "auth_required", msg

            await websocket.send_json(
                {
                    "type": "auth",
                    "access_token": token,
                }
            )

            msg = await websocket.receive_json()
            assert msg["type"] == "auth_ok", msg

            await websocket.send_json(
                {"id": next_id(), "type": "homeassistant/expose_entity/list"}
            )

            msg = await websocket.receive_json()
            assert msg["success"], msg

            entity_ids = []
            for entity_id, exposed_info in msg["result"]["exposed_entities"].items():
                if exposed_info.get("conversation"):
                    entity_ids.append(entity_id)

            await websocket.send_json(
                {
                    "id": next_id(),
                    "type": "get_states",
                }
            )
            msg = await websocket.receive_json()
            assert msg["success"], msg
            states = {s["entity_id"]: s for s in msg["result"]}

            # Get device info
            await websocket.send_json(
                {"id": next_id(), "type": "config/device_registry/list"}
            )
            msg = await websocket.receive_json()
            assert msg["success"], msg
            # devices = {device_info["id"]: device_info for device_info in msg["result"]}

            # Floors
            await websocket.send_json(
                {"id": next_id(), "type": "config/floor_registry/list"}
            )
            msg = await websocket.receive_json()
            assert msg["success"], msg
            floors = {
                floor_info["floor_id"]: floor_info for floor_info in msg["result"]
            }
            for floor_info in floors.values():
                names = [floor_info["name"]]
                names.extend(floor_info.get("aliases", []))
                things.floors.append(Floor(names=[name.strip() for name in names]))

            # Areas
            await websocket.send_json(
                {"id": next_id(), "type": "config/area_registry/list"}
            )
            msg = await websocket.receive_json()
            assert msg["success"], msg
            areas = {area_info["area_id"]: area_info for area_info in msg["result"]}
            for area_info in areas.values():
                names = [area_info["name"]]
                names.extend(area_info.get("aliases", []))
                things.areas.append(Area(names=[name.strip() for name in names]))

            # Contains aliases
            # Check area_id as well as area of device_id
            # Use original_device_class
            await websocket.send_json(
                {
                    "id": next_id(),
                    "type": "config/entity_registry/get_entries",
                    "entity_ids": entity_ids,
                }
            )

            msg = await websocket.receive_json()
            assert msg["success"], msg
            for entity_id, entity_info in msg["result"].items():
                domain = entity_id.split(".")[0]
                name = None
                names = []

                if entity_info:
                    if entity_info.get("disabled_by") is not None:
                        # Skip disabled entities
                        continue

                    name = entity_info.get("name") or entity_info["original_name"]
                    names.extend(entity_info.get("aliases", []))

                if (not name) and (entity_id in states):
                    name = states[entity_id]["attributes"].get("friendly_name")

                if name:
                    names.append(name)

                things.entities.append(
                    Entity(names=[name.strip() for name in names], domain=domain)
                )

            # Get sentences from sentence triggers
            await websocket.send_json(
                {"id": next_id(), "type": "conversation/sentences/list"}
            )
            msg = await websocket.receive_json()
            if msg["success"]:
                things.trigger_sentences.extend(msg["result"]["trigger_sentences"])

    return things
