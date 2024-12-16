import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rhasspy_speech.const import LangSuffix


@dataclass
class AppSettings:
    train_dir: Path
    tools_dir: Path
    models_dir: Path

    volume_multiplier: float

    # VAD
    vad_enabled: bool
    vad_threshold: float
    before_speech_seconds: float

    # Speex
    speex_enabled: bool
    speex_noise_suppression: int
    speex_auto_gain: int

    # Edit distance
    max_fuzzy_cost: float

    # Transcribers
    max_active: int
    lattice_beam: float
    acoustic_scale: float
    beam: float
    nbest: int
    streaming: bool

    decode_mode: LangSuffix
    arpa_rescore_order: Optional[int]

    # Home Assistant
    hass_token: Optional[str] = None
    hass_websocket_uri: str = "homeassistant.local"
    hass_ingress: bool = False
    hass_auto_train: bool = False
    hass_builtin_intents: bool = True

    # Web server
    auto_train_model_id: Optional[str] = None

    # Misc
    model_id_for_language: Dict[str, str] = field(default_factory=dict)

    def model_data_dir(self, model_id: str) -> Path:
        return self.models_dir / model_id

    def model_train_dir(self, model_id: str, suffix: Optional[str] = None) -> Path:
        if suffix:
            dirname = f"training_{suffix}"
        else:
            dirname = "training"

        return self.train_dir / model_id / dirname

    def sentences_path(self, model_id: str, suffix: Optional[str] = None) -> Path:
        if suffix:
            filename = f"sentences_{suffix}.yaml"
        else:
            filename = "sentences.yaml"

        return self.train_dir / model_id / filename

    def get_suffixes(self, model_id: str) -> List[str]:
        suffixes: List[str] = []
        for sentences_path in (self.train_dir / model_id).glob("sentences*.yaml"):
            if not sentences_path.is_file():
                continue

            # sentences_{suffix}.yaml
            name_parts = sentences_path.stem.split("_", maxsplit=1)
            if len(name_parts) == 2:
                suffixes.append(name_parts[1])

        return suffixes

    def lists_path(self, model_id: str, suffix: Optional[str] = None) -> Path:
        if suffix:
            filename = f"lists_{suffix}.yaml"
        else:
            filename = "lists.yaml"

        return self.train_dir / model_id / filename

    def model_config(self, model_id: str) -> Dict[str, Any]:
        model_dir = self.model_data_dir(model_id)
        model_config_path = model_dir / "config.json"
        if not model_config_path.exists():
            return {}

        with open(model_config_path, "r", encoding="utf-8") as model_config_file:
            return json.load(model_config_file)


@dataclass
class AppState:
    settings: AppSettings

    # Responses for unknown sentences
    # model_id -> response
    unknown_sentence_responses: Dict[str, str] = field(default_factory=dict)
