"""Methods to train a custom Kaldi model."""

import io
import json
import os
from collections.abc import Collection
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from hassil.intents import Intents

from .const import LangSuffix, WordCasing
from .g2p import LexiconDatabase, get_sounds_like
from .intent_fst import intents_to_fst
from .kaldi import KaldiTrainer
from .tools import KaldiTools


async def train_model(
    language: str,
    intents: Intents,
    train_dir: Union[str, Path],
    model_dir: Union[str, Path],
    tools: KaldiTools,
    words: Optional[Dict[str, Union[str, List[str]]]] = None,
    lang_suffixes: Optional[Collection[LangSuffix]] = None,
    rescore_order: Optional[int] = None,
):
    """Train a model on YAML sentences."""
    model_config: Dict[str, Any] = {}
    model_config_path = os.path.join(model_dir, "config.json")
    if os.path.exists(model_config_path):
        with open(model_config_path, "r", encoding="utf-8") as model_config_file:
            model_config = json.load(model_config_file)

    word_casing = WordCasing(model_config.get("lexicon", {}).get("casing", "lower"))

    lexicon = LexiconDatabase(os.path.join(model_dir, "lexicon.db"))

    # User lexicon
    if words:
        for word, word_prons in words.items():
            if isinstance(word_prons, str):
                word_prons = [word_prons]

            for word_pron in word_prons:
                lexicon.add(word, get_sounds_like(word_pron.split(), lexicon))

    with io.StringIO() as fst_file:
        fst_context = intents_to_fst(
            train_dir=train_dir,
            intents=intents,
            fst_file=fst_file,
            lexicon=lexicon,
            number_language=language,
            word_casing=word_casing,
        )

        trainer_args: Dict[str, Any] = {}
        if "sil_phone" in model_config:
            trainer_args["sil_phone"] = model_config["sil_phone"]

        if "spn_phone" in model_config:
            trainer_args["spn_phone"] = model_config["spn_phone"]

        trainer = KaldiTrainer(
            train_dir=train_dir,
            model_dir=os.path.join(model_dir, "model"),
            tools=tools,
            fst_context=fst_context,
            **trainer_args,
        )

        train_args: Dict[str, Any] = {}
        if rescore_order is not None:
            train_args["rescore_order"] = rescore_order

        await trainer.train(lang_suffixes=lang_suffixes, **train_args)
