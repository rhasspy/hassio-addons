import gzip
import logging
import shlex
import shutil
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Optional, Set, Union

from .const import EPS, SIL, SPN, UNK, LangSuffix
from .intent_fst import IntentsToFstContext
from .tools import KaldiTools

_LOGGER = logging.getLogger(__name__)


class KaldiTrainer:
    def __init__(
        self,
        train_dir: Union[str, Path],
        model_dir: Union[str, Path],
        tools: KaldiTools,
        fst_context: IntentsToFstContext,
        eps: str = EPS,
        unk: str = UNK,
        spn_phone: str = SPN,
        sil_phone: str = SIL,
    ) -> None:
        self.train_dir = Path(train_dir).absolute()
        self.model_dir = Path(model_dir).absolute()
        self.tools = tools
        self.fst_context = fst_context
        self.eps = eps
        self.unk = unk
        self.spn_phone = spn_phone
        self.sil_phone = sil_phone

    @property
    def conf_dir(self) -> Path:
        return self.train_dir / "conf"

    def graph_dir(self, suffix: Optional[str] = None) -> Path:
        if suffix:
            return self.train_dir / f"graph_{suffix}"

        return self.train_dir / "graph"

    @property
    def data_dir(self) -> Path:
        return self.train_dir / "data"

    @property
    def data_local_dir(self) -> Path:
        return self.data_dir / "local"

    def lang_dir(self, suffix: Optional[str] = None) -> Path:
        if suffix:
            return self.data_dir / f"lang_{suffix}"

        return self.data_dir / "lang"

    @property
    def dict_local_dir(self) -> Path:
        return self.data_local_dir / "dict"

    def lang_local_dir(self, suffix: Optional[str] = None) -> Path:
        if suffix:
            return self.data_local_dir / f"lang_{suffix}"

        return self.data_local_dir / "lang"

    # -------------------------------------------------------------------------

    async def train(
        self,
        lang_suffixes: Optional[Collection[LangSuffix]] = None,
        rescore_order: int = 5,
    ) -> None:
        if lang_suffixes is None:
            lang_suffixes = (LangSuffix.GRAMMAR, LangSuffix.ARPA)

        # Extend PATH
        self.train_dir.mkdir(parents=True, exist_ok=True)

        # Copy conf
        if self.conf_dir.exists():
            shutil.rmtree(self.conf_dir)

        shutil.copytree(self.model_dir / "conf", self.conf_dir)

        # Delete existing data/graph
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)

        for graph_dir in self.train_dir.glob("graph_*"):
            if not graph_dir.is_dir():
                continue

            shutil.rmtree(graph_dir)

        # ---------------------------------------------------------------------
        # Kaldi Training
        # ---------------------------------------------------------
        # 1. prepare_lang.sh
        # 2. format_lm.sh (or fstcompile)
        # 3. mkgraph.sh
        # 4. prepare_online_decoding.sh
        # ---------------------------------------------------------

        # Create empty path.sh
        path_sh = self.train_dir / "path.sh"
        if not path_sh.is_file():
            path_sh.write_text("")

        # Write pronunciation dictionary
        await self._create_lexicon()

        # Create utils link
        model_utils_link = self.train_dir / "utils"
        model_utils_link.unlink(missing_ok=True)
        model_utils_link.symlink_to(self.tools.egs_utils_dir, target_is_directory=True)

        # 1. prepare_lang.sh
        for lang_suffix in lang_suffixes:
            await self._prepare_lang(lang_suffix)

        # 2. Generate G.fst from skill graph
        if LangSuffix.GRAMMAR in lang_suffixes:
            await self._create_grammar(LangSuffix.GRAMMAR)
            await self._create_fuzzy_fst(LangSuffix.GRAMMAR, self_loops=False)

        if LangSuffix.ARPA in lang_suffixes:
            await self._create_arpa(LangSuffix.ARPA)
            await self._create_fuzzy_fst(LangSuffix.ARPA)

        if LangSuffix.ARPA_RESCORE in lang_suffixes:
            await self._create_arpa(LangSuffix.ARPA_RESCORE, order=rescore_order)

        # 3. mkgraph.sh
        for lang_suffix in lang_suffixes:
            if lang_suffix != LangSuffix.ARPA_RESCORE:
                await self._mkgraph(lang_suffix)

        # 4. prepare_online_decoding.sh
        for lang_suffix in lang_suffixes:
            if lang_suffix != LangSuffix.ARPA_RESCORE:
                await self._prepare_online_decoding(lang_suffix)

    # -------------------------------------------------------------------------

    async def _create_lexicon(self) -> None:
        _LOGGER.debug("Generating lexicon")
        dict_local_dir = self.data_local_dir / "dict"
        dict_local_dir.mkdir(parents=True, exist_ok=True)

        # Copy phones
        phones_dir = self.model_dir / "phones"
        for phone_file in phones_dir.glob("*.txt"):
            shutil.copy(phone_file, dict_local_dir / phone_file.name)

        # Create dictionary
        dictionary_path = dict_local_dir / "lexicon.txt"
        lexicon = self.fst_context.lexicon
        with open(dictionary_path, "w", encoding="utf-8") as dictionary_file:
            missing_words = set()
            for word in sorted(self.fst_context.vocab):
                if word in (self.unk,):
                    continue

                word_found = False
                for word_pron in lexicon.lookup(word):
                    phonemes_str = " ".join(word_pron)
                    print(word, phonemes_str, file=dictionary_file)
                    word_found = True

                if not word_found:
                    missing_words.add(word)

            missing_words_path = self.train_dir / "missing_words_dictionary.txt"
            missing_words_path.unlink(missing_ok=True)

            if missing_words:
                g2p_model_path = self.model_dir.parent / "g2p.fst"
                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".txt", encoding="utf-8"
                ) as missing_words_file, open(
                    missing_words_path, "w", encoding="utf-8"
                ) as missing_dictionary_file:
                    for word in sorted(missing_words):
                        _LOGGER.warning("Guessing pronunciation for %s", word)
                        print(word, file=missing_words_file)

                    missing_words_file.seek(0)
                    phonetisaurus_output = (
                        (
                            await self.tools.async_run(
                                str(self.tools.phonetisaurus_bin),
                                [
                                    f"--model={g2p_model_path}",
                                    f"--wordlist={missing_words_file.name}",
                                ],
                            )
                        )
                        .decode()
                        .splitlines()
                    )
                    for line in phonetisaurus_output:
                        line = line.strip()
                        if line:
                            line_parts = line.split()
                            if len(line_parts) == 2:
                                word = line_parts[0]
                                _LOGGER.warning(
                                    "No pronunciation could be guessed for: '%s'", word
                                )
                                print(word, self.sil_phone, file=dictionary_file)
                                continue

                            if len(line_parts) < 3:
                                continue

                            word = line_parts[0]
                            phonemes = " ".join(line_parts[2:])

                            print(
                                word,
                                phonemes,
                                file=missing_dictionary_file,
                            )
                            print(word, phonemes, file=dictionary_file)

            # Add <unk>
            print(self.unk, self.spn_phone, file=dictionary_file)

            for label in self.fst_context.meta_labels:
                print(label, self.sil_phone, file=dictionary_file)

    async def _prepare_lang(self, lang_type: LangSuffix) -> None:
        await self.tools.async_run(
            "bash",
            [
                str(self.tools.egs_utils_dir / "prepare_lang.sh"),
                str(self.dict_local_dir),
                self.unk,
                str(self.lang_local_dir(lang_type.value)),
                str(self.lang_dir(lang_type.value)),
            ],
            cwd=self.train_dir,
        )

    async def _create_arpa(
        self, lang_type: LangSuffix, order: int = 3, method: str = "witten_bell"
    ) -> None:
        lang_dir = self.lang_dir(lang_type.value)
        fst_path = lang_dir / "G.arpa.fst"
        text_fst_path = fst_path.with_suffix(".fst.txt")
        arpa_path = lang_dir / "lm.arpa"

        with open(text_fst_path, "w", encoding="utf-8") as text_fst_file:
            self.fst_context.fst_file.seek(0)
            shutil.copyfileobj(self.fst_context.fst_file, text_fst_file)

        await self.tools.async_run(
            "fstcompile",
            [
                shlex.quote(f"--isymbols={lang_dir}/words.txt"),
                shlex.quote(f"--osymbols={lang_dir}/words.txt"),
                "--keep_isymbols=true",
                "--keep_osymbols=true",
                shlex.quote(str(text_fst_path)),
                shlex.quote(str(fst_path)),
            ],
        )
        await self.tools.async_run_pipeline(
            [
                "ngramcount",
                f"--order={order}",
                shlex.quote(str(fst_path)),
                "-",
            ],
            [
                "ngrammake",
                f"--method={method}",
            ],
            [
                "ngramprint",
                "--ARPA",
                "-",
                shlex.quote(str(arpa_path)),
            ],
        )

        lang_local_dir = self.lang_local_dir(lang_type.value)
        arpa_gz_path = lang_local_dir / "lm.arpa.gz"
        with open(arpa_path, "r", encoding="utf-8") as arpa_file, gzip.open(
            arpa_gz_path, "wt", encoding="utf-8"
        ) as arpa_gz_file:
            shutil.copyfileobj(arpa_file, arpa_gz_file)

        await self.tools.async_run(
            "bash",
            [
                str(self.tools.egs_utils_dir / "format_lm.sh"),
                str(lang_dir),
                str(arpa_gz_path),
                str(self.dict_local_dir / "lexicon.txt"),
                str(lang_dir),
            ],
        )

    async def _create_grammar(self, lang_type: LangSuffix) -> None:
        fst_file = self.fst_context.fst_file
        lang_dir = self.lang_dir(lang_type.value)
        fst_path = lang_dir / "G.fst"
        text_fst_path = fst_path.with_suffix(".fst.txt")

        with open(text_fst_path, "w", encoding="utf-8") as text_fst_file:
            fst_file.seek(0)
            shutil.copyfileobj(fst_file, text_fst_file)

        await self.tools.async_run_pipeline(
            [
                "fstcompile",
                shlex.quote(f"--isymbols={lang_dir}/words.txt"),
                shlex.quote(f"--osymbols={lang_dir}/words.txt"),
                "--keep_isymbols=false",
                "--keep_osymbols=false",
                "--keep_state_numbering=true",
                shlex.quote(str(text_fst_path)),
                "-",
            ],
            ["fstproject", "--project_type=input"],  # needed for determinization
            ["fstdeterminize"],
            ["fstminimize"],
            [
                "fstarcsort",
                "--sort_type=ilabel",
                "-",
                shlex.quote(str(fst_path)),
            ],
        )

    async def _create_fuzzy_fst(
        self, lang_type: LangSuffix, self_loops: bool = True
    ) -> None:
        lang_dir = self.lang_dir(lang_type.value)
        fst_path = lang_dir / f"G.{lang_type.value}.fst"
        if not fst_path.exists():
            fst_path = lang_dir / "G.fst"

        text_fst_path = fst_path.with_suffix(".fst.txt")

        # Create a version of the FST with self loops that allow skipping words
        fuzzy_fst_path = lang_dir / "G.fuzzy.fst"
        text_fuzzy_fst_path = fuzzy_fst_path.with_suffix(".fst.txt")
        _LOGGER.debug("Creating fuzzy FST at %s", fuzzy_fst_path)

        states: Set[str] = set()

        # Copy transitions and add self loops
        with open(text_fst_path, "r", encoding="utf-8") as text_fst_file, open(
            text_fuzzy_fst_path, "w", encoding="utf-8"
        ) as text_fuzzy_fst_file:
            for line in text_fst_file:
                line = line.strip()
                if not line:
                    continue

                # Copy transition
                print(line, file=text_fuzzy_fst_file)

                state = line.split(maxsplit=1)[0]
                if state in states:
                    continue

                states.add(state)

            # Create self loops
            for state in states:
                # No penalty for <eps>
                print(state, state, self.eps, self.eps, 0.0, file=text_fuzzy_fst_file)

                for word in self.fst_context.vocab:
                    if word[0] in ("<", "_"):
                        # Skip meta words
                        continue

                    # Penalty for word removal
                    print(state, state, word, self.eps, 1.0, file=text_fuzzy_fst_file)

        await self.tools.async_run_pipeline(
            [
                "fstcompile",
                shlex.quote(f"--isymbols={lang_dir}/words.txt"),
                shlex.quote(f"--osymbols={lang_dir}/words.txt"),
                "--keep_isymbols=true",
                "--keep_osymbols=true",
                shlex.quote(str(text_fuzzy_fst_path)),
                "-",
            ],
            [
                "fstarcsort",
                "--sort_type=ilabel",
                "-",
                shlex.quote(str(fuzzy_fst_path)),
            ],
        )

    async def _mkgraph(self, lang_type: LangSuffix) -> None:
        lang_dir = self.lang_dir(lang_type.value)
        if not lang_dir.is_dir():
            _LOGGER.warning("Lang dir does not exist: %s", lang_dir)
            return

        await self.tools.async_run(
            "bash",
            [
                str(self.tools.egs_utils_dir / "mkgraph.sh"),
                "--self-loop-scale",
                "1.0",
                str(lang_dir),
                str(self.model_dir / "model"),
                str(self.graph_dir(lang_type.value)),
            ],
        )

    async def _prepare_online_decoding(self, lang_type: LangSuffix) -> None:
        extractor_dir = self.model_dir / "extractor"
        if not extractor_dir.is_dir():
            _LOGGER.warning("Extractor dir does not exist: %s", extractor_dir)
            return

        # Generate online.conf
        mfcc_conf = self.model_dir / "conf" / "mfcc_hires.conf"
        await self.tools.async_run(
            "bash",
            [
                str(
                    self.tools.egs_steps_dir
                    / "online"
                    / "nnet3"
                    / "prepare_online_decoding.sh"
                ),
                "--mfcc-config",
                str(mfcc_conf),
                str(self.lang_dir(lang_type.value)),
                str(extractor_dir),
                str(self.model_dir / "model"),
                str(self.model_dir / "online"),
            ],
            cwd=self.train_dir,
        )
