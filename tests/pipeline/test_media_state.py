from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import museum_pipeline.media.state as media_state
from museum_pipeline.media.acquisition import _persist_failure


class MediaStateTests(unittest.TestCase):
    def test_json_write_rejects_a_symlinked_parent_before_creating_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            link = root / "link"
            link.mkdir()
            original_is_symlink = Path.is_symlink

            def simulated_is_symlink(path: Path) -> bool:
                return path == link or original_is_symlink(path)

            output = link / "record.json"
            with (
                patch.object(media_state, "MEDIA_VAULT", root),
                patch.object(Path, "is_symlink", autospec=True, side_effect=simulated_is_symlink),
            ):
                with self.assertRaisesRegex(ValueError, "symlinks are forbidden"):
                    media_state.write_once(output, {"ok": True})
            self.assertFalse(output.exists())

    def test_json_write_rejects_a_junction_parent_before_creating_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            junction = root / "junction"
            junction.mkdir()
            output = junction / "record.json"

            def simulated_is_junction(path: Path) -> bool:
                return path == junction

            with (
                patch.object(media_state, "MEDIA_VAULT", root),
                patch.object(media_state, "_is_junction", side_effect=simulated_is_junction),
            ):
                with self.assertRaisesRegex(ValueError, "junctions are forbidden"):
                    media_state.write_once(output, {"ok": True})
            self.assertEqual([], list(junction.iterdir()))

    def test_bytes_write_rejects_a_junction_parent_before_creating_temp_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            junction = root / "junction"
            junction.mkdir()
            output = junction / "evidence.bin"

            with (
                patch.object(media_state, "MEDIA_VAULT", root),
                patch.object(media_state, "_is_junction", side_effect=lambda path: path == junction),
            ):
                with self.assertRaisesRegex(ValueError, "junctions are forbidden"):
                    media_state.write_bytes_once(output, b"evidence")
            self.assertEqual([], list(junction.iterdir()))

    @unittest.skipUnless(
        os.name == "nt" and hasattr(Path, "is_junction"),
        "Windows junction required",
    )
    def test_real_windows_junction_parent_is_rejected_before_target_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            target = base / "outside"
            junction = root / "junction"
            root.mkdir()
            target.mkdir()
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(f"junction creation unavailable: {result.stderr.strip()}")
            try:
                self.assertTrue(junction.is_junction())
                output = junction / "record.json"
                with patch.object(media_state, "MEDIA_VAULT", root):
                    with self.assertRaisesRegex(ValueError, "junctions are forbidden"):
                        media_state.write_once(output, {"ok": True})
                    with self.assertRaisesRegex(ValueError, "junctions are forbidden"):
                        media_state.write_bytes_once(junction / "evidence.bin", b"evidence")
                self.assertFalse((target / "record.json").exists())
                self.assertEqual([], list(target.iterdir()))
            finally:
                if junction.is_junction():
                    junction.rmdir()

    def test_existing_hardlink_with_identical_bytes_is_an_idempotent_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            original = root / "original.bin"
            linked = root / "linked.bin"
            original.write_bytes(b"evidence")
            os.link(original, linked)

            with patch.object(media_state, "MEDIA_VAULT", root):
                self.assertFalse(media_state.write_bytes_once(linked, b"evidence"))
            self.assertEqual(original.stat().st_ino, linked.stat().st_ino)
            self.assertEqual(b"evidence", linked.read_bytes())

    def test_changed_failure_is_archived_and_identical_retry_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            directory = root / "artwork"
            directory.mkdir(parents=True)
            path = directory / "acquisition-failure.json"
            first = {
                "artwork_id": "artwork:test",
                "request_id": "media-request:test",
                "step": "acquisition",
                "error_code": "media_http_status",
                "message": "HTTP 503",
                "failed_at": "2026-07-15T00:00:00Z",
                "terminal_for_artwork": True,
            }
            repeated = {**first, "failed_at": "2026-07-15T01:00:00Z"}
            changed = {
                **repeated,
                "error_code": "media_timeout",
                "message": "timeout",
                "failed_at": "2026-07-15T02:00:00Z",
            }
            with patch.object(media_state, "MEDIA_VAULT", root):
                self.assertEqual(first, _persist_failure(path, first))
                self.assertEqual(first, _persist_failure(path, repeated))
                self.assertEqual(changed, _persist_failure(path, changed))
            self.assertEqual(changed, media_state.load_json(path))
            archives = list(directory.glob("acquisition-failure-*.json"))
            self.assertEqual(1, len(archives))
            self.assertEqual(first, media_state.load_json(archives[0]))


if __name__ == "__main__":
    unittest.main()
