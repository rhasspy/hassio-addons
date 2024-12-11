"""Grapheme to phoneme methods."""

import itertools
import sqlite3
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import regex as re
from unicode_rbnf import RbnfEngine

_SOUNDS_LIKE_PARTIAL = re.compile(r"^([^[]*)\[([^]]+)].*$")
_INITIALISM_NO_DOTS = re.compile(r"^(?:\p{Lu}){2,}$")
_INITIALISM_DOTS = re.compile(r"^(?:\p{L}\.){2,}$")
_NUMBER_SPLIT = re.compile(r"(\d+(?:\.\d+)?)")
_NUMBER = re.compile(r"^\d+(\.\d+)?$")

# -----------------------------------------------------------------------------


class LexiconDatabase:
    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = Path(db_path) if db_path else None
        self._conn = sqlite3.Connection(str(self.db_path)) if self.db_path else None
        self._cache: Dict[str, Optional[List[List[str]]]] = {}

    def add(self, word: str, pronunciations: List[List[str]]) -> None:
        cached_prons = self._cache.get(word)
        if cached_prons is None:
            self._cache[word] = pronunciations
        else:
            cached_prons.extend(pronunciations)

    def exists(self, word: str) -> bool:
        if (not self._cache) and (self._conn is not None):
            # Load word list and add placeholders
            cur = self._conn.execute("SELECT DISTINCT word FROM word_phonemes")
            for row in cur:
                self._cache[row[0]] = None

        word_vars = tuple(self._word_variations(word))
        for word_var in word_vars:
            if word_var in self._cache:
                return True

        return False

    def lookup(self, word: str) -> List[List[str]]:
        word_vars = list(self._word_variations(word))
        for word_var in word_vars:
            cached_prons = self._cache.get(word_var)
            if cached_prons is not None:
                return cached_prons

        if self._conn is None:
            return []

        db_prons: List[List[str]] = []
        for word_var in word_vars:
            cur = self._conn.execute(
                "SELECT phonemes FROM word_phonemes WHERE word = ? ORDER by pron_order",
                (word_var,),
            )
            for row in cur:
                db_prons.append(row[0].split())

            if db_prons:
                # Only return pronunciation for first variation
                self._cache[word_var] = db_prons
                break

        # Update cache
        self._cache[word] = db_prons

        return db_prons

    def alignments(self, word: str) -> List[str]:
        if self._conn is None:
            return []

        alignments: List[str] = []
        for word_var in self._word_variations(word):
            cur = self._conn.execute(
                "SELECT alignment FROM g2p_alignments WHERE word = ?",
                (word_var,),
            )
            for row in cur:
                alignments.append(row[0])

            if alignments:
                # Only return alignments for first variation
                break

        return alignments

    def _word_variations(self, word: str) -> Iterable[str]:
        yield word
        word_lower = word.lower()
        if word_lower != word:
            yield word_lower

        word_casefold = word.casefold()
        if word_casefold != word_lower:
            yield word_casefold

        word_upper = word.upper()
        if word_upper != word:
            yield word_upper


# -----------------------------------------------------------------------------


def split_words(
    text: str, lexicon: LexiconDatabase, number_engine: Optional[RbnfEngine] = None
) -> List[Union[str, Tuple[str, Optional[str]]]]:
    words: List[Union[str, Tuple[str, Optional[str]]]] = []
    for word in text.split():
        if lexicon.exists(word):
            words.append(word)
            continue

        # abc123 -> abc 123
        for sub_word in _NUMBER_SPLIT.split(word):
            if not sub_word:
                continue

            if lexicon.exists(sub_word):
                words.append(sub_word)
                continue

            if _INITIALISM_NO_DOTS.match(sub_word):
                # ABC -> A B C
                words.extend(list(sub_word))
            elif _INITIALISM_DOTS.match(sub_word):
                # A.B.C. -> A B C
                words.extend((c for c in sub_word if c != "."))
            elif _NUMBER.match(sub_word) and (number_engine is not None):
                # 123 -> one hundred twenty three
                number_word_str = number_engine.format_number(sub_word).text
                number_words = number_word_str.replace("-", " ").split()
                for num_word_idx, number_word in enumerate(number_words):
                    if num_word_idx == 0:
                        words.append((number_word, sub_word))
                    else:
                        words.append((number_word, None))
            else:
                # Will guess later
                words.append(sub_word)

    return words


# -----------------------------------------------------------------------------


def get_sounds_like(
    sounds_like: Iterable[str],
    lexicon: LexiconDatabase,
) -> List[List[str]]:
    # Identify literal phonemes
    in_phoneme = False

    # line -> alternatives -> phoneme sequence
    known_phonemes: List[List[List[str]]] = []

    # ongoing phoneme sequence
    current_phonemes: List[str] = []

    # Process space-separated tokens
    for sounds_like_word in sounds_like:
        if sounds_like_word.startswith("/"):
            # Begin literal phoneme string
            # /P1 P2 P3/
            in_phoneme = True
            sounds_like_word = sounds_like_word[1:]
            current_phonemes = []

        end_slash = sounds_like_word.endswith("/")
        if end_slash:
            # End literal phoneme string
            # /P1 P2 P3/
            sounds_like_word = sounds_like_word[:-1]

        if in_phoneme:
            # Literal phonemes
            # P_N of /P1 P2 P3/
            current_phonemes.append(sounds_like_word)
        else:
            # Check for [part]ial word
            partial_match = _SOUNDS_LIKE_PARTIAL.match(sounds_like_word)
            if partial_match:
                partial_prefix, partial_body = (
                    partial_match.group(1),
                    partial_match.group(2),
                )

                # Align graphemes with phonemes
                word = re.sub(r"[\[\]]", "", sounds_like_word)
                aligned_phonemes = get_aligned_phonemes(
                    lexicon, word, partial_prefix, partial_body
                )

                # Add all possible alignments (phoneme sequences) as alternatives
                known_phonemes.append(list(aligned_phonemes))
            else:
                # Add all pronunciations as alternatives
                known_phonemes.append(lexicon.lookup(sounds_like_word))

        if end_slash:
            in_phoneme = False
            if current_phonemes:
                known_phonemes.append([current_phonemes])

    pronunciations = []
    # Collect pronunciations from known words
    # word_prons: List[List[List[str]]] = []
    for word_phonemes in itertools.product(*known_phonemes):
        # Generate all possible pronunciations.
        word_pron = list(itertools.chain(*word_phonemes))
        pronunciations.append(word_pron)

    return pronunciations


def get_aligned_phonemes(
    lexicon: LexiconDatabase, word: str, prefix: str, body: str
) -> Iterable[List[str]]:
    for alignment in lexicon.alignments(word):
        word = ""
        inputs_outputs = []

        # Parse phonetisaurus alignment.
        # For example "test" = "t}t e}ˈɛ s}s t}t i}ɪ n|g}ŋ"
        parts = alignment.split()
        for part in parts:
            # Assume default delimiters:
            # } separates input/output
            # | separates input/output tokens
            # _ indicates empty output
            part_in, part_out = part.split("}")
            part_ins = part_in.split("|")
            if part_out == "_":
                # Empty output
                part_outs = []
            else:
                part_outs = part_out.split("|")

            inputs_outputs.append((part_ins, part_outs))
            word += "".join(part_ins)

        can_match = True
        prefix_chars = list(prefix)
        body_chars = list(body)

        phonemes = []
        for word_input, word_output in inputs_outputs:
            word_input = list(word_input)
            word_output = list(word_output)

            while prefix_chars and word_input:
                # Exhaust characters before desired word segment first
                if word_input[0] != prefix_chars[0]:
                    can_match = False
                    break

                prefix_chars = prefix_chars[1:]
                word_input = word_input[1:]

            while body_chars and word_input:
                # Match desired word segment
                if word_input[0] != body_chars[0]:
                    can_match = False
                    break

                body_chars = body_chars[1:]
                word_input = word_input[1:]

                if word_output:
                    phonemes.append(word_output[0])
                    word_output = word_output[1:]

            if not can_match or not body_chars:
                # Mismatch or done with word segment
                break

        if can_match and phonemes:
            yield phonemes


# -----------------------------------------------------------------------------


def guess_pronunciations(
    words: Iterable[str],
    g2p_model_path: Union[str, Path],
    phonetisaurus_bin: Union[str, Path],
) -> Iterable[Tuple[str, str]]:
    with tempfile.NamedTemporaryFile(
        "w+", encoding="utf-8", suffix=".txt"
    ) as wordlist_file:
        for word in words:
            print(word, file=wordlist_file)

        wordlist_file.seek(0)

        phonetisaurus_output = (
            subprocess.check_output(
                [
                    str(phonetisaurus_bin),
                    f"--model={g2p_model_path}",
                    f"--wordlist={wordlist_file.name}",
                ]
            )
            .decode()
            .splitlines()
        )
        for line in phonetisaurus_output:
            line = line.strip()
            if line:
                line_parts = line.split()
                if len(line_parts) < 3:
                    continue

                word = line_parts[0]
                phonemes = " ".join(line_parts[2:])
                yield (word, phonemes)
