from dataclasses import dataclass
from typing import Dict, Optional

URL_FORMAT = "https://huggingface.co/datasets/rhasspy/rhasspy-speech/resolve/main/models/{model_id}.tar.gz?download=true"


@dataclass
class Model:
    id: str
    language: str
    language_code: str
    language_family: str
    attribution: str
    url: str
    version: Optional[str] = None


MODEL_IDS = [
    ("ca_ES-coqui", "Catalan, Spain"),
    ("cs_CZ-rhasspy", "Czech, Czech Republic"),
    ("de_DE-zamia", "German, Germany"),
    ("el_GR-coqui", "Greek, Greece"),
    ("en_US-rhasspy", "English, United States"),
    # ("en_US-zamia", "English, United States"),
    # ("en_US-coqui", "English, United States"),
    ("es_ES-rhasspy", "Spanish, Spain"),
    ("eu_ES-coqui", "Basque, Spain"),
    ("fa_IR-coqui", "Persian, Iran"),
    ("fi_FI-coqui", "Finnish, Finland"),
    ("fr_FR-rhasspy", "French, France"),
    # ("fr_FR-guyot", "French, France"),
    ("hi_IN-coqui", "Hindi, India"),
    ("it_IT-rhasspy", "Italian, Italy"),
    ("lb_LU-coqui", "Luxembourgish, Luxembourg"),
    ("ka_GE-coqui", "Georgian, Georgia"),
    ("mn_MN-coqui", "Mongolian, Mongolia"),
    ("pl_PL-coqui", "Polish, Poland"),
    ("pt_PT-coqui", "Portuguese, Portugal"),
    ("nl_NL-cgn", "Dutch, Netherlands"),
    ("ro_RO-coqui", "Romanian, Romania"),
    ("ru_RU-rhasspy", "Russian, Russia"),
    ("sl_SL-coqui", "Slovenian, Slovenia"),
    ("sw_CD-coqui", "Swahili, Democratic Republic of the Congo"),
    ("ta_IN-coqui", "Tamil, India"),
    ("th_TH-coqui", "Thai, Thailand"),
    ("tr_TR-coqui", "Turkish, Turkey"),
]

MODELS: Dict[str, Model] = {
    model_id: Model(
        id=model_id,
        language=model_lang,
        language_code=model_id.split("-", maxsplit=1)[0],
        language_family=model_id.split("-", maxsplit=1)[0].split("_", maxsplit=1)[0],
        attribution=model_id.split("-", maxsplit=1)[1].capitalize(),
        url=URL_FORMAT.format(model_id=model_id),
    )
    for model_id, model_lang in MODEL_IDS
}
