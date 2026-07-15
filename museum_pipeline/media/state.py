from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from museum_pipeline.canonical_json import canonical_json_bytes, write_canonical_json
from museum_pipeline.media.constants import MEDIA_VAULT


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: Any) -> bool:
    """Write a governed artifact once; an identical rerun is an idempotent no-op."""
    assert_vault_path(path)
    payload = canonical_json_bytes(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"governed media state already exists with different bytes: {path.name}")
        return False
    write_canonical_json(path, value)
    return True


def write_bytes_once(path: Path, payload: bytes) -> bool:
    """Atomically install immutable evidence bytes without overwriting."""
    assert_vault_path(path)
    if path.exists():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
            raise ValueError(f"immutable media evidence already exists with different bytes: {path.name}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise ValueError(f"immutable media evidence appeared concurrently: {path.name}")
        os.link(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def replace_generated(path: Path, value: Any) -> None:
    """Atomically replace a reproducible aggregate, never a source snapshot or original."""
    candidate = Path(path).absolute()
    try:
        candidate.relative_to(MEDIA_VAULT.absolute())
    except ValueError:
        _reject_link_components(candidate, context="generated media paths")
    else:
        assert_vault_path(candidate)
    write_canonical_json(path, value)


def assert_vault_path(path: Path) -> None:
    raw_root = MEDIA_VAULT.absolute()
    raw_candidate = Path(path).absolute()
    try:
        raw_candidate.relative_to(raw_root)
    except ValueError as error:
        raise ValueError("media state path escaped the governed vault") from error
    _reject_link_components(raw_candidate, context="the governed media vault")
    root = raw_root.resolve()
    candidate = raw_candidate.resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise ValueError("media state path escaped the governed vault")


def _is_junction(path: Path) -> bool:
    """Return whether *path* is a Windows junction without classifying hardlinks as links."""
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _reject_link_components(path: Path, *, context: str) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(f"symlinks are forbidden in {context}")
        if _is_junction(component):
            raise ValueError(f"junctions are forbidden in {context}")
