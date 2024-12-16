"""Convert sentences to FST."""

import logging
from dataclasses import dataclass, field
from typing import Optional, Set, TextIO

from hassil.intents import Intents

from .const import WordCasing
from .g2p import LexiconDatabase
from .hassil_fst import G2PInfo
from .hassil_fst import intents_to_fst as hassil_intents_to_fst

_LOGGER = logging.getLogger(__name__)


@dataclass
class IntentsToFstContext:
    fst_file: TextIO
    lexicon: LexiconDatabase
    vocab: Set[str] = field(default_factory=set)
    meta_labels: Set[str] = field(default_factory=set)
    word_casing: WordCasing = WordCasing.LOWER


def intents_to_fst(
    intents: Intents,
    fst_file: TextIO,
    lexicon: LexiconDatabase,
    number_language: Optional[str] = None,
    word_casing: WordCasing = WordCasing.LOWER,
) -> IntentsToFstContext:
    """Convert YAML sentence files to an FST for Kaldi."""
    context = IntentsToFstContext(fst_file=fst_file, lexicon=lexicon)
    casing_func = WordCasing.get_function(word_casing)

    fst = hassil_intents_to_fst(
        intents, number_language=number_language, g2p_info=G2PInfo(lexicon, casing_func)
    ).remove_spaces()
    fst.prune()

    fst.write(context.fst_file)
    context.fst_file.seek(0)
    context.vocab = fst.words
    context.meta_labels = fst.output_words - fst.words

    return context
