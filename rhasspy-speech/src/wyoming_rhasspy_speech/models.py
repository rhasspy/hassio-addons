from dataclasses import dataclass
from typing import Dict, Optional

URL_FORMAT = "https://huggingface.co/datasets/rhasspy/rhasspy-speech/resolve/main/models/{model_id}.tar.gz?download=true"


@dataclass
class Model:
    id: str
    language: str
    language_code: str
    attribution: str
    url: str
    version: Optional[str] = None


MODEL_IDS = [
    ("cs_CZ-rhasspy", "Czech, Czech Republic"),
    ("de_DE-zamia", "German, Germany"),
    ("en_US-rhasspy", "English, United States"),
    # ("en_US-zamia", "English, United States"),
    ("es_ES-rhasspy", "Spanish, Spain"),
    # ("fr_FR-guyot", "French, France"),
    ("fr_FR-rhasspy", "French, France"),
    ("it_IT-rhasspy", "Italian, Italy"),
    ("nl_NL-cgn", "Dutch, Netherlands"),
    ("ru_RU-rhasspy", "Russian, Russia"),
]

MODELS: Dict[str, Model] = {
    model_id: Model(
        id=model_id,
        language=model_lang,
        language_code=model_id.split("-", maxsplit=1)[0],
        attribution=model_id.split("-", maxsplit=1)[1].capitalize(),
        url=URL_FORMAT.format(model_id=model_id),
    )
    for model_id, model_lang in MODEL_IDS
}
