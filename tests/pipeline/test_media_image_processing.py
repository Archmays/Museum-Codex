from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageCms, ImageDraw

from museum_pipeline.media.image_processing import (
    ImageProcessingError,
    build_derivatives,
    compare_preview_visual_match,
    compute_phash64,
    inspect_image_bytes,
    phash_distance,
)


def _image_bytes(image: Image.Image, image_format: str, **save_options: object) -> bytes:
    output = io.BytesIO()
    image.save(output, format=image_format, **save_options)
    return output.getvalue()


def _pattern(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), "#eee7d7")
    draw = ImageDraw.Draw(image)
    draw.rectangle((width // 12, height // 10, width * 5 // 12, height * 9 // 10), fill="#18334f")
    draw.ellipse((width // 2, height // 7, width * 11 // 12, height * 6 // 7), fill="#c55b3c")
    draw.line((0, height - 1, width - 1, 0), fill="#222222", width=max(1, width // 80))
    return image


class MediaImageProcessingTests(unittest.TestCase):
    def test_inspects_magic_mime_decode_dimensions_hash_and_phash(self) -> None:
        payload = _image_bytes(_pattern(96, 64), "JPEG", quality=92)

        record = inspect_image_bytes(payload, "image/jpeg; charset=binary")

        self.assertEqual("JPEG", record["format"])
        self.assertEqual("image/jpeg", record["mime"])
        self.assertEqual((96, 64), (record["width"], record["height"]))
        self.assertEqual((96, 64), (record["display_width"], record["display_height"]))
        self.assertEqual(96 * 64, record["pixels"])
        self.assertEqual(len(payload), record["bytes"])
        self.assertRegex(record["sha256"], r"^sha256:[a-f0-9]{64}$")
        self.assertTrue(record["decode"]["ok"])
        self.assertTrue(record["magic_mime_match"])
        self.assertEqual("phash64-dct-v1", record["phash"]["algorithm"])
        self.assertRegex(record["phash"]["value"], r"^phash64:[a-f0-9]{16}$")

    def test_rejects_mismatch_html_decode_failure_and_pixel_limit(self) -> None:
        png = _image_bytes(_pattern(20, 20), "PNG")
        cases = (
            (png, "image/jpeg", "mime_magic_mismatch", {}),
            (b"<!doctype html><html><body>blocked</body></html>", "image/jpeg", "html_payload", {}),
            (b"\xff\xd8\xff\xe0broken", "image/jpeg", "decode_failed", {}),
            (png, "image/png", "pixel_limit_exceeded", {"max_pixels": 100}),
        )
        for payload, mime, code, options in cases:
            with self.subTest(code=code):
                with self.assertRaises(ImageProcessingError) as caught:
                    inspect_image_bytes(payload, mime, **options)
                self.assertEqual(code, caught.exception.code)

    def test_quality_flags_cover_orientation_border_blank_and_placeholder(self) -> None:
        bordered = Image.new("RGB", (256, 192), "black")
        ImageDraw.Draw(bordered).rectangle((16, 16, 239, 175), fill="white")
        bordered_record = inspect_image_bytes(_image_bytes(bordered, "PNG"), "image/png")
        self.assertTrue(bordered_record["quality"]["flags"]["border_suspected"])

        blank = Image.new("RGB", (256, 192), "white")
        blank_record = inspect_image_bytes(_image_bytes(blank, "PNG"), "image/png")
        self.assertTrue(blank_record["quality"]["flags"]["blank"])
        self.assertTrue(blank_record["quality"]["flags"]["monochrome"])

        tiny = Image.new("RGB", (1, 1), "white")
        tiny_record = inspect_image_bytes(_image_bytes(tiny, "PNG"), "image/png")
        self.assertTrue(tiny_record["quality"]["flags"]["tracking_pixel"])
        self.assertTrue(tiny_record["quality"]["flags"]["placeholder_suspected"])

        oriented = _pattern(80, 40)
        exif = Image.Exif()
        exif[274] = 6
        oriented_record = inspect_image_bytes(
            _image_bytes(oriented, "JPEG", quality=95, exif=exif),
            "image/jpeg",
        )
        self.assertEqual(6, oriented_record["orientation"]["exif"])
        self.assertTrue(oriented_record["orientation"]["requires_normalization"])
        self.assertEqual((40, 80), (oriented_record["display_width"], oriented_record["display_height"]))

    def test_phash_distance_and_preview_visual_match(self) -> None:
        candidate = _pattern(320, 200)
        preview = candidate.resize((160, 100), Image.Resampling.LANCZOS)
        unrelated = Image.new("RGB", (320, 200), "white")
        candidate_bytes = _image_bytes(candidate, "PNG")
        preview_bytes = _image_bytes(preview, "JPEG", quality=88)
        unrelated_bytes = _image_bytes(unrelated, "PNG")

        candidate_hash = compute_phash64(candidate)
        self.assertEqual(0, phash_distance(candidate_hash, candidate_hash))
        self.assertGreater(phash_distance(candidate_hash, compute_phash64(unrelated)), 5)

        match = compare_preview_visual_match(
            candidate_bytes,
            "image/png",
            preview_bytes,
            "image/jpeg",
        )
        self.assertTrue(match["matched"], match)
        self.assertLessEqual(match["phash_distance"], match["max_phash_distance"])

        mismatch = compare_preview_visual_match(
            candidate_bytes,
            "image/png",
            unrelated_bytes,
            "image/png",
            max_phash_distance=5,
        )
        self.assertFalse(mismatch["matched"])
        self.assertIn("phash_distance", mismatch["reasons"])

    def test_preview_comparison_flags_overlay_and_unexpected_site_chrome(self) -> None:
        preview = _pattern(320, 200)
        watermarked = preview.copy()
        overlay = Image.new("RGBA", watermarked.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for offset in range(-200, 520, 48):
            overlay_draw.line((offset, 0, offset + 200, 200), fill=(255, 255, 255, 150), width=12)
        watermarked = Image.alpha_composite(watermarked.convert("RGBA"), overlay).convert("RGB")
        watermark_match = compare_preview_visual_match(
            _image_bytes(watermarked, "PNG"),
            "image/png",
            _image_bytes(preview, "PNG"),
            "image/png",
        )
        self.assertTrue(watermark_match["watermark_overlay_suspected"], watermark_match)
        self.assertIn("watermark_overlay", watermark_match["reasons"])

        chromed = Image.new("RGB", preview.size, "black")
        chromed.paste(preview.resize((280, 160)), (20, 20))
        chrome_match = compare_preview_visual_match(
            _image_bytes(chromed, "PNG"),
            "image/png",
            _image_bytes(preview, "PNG"),
            "image/png",
        )
        self.assertTrue(chrome_match["site_chrome_suspected"], chrome_match)
        self.assertIn("unexpected_border_geometry", chrome_match["reasons"])

        margin = Image.new("RGB", preview.size, "black")
        margin.paste(preview.resize((280, 160)), (20, 20))
        margin_match = compare_preview_visual_match(
            _image_bytes(margin, "PNG"),
            "image/png",
            _image_bytes(margin.resize((160, 100)), "PNG"),
            "image/png",
        )
        self.assertTrue(margin_match["border_geometry_matches"], margin_match)
        self.assertFalse(margin_match["site_chrome_suspected"], margin_match)

    def test_builds_self_verified_derivatives_never_upscales_and_strips_metadata(self) -> None:
        source = _pattern(1000, 500)
        exif = Image.Exif()
        exif[315] = "fixture artist"
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        source_bytes = _image_bytes(source, "JPEG", quality=96, exif=exif, icc_profile=profile)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = build_derivatives(source_bytes, "image/jpeg", output)
            repeated = build_derivatives(source_bytes, "image/jpeg", output)

            self.assertEqual("not_available", result["capabilities"]["avif"]["status"])
            self.assertEqual({"icc_to_srgb"}, {item["transform"]["color"] for item in result["generated"]})
            self.assertEqual(result, repeated)
            self.assertEqual(
                {"320w.jpg", "320w.webp", "640w.jpg", "640w.webp", "960w.jpg", "960w.webp"},
                {item["path"] for item in result["generated"]},
            )
            self.assertEqual([{"width": 1600, "reason": "never_upscale"}], result["skipped"])
            for item in result["generated"]:
                path = output / item["path"]
                self.assertTrue(path.is_file())
                self.assertTrue(item["verification"]["self_verified"])
                self.assertLessEqual(item["width"], 1000)
                self.assertEqual(path.stat().st_size, item["bytes"])
                with Image.open(path) as derivative:
                    derivative.load()
                    self.assertEqual((item["width"], item["height"]), derivative.size)
                    self.assertFalse(derivative.getexif())
                    self.assertNotIn("icc_profile", derivative.info)

        untagged = _image_bytes(_pattern(640, 320), "JPEG", quality=95)
        with tempfile.TemporaryDirectory() as temporary:
            untagged_result = build_derivatives(untagged, "image/jpeg", Path(temporary), widths=(320,))
        self.assertEqual({"assume_srgb"}, {item["transform"]["color"] for item in untagged_result["generated"]})

    def test_derivatives_normalize_exif_orientation(self) -> None:
        source = _pattern(80, 40)
        exif = Image.Exif()
        exif[274] = 6
        source_bytes = _image_bytes(source, "JPEG", quality=95, exif=exif)

        with tempfile.TemporaryDirectory() as temporary:
            result = build_derivatives(source_bytes, "image/jpeg", Path(temporary), widths=(32,))

            self.assertEqual(2, len(result["generated"]))
            self.assertEqual({(32, 64)}, {(item["width"], item["height"]) for item in result["generated"]})
            self.assertTrue(result["source"]["orientation"]["requires_normalization"])

    def test_refuses_transparency_instead_of_silently_flattening_for_jpeg(self) -> None:
        transparent = Image.new("RGBA", (640, 320), (255, 0, 0, 120))
        payload = _image_bytes(transparent, "PNG")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ImageProcessingError) as caught:
                build_derivatives(payload, "image/png", Path(temporary), widths=(320,))
        self.assertEqual("transparent_source_unsupported", caught.exception.code)

    def test_does_not_overwrite_a_conflicting_derivative(self) -> None:
        source = _image_bytes(_pattern(640, 320), "JPEG", quality=95)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            conflict = output / "320w.jpg"
            conflict.write_bytes(b"existing-different-bytes")
            with self.assertRaises(ImageProcessingError) as caught:
                build_derivatives(source, "image/jpeg", output, widths=(320,))
            self.assertEqual("output_conflict", caught.exception.code)
            self.assertEqual(b"existing-different-bytes", conflict.read_bytes())


if __name__ == "__main__":
    unittest.main()
