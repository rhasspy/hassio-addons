"""Transcribe audio stream."""

import asyncio
import logging
import shlex
import tempfile
from collections.abc import AsyncIterable
from pathlib import Path
from typing import List, Optional, Union

from .hassil_fst import decode_meta
from .tools import KaldiTools
from .transcribe_util import get_fuzzy_text

_LOGGER = logging.getLogger(__name__)


class KaldiNnet3StreamTranscriber:
    def __init__(
        self,
        model_dir: Union[str, Path],
        graph_dir: Union[str, Path],
        tools: KaldiTools,
        max_active: int = 7000,
        lattice_beam: float = 8.0,
        acoustic_scale: float = 1.0,
        beam: float = 24.0,
    ):
        self.model_dir = Path(model_dir)
        self.graph_dir = Path(graph_dir)
        self.tools = tools

        self.max_active = max_active
        self.lattice_beam = lattice_beam
        self.acoustic_scale = acoustic_scale
        self.beam = beam

    async def async_transcribe(
        self,
        audio_stream: AsyncIterable[Optional[bytes]],
        lang_dir: Union[str, Path],
        nbest: int = 1,
        max_fuzzy_cost: Optional[float] = None,
        require_fuzzy: bool = False,
    ) -> List[str]:
        lang_dir = Path(lang_dir)
        model_file = self.model_dir / "model" / "model" / "final.mdl"
        words_txt = self.graph_dir / "words.txt"
        online_conf = self.model_dir / "model" / "online" / "conf" / "online.conf"

        with tempfile.NamedTemporaryFile("wb+") as lattice_file:
            lattice_path = lattice_file.name
            program = "online2-cli-nnet3-decode-faster"
            args = [
                f"--config={online_conf}",
                f"--max-active={self.max_active}",
                f"--lattice-beam={self.lattice_beam}",
                "--acoustic-scale=1.0",
                f"--beam={self.beam}",
                str(model_file),
                str(self.graph_dir / "HCLG.fst"),
                str(words_txt),
                f"ark:{lattice_path}",
            ]
            _LOGGER.debug("%s %s", program, args)
            proc = await asyncio.create_subprocess_exec(
                program,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                env=self.tools.extended_env,
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
            nbest_stdout = await self.tools.async_run_pipeline(
                [
                    "lattice-to-nbest",
                    f"--n={nbest}",
                    f"--acoustic-scale={self.acoustic_scale}",
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

            int2sym_stdout = await self.tools.async_run_pipeline(
                [
                    str(self.tools.egs_utils_dir / "int2sym.pl"),
                    "-f",
                    "2-",
                    str(words_txt),
                ],
                input=nbest_stdout,
            )
            _LOGGER.debug("nbest: %s", int2sym_stdout.decode(encoding="utf-8"))

            fuzzy_result = await get_fuzzy_text(nbest_stdout, lang_dir, self.tools)
            if fuzzy_result is not None:
                text, cost = fuzzy_result
                _LOGGER.debug("Fuzzy cost: %s", cost)
                if cost <= max_fuzzy_cost:
                    return [decode_meta(text)]

            if require_fuzzy:
                return []

            texts: List[str] = []
            for line in int2sym_stdout.decode().splitlines():
                if line.startswith("utt-"):
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) > 1:
                        texts.append(decode_meta(parts[1]))

            return texts

    async def async_transcribe_rescore(
        self,
        audio_stream: AsyncIterable[Optional[bytes]],
        old_lang_dir: Union[str, Path],
        new_lang_dir: Union[str, Path],
        nbest: int = 1,
        max_fuzzy_cost: Optional[float] = None,
        require_fuzzy: bool = False,
    ) -> List[str]:
        old_lang_dir = Path(old_lang_dir)
        new_lang_dir = Path(new_lang_dir)

        # Get id for #0 disambiguation state
        phi: Optional[int] = None
        with open(str(new_lang_dir / "words.txt"), "r", encoding="utf-8") as words_file:
            for line in words_file:
                if line.startswith("#0 "):
                    phi = int(line.strip().split(maxsplit=1)[1])
                    break

        if phi is None:
            raise ValueError("No value for disambiguation state (#0)")

        # Create Ldet.fst
        await self.tools.async_run_pipeline(
            ["fstprint", str(new_lang_dir / "L_disambig.fst")],
            ["awk", f"{{if($4 != {phi}){{print;}}}}"],
            ["fstcompile"],
            ["fstdeterminizestar"],
            [
                "fstrmsymbols",
                str(new_lang_dir / "phones" / "disambig.int"),
                "-",
                shlex.quote(str(new_lang_dir / "Ldet.fst")),
            ],
        )

        model_file = self.model_dir / "model" / "model" / "final.mdl"
        words_txt = self.graph_dir / "words.txt"
        online_conf = self.model_dir / "model" / "online" / "conf" / "online.conf"

        with tempfile.NamedTemporaryFile("wb+") as lattice_file:
            lattice_path = lattice_file.name
            program = "online2-cli-nnet3-decode-faster"
            args = [
                f"--config={online_conf}",
                f"--max-active={self.max_active}",
                f"--lattice-beam={self.lattice_beam}",
                "--acoustic-scale=1.0",
                f"--beam={self.beam}",
                str(model_file),
                str(self.graph_dir / "HCLG.fst"),
                str(words_txt),
                f"ark:{lattice_path}",
            ]
            _LOGGER.debug("%s %s", program, args)
            proc = await asyncio.create_subprocess_exec(
                program,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                env=self.tools.extended_env,
            )
            assert proc.stdin is not None
            assert proc.stdout is not None

            async for chunk in audio_stream:
                proc.stdin.write(chunk)
                await proc.stdin.drain()

            _LOGGER.debug("Stream ended")
            proc.stdin.write_eof()
            await proc.communicate()

            nbest_stdout = await self.tools.async_run_pipeline(
                ["lattice-scale", "--lm-scale=0.0", f"ark:{lattice_path}", "ark:-"],
                ["lattice-to-phone-lattice", str(model_file), "ark:-", "ark:-"],
                [
                    "lattice-compose",
                    "ark:-",
                    str(new_lang_dir / "Ldet.fst"),
                    "ark:-",
                ],
                ["lattice-determinize", "ark:-", "ark:-"],
                [
                    "lattice-compose",
                    f"--phi-label={phi}",
                    "ark:-",
                    str(new_lang_dir / "G.fst"),
                    "ark:-",
                ],
                [
                    "lattice-add-trans-probs",
                    "--transition-scale=1.0",
                    "--self-loop-scale=0.1",
                    str(model_file),
                    "ark:-",
                    "ark:-",
                ],
                [
                    "lattice-to-nbest",
                    f"--n={nbest}",
                    f"--acoustic-scale={self.acoustic_scale}",
                    "ark:-",
                    "ark:-",
                ],
                [
                    "nbest-to-linear",
                    "ark:-",
                    "ark:/dev/null",  # alignments
                    "ark,t:-",  # transcriptions
                ],
            )

            int2sym_stdout = await self.tools.async_run_pipeline(
                [
                    str(self.tools.egs_utils_dir / "int2sym.pl"),
                    "-f",
                    "2-",
                    str(new_lang_dir / "words.txt"),
                ],
                input=nbest_stdout,
            )
            _LOGGER.debug("nbest: %s", int2sym_stdout.decode(encoding="utf-8"))

            fuzzy_result = await get_fuzzy_text(nbest_stdout, old_lang_dir, self.tools)
            if fuzzy_result is not None:
                text, cost = fuzzy_result
                _LOGGER.debug("Fuzzy cost: %s", cost)
                if cost <= max_fuzzy_cost:
                    return [decode_meta(text)]

            if require_fuzzy:
                return []

            # Gather nbest transcriptions
            texts: List[str] = []
            for line in int2sym_stdout.decode().splitlines():
                if line.startswith("utt-"):
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) > 1:
                        texts.append(decode_meta(parts[1]))

            return texts
