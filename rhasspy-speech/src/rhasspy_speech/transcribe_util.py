import io
import shlex
from pathlib import Path
from typing import List, Optional, Tuple

from .const import EPS
from .hassil_fst import Fst
from .tools import KaldiTools


async def get_fuzzy_text(
    nbest_stdout: bytes,
    lang_dir: Path,
    tools: KaldiTools,
) -> Optional[Tuple[str, float]]:
    fuzzy_fst_path = lang_dir / "G.fuzzy.fst"
    if not fuzzy_fst_path.exists():
        return None

    words_txt = lang_dir / "words.txt"

    # Get best fuzzy transcription
    input_fst = Fst()
    penalty = 0
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
            penalty += 0.1

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
