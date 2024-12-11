"""Transcribe WAV files."""

import logging
import shlex
from pathlib import Path
from typing import List, Optional, Union

from .hassil_fst import decode_meta
from .tools import KaldiTools
from .transcribe_util import get_fuzzy_text

_LOGGER = logging.getLogger(__name__)


class KaldiNnet3WavTranscriber:
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
        wav_path: Union[str, Path],
        lang_dir: Union[str, Path],
        nbest: int = 1,
        max_fuzzy_cost: Optional[float] = None,
        require_fuzzy: bool = False,
    ) -> List[str]:
        words_txt = self.graph_dir / "words.txt"
        online_conf = self.model_dir / "model" / "online" / "conf" / "online.conf"
        nbest_stdout = await self.tools.async_run_pipeline(
            [
                "online2-wav-nnet3-latgen-faster",
                "--online=false",
                "--do-endpointing=false",
                f"--word-symbol-table={words_txt}",
                f"--config={online_conf}",
                f"--max-active={self.max_active}",
                f"--lattice-beam={self.lattice_beam}",
                "--acoustic-scale=1.0",
                f"--beam={self.beam}",
                str(self.model_dir / "model" / "model" / "final.mdl"),
                str(self.graph_dir / "HCLG.fst"),
                "ark:echo utt utt|",
                f"scp:echo utt {wav_path}|",
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
        wav_path: Union[str, Path],
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

        nbest_stdout = await self.tools.async_run_pipeline(
            [
                "online2-wav-nnet3-latgen-faster",
                "--online=false",
                "--do-endpointing=false",
                f"--word-symbol-table={words_txt}",
                f"--config={online_conf}",
                f"--max-active={self.max_active}",
                f"--lattice-beam={self.lattice_beam}",
                "--acoustic-scale=1.0",
                f"--beam={self.beam}",
                str(model_file),
                str(self.graph_dir / "HCLG.fst"),
                "ark:echo utt utt|",
                f"scp:echo utt {wav_path}|",
                "ark:-",
            ],
            ["lattice-scale", "--lm-scale=0.0", "ark:-", "ark:-"],
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

        texts: List[str] = []
        for line in int2sym_stdout.decode().splitlines():
            if line.startswith("utt-"):
                parts = line.strip().split(maxsplit=1)
                if len(parts) > 1:
                    texts.append(decode_meta(parts[1]))

        return texts


# -----------------------------------------------------------------------------


# class GmmWavTranscriber:
#     def __init__(
#         self,
#         model_dir: Union[str, Path],
#         graph_dir: Union[str, Path],
#         tools: KaldiTools,
#         max_active: int = 7000,
#         lattice_beam: float = 8.0,
#         acoustic_scale: float = 1.0,
#         beam: float = 24.0,
#     ):
#         self.model_dir = Path(model_dir)
#         self.graph_dir = Path(graph_dir)
#         self.tools = tools

#         self.max_active = max_active
#         self.lattice_beam = lattice_beam
#         self.acoustic_scale = acoustic_scale
#         self.beam = beam

#     async def async_transcribe(
#         self,
#         wav_path: Union[str, Path],
#         nbest: int = 1,
#     ) -> List[str]:
#         with tempfile.TemporaryDirectory() as temp_dir:
#             words_txt = self.graph_dir / "words.txt"
#             mfcc_conf = self.model_dir / "model" / "conf" / "mfcc.conf"
#             model_file = self.model_dir / "model" / "model" / "final.mdl"

#             await self.tools.async_run(
#                 "compute-mfcc-feats",
#                 [
#                     f"--config={mfcc_conf}",
#                     f"scp:echo utt {wav_path}|",
#                     f"ark,scp:{temp_dir}/feats.ark,{temp_dir}/feats.scp",
#                 ],
#             )

#             await self.tools.async_run(
#                 "compute-cmvn-stats",
#                 [
#                     f"scp:{temp_dir}/feats.scp",
#                     f"ark,scp:{temp_dir}/cmvn.ark,{temp_dir}/cmvn.scp",
#                 ],
#             )

#             await self.tools.async_run(
#                 "apply-cmvn",
#                 [
#                     f"scp:{temp_dir}/cmvn.scp",
#                     f"scp:{temp_dir}/feats.scp",
#                     f"ark,scp:{temp_dir}/feats_cmvn.ark,{temp_dir}/feats_cmvn.scp",
#                 ],
#             )

#             await self.tools.async_run(
#                 "add-deltas",
#                 [
#                     f"scp:{temp_dir}/feats_cmvn.scp",
#                     f"ark,scp:{temp_dir}/deltas.ark,{temp_dir}/deltas.scp",
#                 ],
#             )

#             stdout = await self.tools.async_run_pipeline(
#                 [
#                     "gmm-latgen-faster",
#                     f"--word-symbol-table={words_txt}",
#                     f"--max-active={self.max_active}",
#                     f"--lattice-beam={self.lattice_beam}",
#                     "--acoustic-scale=1.0",
#                     f"--beam={self.beam}",
#                     str(model_file),
#                     f"{self.graph_dir}/HCLG.fst",
#                     f"scp:{temp_dir}/deltas.scp",
#                     "ark:-",
#                 ],
#                 [
#                     "lattice-to-nbest",
#                     f"--n={nbest}",
#                     f"--acoustic-scale={self.acoustic_scale}",
#                     "ark:-",
#                     "ark:-",
#                 ],
#                 [
#                     "nbest-to-linear",
#                     "ark:-",
#                     "ark:/dev/null",  # alignments
#                     "ark,t:-",  # transcriptions
#                 ],
#                 [
#                     str(self.tools.egs_utils_dir / "int2sym.pl"),
#                     "-f",
#                     "2-",
#                     str(words_txt),
#                 ],
#                 stderr=asyncio.subprocess.STDOUT,
#             )

#             texts: List[str] = []
#             for line in stdout.decode().splitlines():
#                 if line.startswith("utt-"):
#                     parts = line.strip().split(maxsplit=1)
#                     if len(parts) > 1:
#                         texts.append(parts[1])

#             return texts

#     async def async_transcribe_rescore(
#         self,
#         wav_path: Union[str, Path],
#         old_lang_dir: Union[str, Path],
#         new_lang_dir: Union[str, Path],
#         nbest: int = 1,
#     ) -> List[str]:
#         old_lang_dir = Path(old_lang_dir)
#         new_lang_dir = Path(new_lang_dir)

#         # Get id for #0 disambiguation state
#         phi: Optional[int] = None
#         with open(str(new_lang_dir / "words.txt"), "r", encoding="utf-8") as words_file:
#             for line in words_file:
#                 if line.startswith("#0 "):
#                     phi = int(line.strip().split(maxsplit=1)[1])
#                     break

#         if phi is None:
#             raise ValueError("No value for disambiguation state (#0)")

#         # Create Ldet.fst
#         await self.tools.async_run_pipeline(
#             ["fstprint", str(new_lang_dir / "L_disambig.fst")],
#             ["awk", f"{{if($4 != {phi}){{print;}}}}"],
#             ["fstcompile"],
#             ["fstdeterminizestar"],
#             [
#                 "fstrmsymbols",
#                 str(new_lang_dir / "phones" / "disambig.int"),
#                 "-",
#                 shlex.quote(str(new_lang_dir / "Ldet.fst")),
#             ],
#         )

#         with tempfile.TemporaryDirectory() as temp_dir:
#             words_txt = self.graph_dir / "words.txt"
#             mfcc_conf = self.model_dir / "model" / "conf" / "mfcc.conf"
#             model_file = self.model_dir / "model" / "model" / "final.mdl"
#             # mat_file = self.model_dir / "model" / "model" / "final.mat"

#             await self.tools.async_run(
#                 "compute-mfcc-feats",
#                 [
#                     f"--config={mfcc_conf}",
#                     f"scp:echo utt {wav_path}|",
#                     f"ark:{temp_dir}/feats.ark",
#                 ],
#             )

#             await self.tools.async_run(
#                 "compute-cmvn-stats",
#                 [f"ark:{temp_dir}/feats.ark", f"ark:{temp_dir}/cmvn.ark"],
#             )

#             await self.tools.async_run(
#                 "apply-cmvn",
#                 [
#                     f"ark:{temp_dir}/cmvn.ark",
#                     f"ark:{temp_dir}/feats.ark",
#                     f"ark:{temp_dir}/feats_cmvn.ark",
#                 ],
#             )

#             # await self.tools.async_run(
#             #     "add-deltas",
#             #     [
#             #         f"scp:{temp_dir}/feats_cmvn.scp",
#             #         f"ark,scp:{temp_dir}/deltas.ark,{temp_dir}/deltas.scp",
#             #     ],
#             # )

#             stdout = await self.tools.async_run_pipeline(
#                 [
#                     "gmm-latgen-faster",
#                     f"--word-symbol-table={words_txt}",
#                     f"--max-active={self.max_active}",
#                     f"--lattice-beam={self.lattice_beam}",
#                     "--acoustic-scale=1.0",
#                     f"--beam={self.beam}",
#                     str(model_file),
#                     f"{self.graph_dir}/HCLG.fst",
#                     f"scp:{temp_dir}/deltas.scp",
#                     "ark:-",
#                 ],
#                 ["lattice-scale", "--lm-scale=0.0", "ark:-", "ark:-"],
#                 ["lattice-to-phone-lattice", str(model_file), "ark:-", "ark:-"],
#                 [
#                     "lattice-compose",
#                     "ark:-",
#                     str(new_lang_dir / "Ldet.fst"),
#                     "ark:-",
#                 ],
#                 ["lattice-determinize", "ark:-", "ark:-"],
#                 [
#                     "lattice-compose",
#                     f"--phi-label={phi}",
#                     "ark:-",
#                     str(new_lang_dir / "G.fst"),
#                     "ark:-",
#                 ],
#                 [
#                     "lattice-add-trans-probs",
#                     "--transition-scale=1.0",
#                     "--self-loop-scale=0.1",
#                     str(model_file),
#                     "ark:-",
#                     "ark:-",
#                 ],
#                 [
#                     "lattice-to-nbest",
#                     f"--n={nbest}",
#                     f"--acoustic-scale={self.acoustic_scale}",
#                     "ark:-",
#                     "ark:-",
#                 ],
#                 [
#                     "nbest-to-linear",
#                     "ark:-",
#                     "ark:/dev/null",  # alignments
#                     "ark,t:-",  # transcriptions
#                 ],
#                 [
#                     str(self.tools.egs_utils_dir / "int2sym.pl"),
#                     "-f",
#                     "2-",
#                     str(words_txt),
#                 ],
#                 stderr=asyncio.subprocess.STDOUT,
#             )

#             texts: List[str] = []
#             for line in stdout.decode().splitlines():
#                 if line.startswith("utt-"):
#                     parts = line.strip().split(maxsplit=1)
#                     if len(parts) > 1:
#                         texts.append(parts[1])

#             return texts
