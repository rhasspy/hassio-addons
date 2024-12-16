"""Uses Coqui STT and OpenFST for decoding.

See:
- https://github.com/coqui-ai/STT
- https://arxiv.org/pdf/2206.14589
"""

import asyncio
import asyncio.subprocess
import itertools
import logging
import math
import shlex
import shutil
import struct
import tempfile
from asyncio.subprocess import Process
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from .hassil_fst import decode_meta
from .intent_fst import IntentsToFstContext
from .tools import KaldiTools

BLANK = "<blank>"
EPSILON = "<eps>"
SPACE = "<space>"

_LOGGER = logging.getLogger(__name__)


class CoquiSttError(Exception):
    pass


class StreamAlreadyStartedError(CoquiSttError):
    pass


class StreamNotStartedError(CoquiSttError):
    pass


class CoquiSttTranscriber:
    def __init__(
        self,
        model_dir: Union[str, Path],
        exe_path: Union[str, Path],
        tools: KaldiTools,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.exe_path = Path(exe_path)
        self.tools = tools
        self._proc: Optional[Process] = None
        self._is_stream_started = False

    async def _start_process(self) -> None:
        if self._proc is not None:
            self._proc.kill()
            self._proc = None

        self._proc = await asyncio.create_subprocess_exec(
            str(self.exe_path),
            str(self.model_dir / "model.tflite"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def start_stream(self) -> None:
        if self._proc is None:
            await self._start_process()

        if self._is_stream_started:
            raise StreamAlreadyStartedError

        self._is_stream_started = True

    async def process_chunk(self, chunk: bytes) -> None:
        if not self._is_stream_started:
            raise StreamNotStartedError

        assert self._proc is not None
        assert self._proc.stdin is not None
        assert chunk

        # Write chunk size (4 bytes), then chunk
        self._proc.stdin.write(struct.pack("I", len(chunk)))
        self._proc.stdin.write(chunk)
        await self._proc.stdin.drain()

    async def finish_stream(self) -> List[List[float]]:
        if not self._is_stream_started:
            raise StreamNotStartedError

        assert self._proc is not None
        assert self._proc.stdin is not None
        assert self._proc.stdout is not None

        # Zero-length chunk signals end
        self._proc.stdin.write(struct.pack("I", 0))
        await self._proc.stdin.drain()

        try:
            line = (await self._proc.stdout.readline()).decode().strip()
            probs: List[List[float]] = []
            while line:
                probs.append([float(p) for p in line.split()])
                line = (await self._proc.stdout.readline()).decode().strip()

            return probs
        finally:
            self._is_stream_started = False

    async def stop(self) -> None:
        if self._proc is None:
            return

        await self._proc.communicate()
        self._proc = None

    async def decode_probs(
        self,
        probs: List[List[float]],
        train_dir: Union[str, Path],
        prune_threshold: float = 10,
    ) -> str:
        train_dir = Path(train_dir)

        tokens_txt = train_dir / "tokens_with_blank.txt"
        output_txt = train_dir / "output.txt"
        char2idx: Dict[str, int] = {}
        with open(tokens_txt, "r", encoding="utf-8") as words_file:
            for line in words_file:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue

                label = parts[0]
                if label == EPSILON:
                    continue

                char2idx[label] = int(parts[1])

        blank_id = char2idx[BLANK]
        idx2char = {i: c for c, i in char2idx.items()}

        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            logits_txt = temp_dir / "logits.fst.txt"
            with open(logits_txt, "w", encoding="utf-8") as logits_file:
                current = 0

                # Add space to the end and make it the most probable
                space_prob = 0.99
                nonspace_prob = ((1 - space_prob) / (len(probs) - 1)) + 1e-9
                space_probs = [
                    space_prob if c == SPACE else nonspace_prob for c in char2idx
                ]

                for current_probs in itertools.chain(probs, [space_probs]):
                    for i, prob in enumerate(current_probs, start=1):
                        log_prob = -math.log(prob + 1e-9)
                        if i == blank_id:
                            c = BLANK
                        else:
                            c = idx2char[i]

                        print(current, current + 1, c, log_prob, file=logits_file)

                    current += 1

                print(current, file=logits_file)

            # tokens -> chars -> words -> sentences
            tokens_txt = train_dir / "tokens_with_blank.txt"
            token2sen_fst = train_dir / "token2sen.fst"
            stdout = await self.tools.async_run_pipeline(
                [
                    "fstcompile",
                    shlex.quote(f"--isymbols={tokens_txt}"),
                    shlex.quote(f"--osymbols={tokens_txt}"),
                    "--acceptor",
                    shlex.quote(str(logits_txt)),
                ],
                ["fstdeterminize"],
                ["fstminimize"],
                ["fstpush", "--push_weights"],
                ["fstarcsort", "--sort_type=olabel"],
                ["fstprune", f"--weight={prune_threshold}"],  # prune logits
                ["fstcompose", "-", shlex.quote(str(token2sen_fst))],
                ["fstshortestpath"],
                ["fstproject", "--project_type=output"],
                ["fstrmepsilon"],
                ["fsttopsort"],
                [
                    "fstprint",
                    shlex.quote(f"--isymbols={output_txt}"),
                    shlex.quote(f"--osymbols={output_txt}"),
                ],
                ["awk", "{print $4}"],  # output label
            )

        words = stdout.decode(encoding="utf-8").split()
        text = " ".join(words)
        return decode_meta(text)


class CoquiSttTrainer:
    def __init__(
        self,
        model_dir: Union[str, Path],
        tools: KaldiTools,
    ) -> None:
        self.tools = tools
        self.idx2char: Dict[int, str] = {}
        self.char2idx: Dict[str, int] = {}

        self.model_dir = Path(model_dir)
        alphabet_path = self.model_dir / "alphabet.txt"

        # Load alphabet
        a_idx = 1  # <eps> = 0
        with open(alphabet_path, "r", encoding="utf-8") as a_file:
            for line in a_file:
                line = line.strip()
                if line.startswith("#"):
                    continue

                if not line:
                    line = " "
                elif line == "\\#":
                    line = "#"

                c = line[0]
                if c == " ":
                    c = SPACE

                self.idx2char[a_idx] = c
                self.char2idx[c] = a_idx
                a_idx += 1

        self.blank_id = a_idx
        self.idx2char[self.blank_id] = BLANK
        self.char2idx[BLANK] = self.blank_id

    async def train(
        self, ctx: IntentsToFstContext, train_dir: Union[str, Path]
    ) -> None:
        train_dir = Path(train_dir)
        train_dir.mkdir(parents=True, exist_ok=True)

        # CTC tokens
        tokens_with_blank = train_dir / "tokens_with_blank.txt"
        tokens_without_blank = train_dir / "tokens_without_blank.txt"
        with open(
            tokens_with_blank, "w", encoding="utf-8"
        ) as tokens_with_blank_file, open(
            tokens_without_blank, "w", encoding="utf-8"
        ) as tokens_without_blank_file:
            # NOTE: <eps> *MUST* be id 0
            for tokens_file in (tokens_with_blank_file, tokens_without_blank_file):
                print(EPSILON, 0, file=tokens_file)
                for i, c in self.idx2char.items():
                    if c == BLANK:
                        continue

                    print(c, i, file=tokens_file)

            print(BLANK, self.blank_id, file=tokens_with_blank_file)

        # token -> char
        token2char_txt = train_dir / "token2char.fst.txt"
        with open(token2char_txt, "w", encoding="utf-8") as token2char_file:
            start = 0

            # Accept blank
            print(start, start, BLANK, EPSILON, file=token2char_file)
            print(start, file=token2char_file)

            # Each token has a state
            char2state = {c: i for i, c in enumerate(self.char2idx, start=1)}

            for c, c_state in char2state.items():
                if c == BLANK:
                    continue

                # First token (emits char)
                print(start, c_state, c, c, file=token2char_file)

                # Subsequent repeated tokens
                print(c_state, c_state, c, EPSILON, file=token2char_file)

                # Back to start on blank
                print(c_state, start, BLANK, EPSILON, file=token2char_file)

                for c_other, c_other_state in char2state.items():
                    if c_other in (c, BLANK):
                        continue

                    # Switch to other token
                    print(
                        c_state, c_other_state, c_other, c_other, file=token2char_file
                    )

                # Return to start
                # NOTE: This is critical
                print(c_state, start, EPSILON, EPSILON, file=token2char_file)

        # All possible words
        words_txt = train_dir / "words.txt"
        with open(words_txt, "w", encoding="utf-8") as words_file:
            print(EPSILON, 0, file=words_file)
            for i, word in enumerate(sorted(ctx.vocab), start=1):
                if word == EPSILON:
                    continue

                print(word, i, file=words_file)

        output_txt = train_dir / "output.txt"
        with open(output_txt, "w", encoding="utf-8") as output_file:
            print(EPSILON, 0, file=output_file)
            for i, word in enumerate(sorted(ctx.vocab), start=1):
                if word == EPSILON:
                    continue

                print(word, i, file=output_file)

            # Output labels
            for i, word in enumerate(sorted(ctx.meta_labels), start=len(ctx.vocab) + 1):
                print(word, i, file=output_file)

        # char -> word
        char2word_txt = train_dir / "char2word.fst.txt"
        warned_chars: Set[str] = set()
        with open(char2word_txt, "w", encoding="utf-8") as char2word_file:
            start = 0
            current = 1

            for word in ctx.vocab:
                if word == EPSILON:
                    continue

                for c_idx, c in enumerate(word):
                    if c not in self.char2idx:
                        if c not in warned_chars:
                            _LOGGER.warning("Skipping '%s' in '%s'", c, word)
                            warned_chars.add(c)

                        continue

                    if c_idx == 0:
                        # First char, emit word
                        print(start, current, c, word, file=char2word_file)
                    else:
                        # Subsequent chars
                        print(current, current + 1, c, EPSILON, file=char2word_file)
                        current += 1

                # Add space
                print(current, current + 1, SPACE, EPSILON, file=char2word_file)
                current += 1

                # Loop back to start
                print(current, start, EPSILON, EPSILON, file=char2word_file)
                current += 1

            print(start, file=char2word_file)

        # word -> sentence
        word2sen_txt = train_dir / "word2sen.fst.txt"
        with open(word2sen_txt, "w", encoding="utf-8") as word2sen_file:
            ctx.fst_file.seek(0)
            shutil.copyfileobj(ctx.fst_file, word2sen_file)

        token2char_fst = train_dir / "token2char.fst"
        await self.tools.async_run_pipeline(
            [
                "fstcompile",
                shlex.quote(f"--isymbols={tokens_with_blank}"),
                shlex.quote(f"--osymbols={tokens_without_blank}"),
                shlex.quote(str(token2char_txt)),
            ],
            ["fstdeterminize"],
            ["fstminimize"],
            ["fstpush", "--push_weights"],
            ["fstarcsort", "--sort_type=ilabel", "-", shlex.quote(str(token2char_fst))],
        )

        char2word_fst = train_dir / "char2word.fst"
        await self.tools.async_run_pipeline(
            [
                "fstcompile",
                shlex.quote(f"--isymbols={tokens_without_blank}"),
                shlex.quote(f"--osymbols={words_txt}"),
                shlex.quote(str(char2word_txt)),
            ],
            # ["fstdeterminize"],
            # ["fstminimize"],
            ["fstpush", "--push_weights"],
            ["fstarcsort", "--sort_type=ilabel", "-", shlex.quote(str(char2word_fst))],
        )

        word2sen_fst = train_dir / "word2sen.fst"
        await self.tools.async_run_pipeline(
            [
                "fstcompile",
                shlex.quote(f"--isymbols={words_txt}"),
                shlex.quote(f"--osymbols={output_txt}"),
                shlex.quote(str(word2sen_txt)),
            ],
            ["fstarcsort", "--sort_type=ilabel", "-", shlex.quote(str(word2sen_fst))],
        )

        # token -> char -> word
        token2word_fst = train_dir / "token2word.fst"
        await self.tools.async_run_pipeline(
            [
                "fstcompose",
                shlex.quote(str(token2char_fst)),
                shlex.quote(str(char2word_fst)),
            ],
            ["fstarcsort", "--sort_type=ilabel", "-", shlex.quote(str(token2word_fst))],
        )

        # token -> char -> word -> sentence
        token2sen_fst = train_dir / "token2sen.fst"
        await self.tools.async_run_pipeline(
            [
                "fstcompose",
                shlex.quote(str(token2word_fst)),
                shlex.quote(str(word2sen_fst)),
            ],
            ["fstrmepsilon"],
            ["fstpush", "--push_weights"],
            ["fstarcsort", "--sort_type=ilabel", "-", shlex.quote(str(token2sen_fst))],
        )
