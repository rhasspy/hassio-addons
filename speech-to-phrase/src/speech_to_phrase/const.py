"""Constants."""

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Optional, Union

from .speech_tools import SpeechTools

# Kaldi
EPS = "<eps>"
SIL = "SIL"
SPN = "SPN"
UNK = "<unk>"

# Audio
RATE = 16000
WIDTH = 2
CHANNELS = 1


class Language(str, Enum):
    ENGLISH = "en"


class Settings:
    def __init__(
        self,
        models_dir: Union[str, Path],
        train_dir: Union[str, Path],
        tools_dir: Union[str, Path],
        sentences_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.models_dir = Path(models_dir)
        self.train_dir = Path(train_dir)
        self.tools = SpeechTools.from_tools_dir(tools_dir)

        if not sentences_dir:
            # Builtin sentences
            sentences_dir = Path(__file__).parent / "sentences"

        self.sentences = Path(sentences_dir)


class WordCasing(str, Enum):
    KEEP = "keep"
    LOWER = "lower"
    UPPER = "upper"

    @staticmethod
    def get_function(casing: "WordCasing") -> Callable[[str], str]:
        if casing == WordCasing.LOWER:
            return str.lower

        if casing == WordCasing.UPPER:
            return str.upper

        return lambda s: s
