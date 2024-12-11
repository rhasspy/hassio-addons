"""Web UI for training."""

import base64
import io
import json
import logging
import re
import shutil
import tarfile
import tempfile
import time
from collections.abc import Collection, Iterable
from logging.handlers import QueueHandler
from pathlib import Path
from queue import Queue
from typing import Any, Dict, List, Optional, TextIO, Tuple, Union
from urllib.request import urlopen

from flask import Flask, Response, redirect, render_template, request
from flask import url_for as flask_url_for
from hassil.intents import Intents
from hassil.util import merge_dict
from rhasspy_speech.const import LangSuffix
from rhasspy_speech.g2p import LexiconDatabase, get_sounds_like, guess_pronunciations
from rhasspy_speech.tools import KaldiTools
from rhasspy_speech.train import train_model as rhasspy_train_model
from werkzeug.middleware.proxy_fix import ProxyFix
from yaml import SafeDumper, safe_dump, safe_load

from .hass_api import get_exposed_dict
from .models import MODELS
from .sample import sample_intents
from .shared import AppState

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger(__name__)


DOWNLOAD_CHUNK_SIZE = 1024 * 10
USER_INTENT = "CustomSentences"


def ingress_url_for(endpoint, **values):
    """Custom url_for that includes X-Ingress-Path dynamically."""
    ingress_path = request.headers.get("X-Ingress-Path", "")
    base_url = flask_url_for(endpoint, **values)
    # Prepend the ingress path if it's present
    return f"{ingress_path}{base_url}" if ingress_path else base_url


def get_app(state: AppState) -> Flask:
    app = Flask(
        "rhasspy_speech",
        template_folder=str(_DIR / "templates"),
        static_folder=str(_DIR / "static"),
    )

    if state.settings.hass_ingress:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)  # type: ignore[assignment]
        app.jinja_env.globals["url_for"] = ingress_url_for

    @app.route("/")
    def index():
        if state.settings.auto_train_model_id:
            return redirect(
                ingress_url_for("manage", id=state.settings.auto_train_model_id)
            )

        return redirect(ingress_url_for("models"))

    @app.route("/models")
    def models():
        downloaded_models = {
            m.id for m in MODELS.values() if (state.settings.models_dir / m.id).is_dir()
        }
        return render_template(
            "models.html",
            available_models=MODELS,
            downloaded_models=downloaded_models,
        )

    @app.route("/manage")
    def manage():
        model_id = request.args["id"]
        suffix = request.args.get("suffix")

        sentences_path = state.settings.sentences_path(model_id, suffix)
        return render_template(
            "manage.html",
            model_id=model_id,
            suffix=suffix,
            suffixes=state.settings.get_suffixes(model_id),
            has_sentences=sentences_path.exists(),
        )

    @app.route("/download")
    def download():
        model_id = request.args["id"]
        return render_template("download.html", model_id=model_id)

    @app.route("/api/download", methods=["POST"])
    def api_download() -> Response:
        model_id = request.args["id"]

        def download_model() -> Iterable[str]:
            try:
                model = MODELS.get(model_id)
                assert model is not None, f"Unknown model: {model_id}"
                with urlopen(
                    model.url
                ) as model_response, tempfile.TemporaryDirectory() as temp_dir:
                    total_bytes: Optional[int] = None
                    content_length = model_response.getheader("Content-Length")
                    if content_length:
                        total_bytes = int(content_length)
                        yield f"Expecting {total_bytes} byte(s)\n"

                    last_report_time = time.monotonic()
                    model_path = Path(temp_dir) / "model.tar.gz"
                    bytes_downloaded = 0
                    with open(model_path, "wb") as model_file:
                        chunk = model_response.read(DOWNLOAD_CHUNK_SIZE)
                        while chunk:
                            model_file.write(chunk)
                            bytes_downloaded += len(chunk)
                            current_time = time.monotonic()
                            if (current_time - last_report_time) > 1:
                                if (total_bytes is not None) and (total_bytes > 0):
                                    yield f"{int((bytes_downloaded / total_bytes) * 100)}%\n"
                                else:
                                    yield f"Bytes downloaded: {bytes_downloaded}\n"
                                last_report_time = current_time
                            chunk = model_response.read(DOWNLOAD_CHUNK_SIZE)

                    yield "Download complete\n"
                    state.settings.models_dir.mkdir(parents=True, exist_ok=True)
                    with tarfile.open(model_path, "r:gz") as model_tar_file:
                        model_tar_file.extractall(state.settings.models_dir)
                    yield "Model extracted\n"
                    yield "Return to models page to continue\n"
            except Exception as err:
                yield f"ERROR: {err}"

        return Response(download_model(), content_type="text/plain")

    @app.route("/api/train", methods=["POST"])
    async def api_train() -> Response:
        model_id = request.args["id"]
        suffix = request.args.get("suffix")

        logger = logging.getLogger("rhasspy_speech")
        logger.setLevel(logging.DEBUG)
        log_queue: "Queue[Optional[logging.LogRecord]]" = Queue()
        handler = QueueHandler(log_queue)
        logger.addHandler(handler)
        text = "Training started\n"

        try:
            if state.settings.hass_auto_train and state.settings.hass_token:
                _LOGGER.debug("Downloading Home Assistant entities")
                lists_path = state.settings.lists_path(model_id, suffix)
                lists_path.parent.mkdir(parents=True, exist_ok=True)
                with open(lists_path, "w", encoding="utf-8") as lists_file:
                    await write_exposed(state, lists_file)

            await train_model(state, model_id, suffix, log_queue)
            while True:
                log_item = log_queue.get()
                if log_item is None:
                    break

                text += log_item.getMessage() + "\n"
            text += "Training complete\n"
        except Exception as err:
            text += f"ERROR: {err}"
        finally:
            logger.removeHandler(handler)

        return Response(text, content_type="text/plain")

    @app.route("/sentences", methods=["GET", "POST"])
    def sentences():
        model_id = request.args["id"]
        suffix = request.args.get("suffix")
        sentences = ""
        sentences_path = state.settings.sentences_path(model_id, suffix)

        if request.method == "POST":
            sentences = request.form["sentences"]
            try:
                with io.StringIO(sentences) as sentences_file:
                    sentences_dict = safe_load(sentences_file)
                    assert "sentences" in sentences_dict, "Missing sentences block"
                    assert sentences_dict["sentences"], "No sentences"

                # Success
                sentences_path.parent.mkdir(parents=True, exist_ok=True)
                sentences_path.write_text(sentences, encoding="utf-8")

                if state.settings.hass_ingress:
                    return redirect(
                        ingress_url_for("manage", id=model_id, suffix=suffix)
                    )

                return redirect(flask_url_for("manage", id=model_id, suffix=suffix))
            except Exception as err:
                return render_template(
                    "sentences.html",
                    model_id=model_id,
                    sentences=sentences,
                    error=err,
                )

        elif sentences_path.exists():
            sentences = sentences_path.read_text(encoding="utf-8")

        return render_template(
            "sentences.html", model_id=model_id, suffix=suffix, sentences=sentences
        )

    @app.route("/delete", methods=["GET", "POST"])
    def delete():
        model_id = request.args["id"]
        suffix = request.args.get("suffix")

        model_data_dir = state.settings.model_data_dir(model_id)
        if model_data_dir.is_dir():
            shutil.rmtree(model_data_dir)

        model_train_dir = state.settings.model_train_dir(model_id, suffix)
        if model_train_dir.is_dir():
            shutil.rmtree(model_train_dir)

        return redirect(ingress_url_for("index"))

    @app.route("/api/hass_exposed", methods=["POST"])
    async def api_hass_exposed() -> str:
        if state.settings.hass_token is None:
            return "No Home Assistant token"

        with io.StringIO() as hass_exposed_file:
            await write_exposed(state, hass_exposed_file)
            return hass_exposed_file.getvalue()

    @app.route("/words", methods=["GET", "POST"])
    def words():
        model_id = request.args["id"]
        words_str = ""
        found = ""
        guessed = ""

        if request.method == "POST":
            words_str = request.form["words"]
            lexicon = LexiconDatabase(
                state.settings.models_dir / model_id / "lexicon.db"
            )

            if "*" in words_str:
                # pylint: disable=protected-access
                cur = lexicon._conn.execute(
                    "SELECT word, phonemes FROM word_phonemes WHERE word LIKE ?",
                    (words_str.replace("*", "%"),),
                )
                for row in cur:
                    found += f'{row[0]}: "/{row[1]}/"\n'

            else:
                words = words_str.split()
                missing_words = set()
                for word in words:
                    if "[" in word:
                        word_prons = get_sounds_like([word], lexicon)
                    else:
                        word_prons = lexicon.lookup(word)

                    if word_prons:
                        for word_pron in word_prons:
                            phonemes = " ".join(word_pron)
                            found += f'{word}: "/{phonemes}/"\n'
                    else:
                        missing_words.add(word)

                if missing_words:
                    for word, phonemes in guess_pronunciations(
                        missing_words,
                        state.settings.models_dir / model_id / "g2p.fst",
                        state.settings.tools_dir / "phonetisaurus",
                    ):
                        guessed += f'{word}: "/{phonemes}/"\n'

        return render_template(
            "words.html",
            model_id=model_id,
            words=words_str,
            found=found,
            guessed=guessed,
        )

    @app.route("/intents")
    def intents():
        model_id = request.args["id"]
        suffix = request.args.get("suffix")

        language = get_locale(model_id)
        intents, _words = get_intents(state, model_id, suffix)

        if intents is not None:
            sentences = sample_intents(intents)

            # HassTurnOn -> Turn On
            sentences = {
                " ".join(
                    re.findall("[A-Z][a-z]*", re.sub("^Hass", "", intent_name))
                ): intent_sentences
                for intent_name, intent_sentences in sentences.items()
            }
        else:
            sentences = {}

        return render_template(
            "intents.html",
            model_id=model_id,
            suffix=suffix,
            sentences=sentences,
            language=language,
            isstring=lambda x: isinstance(x, str),
            decode_list=lambda x: json.loads(
                base64.b64decode(x.encode("utf-8")).decode("utf-8")
            ),
        )

    @app.errorhandler(Exception)
    async def handle_error(err):
        """Return error as text."""
        return (f"{err.__class__.__name__}: {err}", 500)

    return app


# -----------------------------------------------------------------------------


def get_locale(model_id: str) -> str:
    return model_id.split("-", maxsplit=1)[0]


def get_language(model_id: str) -> str:
    return model_id.split("-", maxsplit=1)[0].split("_", maxsplit=1)[0]


def get_intents(
    state: AppState, model_id: str, suffix: Optional[str]
) -> Tuple[Optional[Intents], Optional[Dict[str, Union[str, List[str]]]]]:
    language = get_language(model_id)
    words: Optional[Dict[str, Union[str, List[str]]]] = None

    sentence_files: List[Union[str, Path]] = []
    sentences_path = state.settings.sentences_path(model_id, suffix)
    if sentences_path.exists():
        temp_sentences = tempfile.NamedTemporaryFile("w+", suffix=".yaml")
        with open(sentences_path, "r", encoding="utf-8") as sentences_file:
            intents_dict: Dict[str, Any] = {"language": language}
            sentences_dict = safe_load(sentences_file)
            sentences = sentences_dict.pop("sentences", None)
            words = sentences_dict.pop("words", None)
            if sentences:
                intent_data = []
                plain_sentences = []
                for sentence in sentences:
                    if isinstance(sentence, str):
                        plain_sentences.append(sentence)
                    else:
                        sentence_template = sentence.pop("in", None)
                        if not sentence_template:
                            _LOGGER.warning("Malformed sentence: %s", sentence)
                            continue

                        # Override sentence output
                        sentence_output = sentence.pop("out", None)
                        if sentence_output:
                            sentence.setdefault("metadata", {})
                            sentence["metadata"]["output"] = sentence_output

                        intent_data.append(
                            {"sentences": [sentence_template], **sentence}
                        )

                if plain_sentences:
                    intent_data.append({"sentences": plain_sentences})

                intents_dict["intents"] = {USER_INTENT: {"data": intent_data}}

            merge_dict(intents_dict, sentences_dict)
            safe_dump(intents_dict, temp_sentences)

        temp_sentences.seek(0)
        sentence_files.append(temp_sentences.name)

    if state.settings.hass_builtin_intents:
        intents_path = _DIR / "sentences" / f"{language}.yaml"
        if intents_path.exists():
            sentence_files.append(intents_path)

    if not sentence_files:
        return None, None

    if state.settings.hass_auto_train:
        # Use Home Assistant entities, if they exist
        lists_path = state.settings.lists_path(model_id, suffix)
        if lists_path.exists():
            sentence_files.append(lists_path)

    return Intents.from_files(sentence_files), words


async def write_exposed(state: AppState, yaml_file: TextIO) -> None:
    assert state.settings.hass_token, "No token"

    exposed_dict = await get_exposed_dict(
        state.settings.hass_token, state.settings.hass_websocket_uri
    )
    SafeDumper.ignore_aliases = lambda *args: True  # type: ignore[assignment]
    safe_dump({"lists": exposed_dict}, yaml_file, sort_keys=False)


async def train_model(
    state: AppState,
    model_id: str,
    suffix: Optional[str] = None,
    log_queue: Optional[Queue] = None,
):
    try:
        _LOGGER.info("Training %s (suffix=%s)", model_id, suffix)
        start_time = time.monotonic()
        language = get_language(model_id)
        intents, words = get_intents(state, model_id, suffix)
        if intents is None:
            raise ValueError("No intents")

        model_train_dir = state.settings.model_train_dir(model_id, suffix)
        model_train_dir.mkdir(parents=True, exist_ok=True)

        lang_suffixes: Collection[LangSuffix]
        if state.settings.decode_mode == "grammar":
            lang_suffixes = (LangSuffix.GRAMMAR,)
        elif state.settings.decode_mode == "arpa_rescore":
            lang_suffixes = (LangSuffix.ARPA, LangSuffix.ARPA_RESCORE)
        else:
            lang_suffixes = (LangSuffix.ARPA,)

        await rhasspy_train_model(
            language=language,
            intents=intents,
            model_dir=state.settings.models_dir / model_id,
            train_dir=model_train_dir,
            words=words,
            tools=KaldiTools.from_tools_dir(state.settings.tools_dir),
            lang_suffixes=lang_suffixes,
            rescore_order=state.settings.arpa_rescore_order,
        )
        _LOGGER.debug(
            "Training completed in %s second(s)", time.monotonic() - start_time
        )
    except Exception as err:
        _LOGGER.exception("Unexpected error while training")
        raise err
    finally:
        if log_queue is not None:
            log_queue.put(None)
