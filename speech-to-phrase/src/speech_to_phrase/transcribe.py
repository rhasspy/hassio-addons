"""Model transcription."""

import asyncio
import io
import logging
import shlex
import tempfile
from collections.abc import AsyncIterable
from pathlib import Path
from typing import List, Optional, Tuple

from .const import EPS, Settings
from .hassil_fst import Fst, decode_meta
from .models import Model
from .speech_tools import SpeechTools

_LOGGER = logging.getLogger(__name__)

# Decoding
MAX_ACTIVE = 7000
LATTICE_BEAM = 8.0
DECODE_ACOUSTIC_SCALE = 1.0
BEAM = 24.0

# Lower sticks more to LM, but accepts more OOV sentences
NBEST_ACOUSTIC_SCALE = 0.9

# Candidates for fuzzy matching
NBEST = 3
NBEST_PENALTY = 0.1

# Max penalty before we declare the sentence to be OOV
MAX_FUZZY_COST = 2.0


async def transcribe(
    model: Model, settings: Settings, audio_stream: AsyncIterable[bytes]
) -> str:
    """Transcribe text from an audio stream."""
    model_dir = (settings.models_dir / model.id).absolute()
    train_dir = (settings.train_dir / model.id).absolute()
    lang_dir = train_dir / "data" / "lang"
    graph_dir = train_dir / "graph"
    tools = settings.tools

    model_file = model_dir / "model" / "model" / "final.mdl"
    words_txt = graph_dir / "words.txt"
    online_conf = model_dir / "model" / "online" / "conf" / "online.conf"

    with tempfile.NamedTemporaryFile("wb+") as lattice_file:
        lattice_path = lattice_file.name
        program = "online2-cli-nnet3-decode-faster"
        args = [
            f"--config={online_conf}",
            f"--max-active={MAX_ACTIVE}",
            f"--lattice-beam={LATTICE_BEAM}",
            f"--acoustic-scale={DECODE_ACOUSTIC_SCALE}",
            f"--beam={BEAM}",
            str(model_file),
            str(graph_dir / "HCLG.fst"),
            str(words_txt),
            f"ark:{lattice_path}",
        ]
        _LOGGER.debug("%s %s", program, args)
        proc = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            env=tools.extended_env,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None

        async for chunk in audio_stream:
            proc.stdin.write(chunk)
            await proc.stdin.drain()

        _LOGGER.debug("Stream ended")
        proc.stdin.write_eof()
        await proc.communicate()

        # Transcripts
        nbest_stdout = await tools.async_run_pipeline(
            [
                "lattice-to-nbest",
                f"--n={NBEST}",
                f"--acoustic-scale={NBEST_ACOUSTIC_SCALE}",
                f"ark:{lattice_path}",
                "ark:-",
            ],
            [
                "nbest-to-linear",
                "ark:-",
                "ark:/dev/null",  # alignments
                "ark,t:-",  # transcriptions
            ],
        )

        int2sym_stdout = await tools.async_run_pipeline(
            [
                str(tools.egs_utils_dir / "int2sym.pl"),
                "-f",
                "2-",
                str(words_txt),
            ],
            input=nbest_stdout,
        )
        _LOGGER.debug("nbest: %s", int2sym_stdout.decode(encoding="utf-8"))

        fuzzy_result = await _get_fuzzy_text(nbest_stdout, lang_dir, tools)
        if fuzzy_result is None:
            # Failed to match fuzzy FST
            return ""

        text, cost = fuzzy_result
        _LOGGER.debug("Fuzzy cost: %s", cost)
        if cost > MAX_FUZZY_COST:
            # Fuzzy cost was too high
            return ""

        return decode_meta(text)


async def _get_fuzzy_text(
    nbest_stdout: bytes,
    lang_dir: Path,
    tools: SpeechTools,
) -> Optional[Tuple[str, float]]:
    fuzzy_fst_path = lang_dir / "G.fuzzy.fst"
    if not fuzzy_fst_path.exists():
        return None

    words_txt = lang_dir / "words.txt"

    # Get best fuzzy transcription
    input_fst = Fst()
    penalty = 0.0
    with io.StringIO(nbest_stdout.decode("utf-8")) as nbest_file:
        for line in nbest_file:
            line = line.strip()
            if not line:
                continue

            # Strip utt-*
            path = line.split()[1:]
            state = input_fst.start
            for symbol in path:
                state = input_fst.next_edge(state, symbol, symbol, log_prob=penalty)

            input_fst.final_states.add(state)

            # Each lower nbest candidate should be penalized more
            penalty += NBEST_PENALTY

    with io.StringIO() as input_fst_file:
        input_fst.write(input_fst_file)
        input_fst_file.flush()
        input_fst_file.seek(0)

        stdout = await tools.async_run_pipeline(
            ["fstcompile"],
            [
                "fstcompose",
                "-",
                shlex.quote(str(fuzzy_fst_path)),
            ],
            ["fstshortestpath"],
            ["fstrmepsilon"],
            ["fsttopsort"],
            ["fstproject", "--project_type=output"],
            ["fstprint", f"--osymbols={words_txt}"],
            input=input_fst_file.getvalue().encode("utf-8"),
        )

        words: List[str] = []
        word_cost: float = 0
        for line in stdout.decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 4:
                continue

            word = parts[3]

            if len(parts) > 4:
                word_log_prob = float(parts[4])
                word_cost += word_log_prob

            if word == EPS:
                continue

            words.append(word)

        if words:
            text = " ".join(words)
            return (text, word_cost)

        return None
