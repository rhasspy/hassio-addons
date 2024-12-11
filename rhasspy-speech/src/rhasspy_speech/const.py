from collections.abc import Callable
from enum import Enum

EPS = "<eps>"
SIL = "SIL"
SPN = "SPN"
UNK = "<unk>"


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


class ModelType(str, Enum):
    NNET3 = "nnet3"
    GMM = "gmm"


class LangSuffix(str, Enum):
    GRAMMAR = "grammar"
    ARPA = "arpa"
    ARPA_RESCORE = "arpa_rescore"
