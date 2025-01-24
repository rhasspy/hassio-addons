"""Grapheme to phoneme methods."""

import sqlite3
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import regex as re
from unicode_rbnf import RbnfEngine

_INITIALISM_NO_DOTS = re.compile(r"^(?:\p{Lu}){2,}$")
_INITIALISM_DOTS = re.compile(r"^(?:\p{L}\.){2,}$")
_NUMBER_SPLIT = re.compile(r"(\d+(?:\.\d+)?)")
_NUMBER = re.compile(r"^\d+(\.\d+)?$")

# -----------------------------------------------------------------------------


class LexiconDatabase:
    """Pronunciation database."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = Path(db_path) if db_path else None
        self._conn = sqlite3.Connection(str(self.db_path)) if self.db_path else None
        self._cache: Dict[str, Optional[List[List[str]]]] = {}

    def add(self, word: str, pronunciations: List[List[str]]) -> None:
        """Add pronunciations for a word (cache only)."""
        cached_prons = self._cache.get(word)
        if cached_prons is None:
            self._cache[word] = pronunciations
        else:
            cached_prons.extend(pronunciations)

    def exists(self, word: str) -> bool:
        """Check if a pronunciation is known for the word."""
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
        """Get pronunciations for a word."""
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
    """Split text/words into input/output sub-words."""
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
                        # Emit number string on first word.
                        # 100 becomes one -> 100, hundred -> None
                        words.append((number_word, sub_word))
                    else:
                        words.append((number_word, None))
            else:
                # Will guess later
                words.append(sub_word)

    return words


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
