"""Speech-to-phrase models."""

from dataclasses import dataclass
from typing import Dict

from .const import Language, WordCasing


@dataclass
class Model:
    """Speech-to-phrase model."""

    id: str
    description: str
    version: str
    author: str
    url: str
    casing: WordCasing
    sentences_language: str
    number_language: str


MODELS: Dict[str, Model] = {
    Language.ENGLISH.value: Model(
        id="en_US-rhasspy",
        description="U.S. English Kaldi model",
        version="1.0",
        author="Rhasspy",
        url="https://github.com/rhasspy/rhasspy",
        casing=WordCasing.LOWER,
        sentences_language="en",
        number_language="en",
    )
}
