from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from museum_pipeline.canonical_json import canonical_json_bytes


def sha256_bytes(value: bytes, *, prefixed: bool = True) -> str:
    digest = hashlib.sha256(value).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


def sha256_file(path: Path, *, prefixed: bool = True) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    return f"sha256:{value}" if prefixed else value


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))
