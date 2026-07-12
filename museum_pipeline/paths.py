from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from museum_pipeline.errors import PipelineError


SAFE_RELATIVE_PATTERN = re.compile(
    r"^(?!/)(?!.*\\)(?!.*:)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._/-]+$"
)
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def safe_relative_path(value: str) -> PurePosixPath:
    if not value or not SAFE_RELATIVE_PATTERN.fullmatch(value):
        raise PipelineError("unsafe_path", "Path must be a safe POSIX relative path")
    result = PurePosixPath(value)
    if result.is_absolute() or result in {PurePosixPath("."), PurePosixPath("..")}:
        raise PipelineError("unsafe_path", "Path must remain relative")
    if any(part in {"", ".", ".."} for part in result.parts):
        raise PipelineError("unsafe_path", "Path contains an unsafe segment")
    if str(result) != value or "//" in value:
        raise PipelineError("unsafe_path", "Path must use one canonical POSIX spelling")
    for part in result.parts:
        stem = part.rstrip(".").split(".", 1)[0].upper()
        if part.endswith(".") or stem in WINDOWS_RESERVED_NAMES:
            raise PipelineError("unsafe_path", "Path contains a Windows-reserved segment")
    return result


def resolve_within(
    root: Path,
    relative: str,
    *,
    must_exist: bool = False,
    reject_symlinks: bool = True,
) -> Path:
    safe = safe_relative_path(relative)
    root_resolved = root.resolve(strict=True)
    candidate = root_resolved.joinpath(*safe.parts)
    if reject_symlinks:
        current = root_resolved
        for part in safe.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise PipelineError("symlink_escape", "Symbolic links are not allowed in governed paths")
    resolved = candidate.resolve(strict=must_exist)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as error:
        raise PipelineError("path_escape", "Resolved path escapes the governed root") from error
    return resolved
