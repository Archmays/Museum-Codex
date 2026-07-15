from __future__ import annotations

import hashlib
import io
import math
import os
import re
import tempfile
import warnings
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import PIL
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError


DEFAULT_MAX_PIXELS = 40_000_000
DEFAULT_DERIVATIVE_WIDTHS = (320, 640, 960, 1600)
PHASH_ALGORITHM = "phash64-dct-v1"
PROCESSOR_VERSION = "1.1.0"

_FORMAT_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
_MIME_ALIASES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
}
_PHASH_PATTERN = re.compile(r"^(?:phash64:)?([a-fA-F0-9]{16})$")


class ImageProcessingError(ValueError):
    """A fail-closed image error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def inspect_image_bytes(
    payload: bytes,
    declared_mime: str,
    *,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> dict[str, Any]:
    """Validate image bytes and return deterministic technical/quality evidence."""

    raw = _require_bytes(payload)
    canonical_mime = _canonical_mime(declared_mime)
    detected_format = _detect_magic(raw)
    detected_mime = _FORMAT_MIME[detected_format]
    if canonical_mime != detected_mime:
        raise ImageProcessingError(
            "mime_magic_mismatch",
            f"Declared MIME {canonical_mime!r} does not match {detected_mime!r} magic bytes",
        )

    image = _decode(raw, detected_format, max_pixels=max_pixels)
    orientation, orientation_error = _read_orientation(image)
    try:
        display_image = ImageOps.exif_transpose(image)
    except Exception as exc:
        raise ImageProcessingError("orientation_failed", f"EXIF orientation could not be applied: {exc}") from exc
    quality = _quality_assessment(display_image)
    phash = compute_phash64(display_image)
    icc_profile = image.info.get("icc_profile")
    record: dict[str, Any] = {
        "format": detected_format,
        "mime": detected_mime,
        "declared_mime": canonical_mime,
        "magic_mime_match": True,
        "bytes": len(raw),
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "width": image.width,
        "height": image.height,
        "display_width": display_image.width,
        "display_height": display_image.height,
        "pixels": image.width * image.height,
        "mode": image.mode,
        "decode": {"ok": True, "decoder": f"Pillow {PIL.__version__}"},
        "orientation": {
            "exif": orientation,
            "requires_normalization": orientation not in {None, 1},
            "read_error": orientation_error,
        },
        "color": {
            "icc_profile_present": isinstance(icc_profile, bytes) and bool(icc_profile),
            "icc_profile_bytes": len(icc_profile) if isinstance(icc_profile, bytes) else 0,
            "transparency_present": _has_transparency(image),
        },
        "quality": quality,
        "phash": {"algorithm": PHASH_ALGORITHM, "value": phash},
    }
    return record


def compute_phash64(image: Image.Image) -> str:
    """Return a deterministic 64-bit DCT perceptual hash without NumPy."""

    if not isinstance(image, Image.Image):
        raise TypeError("compute_phash64 requires a Pillow Image")
    normalized = ImageOps.exif_transpose(image).convert("L").resize((32, 32), Image.Resampling.LANCZOS)
    values = [float(value) for value in normalized.getdata()]
    cosine = [
        [math.cos(math.pi * (2 * position + 1) * frequency / 64.0) for position in range(32)]
        for frequency in range(8)
    ]
    row_terms = [
        [sum(values[row * 32 + column] * cosine[frequency][column] for column in range(32)) for frequency in range(8)]
        for row in range(32)
    ]
    coefficients: list[float] = []
    for vertical in range(8):
        vertical_scale = 1 / math.sqrt(2) if vertical == 0 else 1.0
        for horizontal in range(8):
            horizontal_scale = 1 / math.sqrt(2) if horizontal == 0 else 1.0
            coefficient = sum(row_terms[row][horizontal] * cosine[vertical][row] for row in range(32))
            coefficients.append(coefficient * vertical_scale * horizontal_scale)
    threshold = median(coefficients[1:])
    hash_value = 0
    for coefficient in coefficients:
        hash_value = (hash_value << 1) | int(coefficient > threshold)
    return f"phash64:{hash_value:016x}"


def phash_distance(left: str, right: str) -> int:
    """Return the Hamming distance between two 64-bit perceptual hashes."""

    left_value = _parse_phash(left)
    right_value = _parse_phash(right)
    return (left_value ^ right_value).bit_count()


def compare_preview_visual_match(
    candidate_bytes: bytes,
    candidate_mime: str,
    preview_bytes: bytes,
    preview_mime: str,
    *,
    max_phash_distance: int = 12,
    max_aspect_ratio_delta: float = 0.08,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> dict[str, Any]:
    """Compare official preview and acquired bytes using pHash plus aspect ratio."""

    if not isinstance(max_phash_distance, int) or not 0 <= max_phash_distance <= 64:
        raise ValueError("max_phash_distance must be an integer from 0 to 64")
    if not isinstance(max_aspect_ratio_delta, (int, float)) or max_aspect_ratio_delta < 0:
        raise ValueError("max_aspect_ratio_delta must be non-negative")
    candidate = inspect_image_bytes(candidate_bytes, candidate_mime, max_pixels=max_pixels)
    preview = inspect_image_bytes(preview_bytes, preview_mime, max_pixels=max_pixels)
    distance = phash_distance(candidate["phash"]["value"], preview["phash"]["value"])
    candidate_ratio = candidate["display_width"] / candidate["display_height"]
    preview_ratio = preview["display_width"] / preview["display_height"]
    ratio_delta = abs(candidate_ratio - preview_ratio) / max(candidate_ratio, preview_ratio)
    reasons: list[str] = []
    if distance > max_phash_distance:
        reasons.append("phash_distance")
    if ratio_delta > max_aspect_ratio_delta:
        reasons.append("aspect_ratio")
    if candidate["quality"]["flags"]["placeholder_suspected"]:
        reasons.append("candidate_placeholder")
    candidate_border = candidate["quality"]["flags"]["border_suspected"]
    preview_border = preview["quality"]["flags"]["border_suspected"]
    candidate_border_edges = candidate["quality"]["flags"]["border_edges"]
    preview_border_edges = preview["quality"]["flags"]["border_edges"]
    border_geometry_matches = (
        candidate_border == preview_border
        and set(candidate_border_edges) == set(preview_border_edges)
    )
    site_chrome_suspected = candidate_border and not border_geometry_matches
    watermark_overlay_suspected = 2 < distance <= max_phash_distance and ratio_delta <= max_aspect_ratio_delta
    if site_chrome_suspected:
        reasons.append("unexpected_border_geometry")
    if watermark_overlay_suspected:
        reasons.append("watermark_overlay")
    return {
        "matched": not reasons,
        "algorithm": PHASH_ALGORITHM,
        "candidate_phash": candidate["phash"]["value"],
        "preview_phash": preview["phash"]["value"],
        "phash_distance": distance,
        "max_phash_distance": max_phash_distance,
        "aspect_ratio_delta": round(ratio_delta, 6),
        "max_aspect_ratio_delta": max_aspect_ratio_delta,
        "candidate_border_suspected": candidate_border,
        "candidate_border_edges": candidate_border_edges,
        "preview_border_suspected": preview_border,
        "preview_border_edges": preview_border_edges,
        "border_geometry_matches": border_geometry_matches,
        "site_chrome_suspected": site_chrome_suspected,
        "watermark_overlay_suspected": watermark_overlay_suspected,
        "reasons": reasons,
    }


def build_derivatives(
    source_bytes: bytes,
    source_mime: str,
    output_dir: Path,
    *,
    widths: Iterable[int] = DEFAULT_DERIVATIVE_WIDTHS,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    jpeg_quality: int = 85,
    webp_quality: int = 82,
) -> dict[str, Any]:
    """Build idempotent JPEG/WebP derivatives and verify every installed byte."""

    requested_widths = _validated_widths(widths)
    if not 1 <= jpeg_quality <= 95:
        raise ValueError("jpeg_quality must be between 1 and 95")
    if not 1 <= webp_quality <= 100:
        raise ValueError("webp_quality must be between 1 and 100")
    destination = Path(output_dir)
    source_record = inspect_image_bytes(source_bytes, source_mime, max_pixels=max_pixels)
    source_image = _decode(_require_bytes(source_bytes), source_record["format"], max_pixels=max_pixels)
    normalized, color_transform = _normalize_for_derivatives(source_image)

    generated: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for width in requested_widths:
        if width > normalized.width:
            skipped.append({"width": width, "reason": "never_upscale"})
            continue
        height = max(1, round(normalized.height * width / normalized.width))
        resized = normalized.copy() if (width, height) == normalized.size else normalized.resize(
            (width, height), Image.Resampling.LANCZOS
        )
        for image_format, extension, mime, quality in (
            ("JPEG", "jpg", "image/jpeg", jpeg_quality),
            ("WEBP", "webp", "image/webp", webp_quality),
        ):
            encoded = _encode_derivative(resized, image_format, quality)
            verification = _verify_derivative_bytes(
                encoded,
                mime,
                expected_size=(width, height),
                max_pixels=max_pixels,
            )
            relative_path = f"{width}w.{extension}"
            installed = _install_without_overwrite(destination / relative_path, encoded)
            installed_verification = _verify_derivative_bytes(
                installed,
                mime,
                expected_size=(width, height),
                max_pixels=max_pixels,
            )
            if verification["sha256"] != installed_verification["sha256"]:
                raise ImageProcessingError("output_verification_failed", f"Installed bytes drifted for {relative_path}")
            generated.append(
                {
                    "path": relative_path,
                    "format": image_format,
                    "mime": mime,
                    "width": width,
                    "height": height,
                    "pixels": width * height,
                    "bytes": len(installed),
                    "sha256": installed_verification["sha256"],
                    "phash64": installed_verification["phash64"],
                    "source_sha256": source_record["sha256"],
                    "transform": {
                        "orientation": "exif_transpose" if source_record["orientation"]["requires_normalization"] else "identity",
                        "color": color_transform,
                        "resize": "lanczos" if (width, height) != normalized.size else "identity",
                        "metadata": "stripped",
                        "upscaled": False,
                        "quality": quality,
                    },
                    "verification": {
                        "self_verified": True,
                        "magic_mime_decode": True,
                        "dimensions_match": True,
                        "metadata_stripped": True,
                    },
                }
            )

    return {
        "schema_version": "1.0.0",
        "processor": {
            "name": "museum_pipeline.media.image_processing",
            "version": PROCESSOR_VERSION,
            "pillow_version": PIL.__version__,
        },
        "source": source_record,
        "requested_widths": requested_widths,
        "capabilities": {"avif": _avif_capability()},
        "generated": generated,
        "skipped": skipped,
    }


def _require_bytes(payload: bytes) -> bytes:
    if not isinstance(payload, bytes):
        raise TypeError("image payload must be bytes")
    if not payload:
        raise ImageProcessingError("empty_payload", "Image payload is empty")
    return payload


def _canonical_mime(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ImageProcessingError("mime_missing", "A declared image MIME type is required")
    essence = value.split(";", 1)[0].strip().lower()
    canonical = _MIME_ALIASES.get(essence)
    if canonical is None:
        raise ImageProcessingError("mime_unsupported", f"Unsupported image MIME type: {essence!r}")
    return canonical


def _detect_magic(payload: bytes) -> str:
    if payload.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return "WEBP"
    prefix = payload[:1024].lstrip().lower()
    if prefix.startswith((b"<!doctype html", b"<html", b"<?xml")) or b"<html" in prefix:
        raise ImageProcessingError("html_payload", "Response bytes contain HTML/XML instead of an image")
    raise ImageProcessingError("magic_unsupported", "Image magic bytes are not JPEG, PNG, or WebP")


def _decode(payload: bytes, expected_format: str, *, max_pixels: int) -> Image.Image:
    if not isinstance(max_pixels, int) or isinstance(max_pixels, bool) or max_pixels < 1:
        raise ValueError("max_pixels must be a positive integer")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(payload))
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageProcessingError("decompression_bomb", str(exc)) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageProcessingError("decode_failed", f"Pillow could not identify the image: {exc}") from exc
    observed_format = str(image.format or "").upper()
    if observed_format == "JPG":
        observed_format = "JPEG"
    if observed_format != expected_format:
        raise ImageProcessingError(
            "decoder_format_mismatch",
            f"Magic bytes identify {expected_format}, but Pillow decoded {observed_format or 'unknown'}",
        )
    if image.width < 1 or image.height < 1:
        raise ImageProcessingError("invalid_dimensions", "Image dimensions must be positive")
    pixels = image.width * image.height
    if pixels > max_pixels:
        raise ImageProcessingError(
            "pixel_limit_exceeded",
            f"Image has {pixels} pixels; configured limit is {max_pixels}",
        )
    try:
        image.load()
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise ImageProcessingError("decode_failed", f"Image payload is truncated or corrupt: {exc}") from exc
    return image


def _read_orientation(image: Image.Image) -> tuple[int | None, str | None]:
    try:
        value = image.getexif().get(274, 1)
        return (int(value), None) if value is not None else (None, None)
    except (OSError, TypeError, ValueError) as exc:
        return None, str(exc)


def _quality_assessment(image: Image.Image) -> dict[str, Any]:
    sample = image.convert("RGB")
    sample.thumbnail((512, 512), Image.Resampling.LANCZOS)
    gray = sample.convert("L")
    histogram = gray.histogram()
    total = sum(histogram)
    entropy = -sum(
        (count / total) * math.log2(count / total)
        for count in histogram
        if count
    )
    luma_sum = sum(value * count for value, count in enumerate(histogram))
    luma_mean = luma_sum / total
    luma_variance = sum(((value - luma_mean) ** 2) * count for value, count in enumerate(histogram)) / total
    luma_stddev = math.sqrt(luma_variance)
    luma_min, luma_max = gray.getextrema()
    blur_score = _laplacian_variance(gray)
    colorfulness = _mean_channel_spread(sample)
    border_suspected, border_edges = _border_flags(gray)
    blank = (luma_max - luma_min) <= 2 or luma_stddev < 1.0
    monochrome = colorfulness <= 2.0
    tracking_pixel = image.width <= 4 and image.height <= 4
    low_resolution = image.width < 128 or image.height < 128 or image.width * image.height < 32_768
    placeholder_reasons: list[str] = []
    if tracking_pixel:
        placeholder_reasons.append("tracking_pixel")
    if low_resolution and blank:
        placeholder_reasons.append("low_resolution_blank")
    elif low_resolution and entropy < 2.0:
        placeholder_reasons.append("low_resolution_low_entropy")
    flags = {
        "blank": blank,
        "monochrome": monochrome,
        "blurred": blur_score < 20.0,
        "low_resolution": low_resolution,
        "tracking_pixel": tracking_pixel,
        "placeholder_suspected": bool(placeholder_reasons),
        "placeholder_reasons": placeholder_reasons,
        "border_suspected": border_suspected,
        "border_edges": border_edges,
    }
    return {
        "entropy_bits": round(entropy, 6),
        "blur_laplacian_variance": round(blur_score, 6),
        "luma_mean": round(luma_mean, 6),
        "luma_stddev": round(luma_stddev, 6),
        "luma_range": [luma_min, luma_max],
        "mean_channel_spread": round(colorfulness, 6),
        "flags": flags,
        "thresholds": {
            "blur_laplacian_variance_below": 20.0,
            "monochrome_channel_spread_at_most": 2.0,
            "max_quality_sample": 512,
        },
    }


def _laplacian_variance(gray: Image.Image) -> float:
    width, height = gray.size
    if width < 3 or height < 3:
        return 0.0
    values = list(gray.getdata())
    count = 0
    total = 0.0
    total_squared = 0.0
    for row in range(1, height - 1):
        offset = row * width
        for column in range(1, width - 1):
            index = offset + column
            laplacian = (
                4 * values[index]
                - values[index - 1]
                - values[index + 1]
                - values[index - width]
                - values[index + width]
            )
            total += laplacian
            total_squared += laplacian * laplacian
            count += 1
    mean = total / count
    return max(0.0, total_squared / count - mean * mean)


def _mean_channel_spread(image: Image.Image) -> float:
    total = 0
    count = 0
    for red, green, blue in image.getdata():
        total += max(red, green, blue) - min(red, green, blue)
        count += 1
    return total / max(1, count)


def _border_flags(gray: Image.Image) -> tuple[bool, list[str]]:
    width, height = gray.size
    if width < 16 or height < 16:
        return False, []
    pixels = gray.load()
    band = max(2, round(min(width, height) * 0.04))
    center_values = [
        pixels[column, row]
        for row in range(height // 4, max(height // 4 + 1, height * 3 // 4))
        for column in range(width // 4, max(width // 4 + 1, width * 3 // 4))
    ]
    center_mean = sum(center_values) / len(center_values)
    edge_values = {
        "top": [pixels[column, row] for row in range(band) for column in range(width)],
        "bottom": [pixels[column, row] for row in range(height - band, height) for column in range(width)],
        "left": [pixels[column, row] for row in range(height) for column in range(band)],
        "right": [pixels[column, row] for row in range(height) for column in range(width - band, width)],
    }
    flagged: list[str] = []
    for name, values in edge_values.items():
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        if math.sqrt(variance) <= 4.0 and abs(mean - center_mean) >= 12.0:
            flagged.append(name)
    opposing = {"top", "bottom"}.issubset(flagged) or {"left", "right"}.issubset(flagged)
    return len(flagged) >= 3 or opposing, flagged


def _has_transparency(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        alpha = image.getchannel("A")
        return alpha.getextrema()[0] < 255
    if image.mode == "P" and "transparency" in image.info:
        return image.convert("RGBA").getchannel("A").getextrema()[0] < 255
    return False


def _parse_phash(value: str) -> int:
    if not isinstance(value, str):
        raise ValueError("pHash must be a string")
    match = _PHASH_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("pHash must be exactly 64 bits encoded as 16 hexadecimal characters")
    return int(match.group(1), 16)


def _validated_widths(widths: Iterable[int]) -> list[int]:
    try:
        values = list(widths)
    except TypeError as exc:
        raise ValueError("widths must be an iterable of positive integers") from exc
    if not values or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in values):
        raise ValueError("widths must contain positive integers")
    if len(values) != len(set(values)):
        raise ValueError("widths must not contain duplicates")
    return sorted(values)


def _normalize_for_derivatives(image: Image.Image) -> tuple[Image.Image, str]:
    oriented = ImageOps.exif_transpose(image)
    if _has_transparency(oriented):
        raise ImageProcessingError(
            "transparent_source_unsupported",
            "JPEG fallback would require silently flattening transparency",
        )
    icc_profile = oriented.info.get("icc_profile")
    if isinstance(icc_profile, bytes) and icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
            destination_profile = ImageCms.createProfile("sRGB")
            working = oriented if oriented.mode in {"RGB", "CMYK", "LAB"} else oriented.convert("RGB")
            converted = ImageCms.profileToProfile(
                working,
                source_profile,
                destination_profile,
                outputMode="RGB",
                renderingIntent=ImageCms.Intent.PERCEPTUAL,
            )
        except Exception as exc:
            raise ImageProcessingError("icc_conversion_failed", f"ICC profile could not be normalized to sRGB: {exc}") from exc
        transform = "icc_to_srgb"
    else:
        converted = oriented.convert("RGB")
        transform = "assume_srgb"
    stripped = Image.frombytes("RGB", converted.size, converted.tobytes())
    return stripped, transform


def _encode_derivative(image: Image.Image, image_format: str, quality: int) -> bytes:
    output = io.BytesIO()
    if image_format == "JPEG":
        image.save(
            output,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling="4:2:0",
        )
    elif image_format == "WEBP":
        image.save(output, format="WEBP", quality=quality, method=6)
    else:
        raise ValueError(f"Unsupported derivative format: {image_format}")
    return output.getvalue()


def _verify_derivative_bytes(
    payload: bytes,
    mime: str,
    *,
    expected_size: tuple[int, int],
    max_pixels: int,
) -> dict[str, str]:
    inspection = inspect_image_bytes(payload, mime, max_pixels=max_pixels)
    if (inspection["width"], inspection["height"]) != expected_size:
        raise ImageProcessingError(
            "output_dimensions_mismatch",
            f"Expected derivative dimensions {expected_size}, got {(inspection['width'], inspection['height'])}",
        )
    image = _decode(payload, inspection["format"], max_pixels=max_pixels)
    if image.getexif():
        raise ImageProcessingError("output_metadata_present", "Derivative still contains EXIF metadata")
    if image.info.get("icc_profile"):
        raise ImageProcessingError("output_metadata_present", "Derivative still contains an ICC profile")
    return {"sha256": inspection["sha256"], "phash64": inspection["phash"]["value"]}


def _install_without_overwrite(path: Path, payload: bytes) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing != payload:
            raise ImageProcessingError("output_conflict", f"Refusing to overwrite different bytes at {path.name}")
        return existing

    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            existing = path.read_bytes()
            if existing != payload:
                raise ImageProcessingError("output_conflict", f"Refusing to overwrite different bytes at {path.name}")
        except OSError:
            try:
                with path.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                existing = path.read_bytes()
                if existing != payload:
                    raise ImageProcessingError("output_conflict", f"Refusing to overwrite different bytes at {path.name}")
        installed = path.read_bytes()
        if installed != payload:
            raise ImageProcessingError("output_verification_failed", f"Installed bytes do not match encoded bytes at {path.name}")
        return installed
    finally:
        temporary.unlink(missing_ok=True)


def _avif_capability() -> dict[str, Any]:
    Image.init()
    available = "AVIF" in Image.SAVE and Image.registered_extensions().get(".avif") == "AVIF"
    if available:
        return {"status": "available", "generated": False, "reason": "AVIF is not in the required derivative set"}
    return {
        "status": "not_available",
        "generated": False,
        "reason": f"Pillow {PIL.__version__} has no registered AVIF encoder",
    }


__all__ = [
    "DEFAULT_DERIVATIVE_WIDTHS",
    "DEFAULT_MAX_PIXELS",
    "ImageProcessingError",
    "build_derivatives",
    "compare_preview_visual_match",
    "compute_phash64",
    "inspect_image_bytes",
    "phash_distance",
]
