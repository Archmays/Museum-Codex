from __future__ import annotations

import re
import unicodedata

from museum_pipeline.errors import PipelineError


BCP47_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def normalize_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def validate_language_tag(value: str) -> str:
    if BCP47_PATTERN.fullmatch(value) is None:
        raise PipelineError("language_tag_invalid", "Language tag is not a supported BCP 47 form")
    return value
