import logging
from typing import Any, Dict

import aiohttp

_LOGGER = logging.getLogger(__name__)


async def get_exposed_dict(token: str, uri: str) -> Dict[str, Any]:
    current_id = 0

    def next_id() -> int:
        nonlocal current_id
        current_id += 1
        return current_id

    name_list = []
    area_list = []
    floor_list = []
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
            assert msg["success"]

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
            assert msg["success"]
            states = {s["entity_id"]: s for s in msg["result"]}

            # Get device info
            await websocket.send_json(
                {"id": next_id(), "type": "config/device_registry/list"}
            )
            msg = await websocket.receive_json()
            assert msg["success"]
            # devices = {device_info["id"]: device_info for device_info in msg["result"]}

            # Floors
            await websocket.send_json(
                {"id": next_id(), "type": "config/floor_registry/list"}
            )
            msg = await websocket.receive_json()
            assert msg["success"]
            floors = {
                floor_info["floor_id"]: floor_info for floor_info in msg["result"]
            }
            for _floor_id, floor_info in floors.items():
                names = [floor_info["name"]]
                names.extend(floor_info.get("aliases", []))

                for name in names:
                    # floor_list.append(
                    #     {"in": name, "context": {"floor_id": floor_id}}
                    # )
                    floor_list.append(name)

            # Areas
            await websocket.send_json(
                {"id": next_id(), "type": "config/area_registry/list"}
            )
            msg = await websocket.receive_json()
            assert msg["success"]
            areas = {area_info["area_id"]: area_info for area_info in msg["result"]}
            for _area_id, area_info in areas.items():
                names = [area_info["name"]]
                names.extend(area_info.get("aliases", []))

                # context = {"area_id": area_id}
                # floor = area_info.get("floor_id")
                # if floor:
                #     context["floor"] = floor

                for name in names:
                    # area_list.append({"in": name, "context": context})
                    area_list.append(name)

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
            assert msg["success"]
            for entity_id, entity_info in msg["result"].items():
                domain = entity_id.split(".")[0]
                name = None
                names = []
                # area = None

                if entity_info:
                    name = entity_info.get("name") or entity_info["original_name"]
                    names.extend(entity_info.get("aliases", []))

                    # device_info = devices.get(entity_info.get("device_id"), {})
                    # area = device_info.get("area_id", entity_info.get("area_id"))

                if (not name) and (entity_id in states):
                    name = states[entity_id]["attributes"].get("friendly_name")

                if name:
                    names.append(name)

                for name in names:
                    name = name.strip()
                    context = {"domain": domain}
                    # context = {"domain": domain, "entity_id": entity_id}
                    # if area:
                    #     context["area"] = area
                    #     floor = areas.get(area, {}).get("floor_id")
                    #     if floor:
                    #         context["floor"] = floor

                    name_list.append({"in": name, "context": context})

    output_dict = {}
    if name_list:
        output_dict["name"] = {"values": name_list}

    if area_list:
        output_dict["area"] = {"values": area_list}

    if floor_list:
        output_dict["floor"] = {"values": floor_list}

    return output_dict
