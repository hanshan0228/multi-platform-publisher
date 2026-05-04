from __future__ import annotations

import json
import sys
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _write_brief(tmp_path: Path, body: str) -> Path:
    brief_path = tmp_path / "brief.md"
    brief_path.write_text(body, encoding="utf-8")
    return brief_path


def _touch_images(images_dir: Path, count: int) -> None:
    images_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        (images_dir / f"{index:02d}.png").write_bytes(b"fake")


class ToutiaoMicroTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory(prefix="toutiao-micro-test-")
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_prepare_payload_reads_short_text_and_images(self):
        import toutiao_micro

        brief_path = _write_brief(
            self.tmp_path,
            textwrap.dedent(
                """\
                ---
                topic: "Chengkan travel guide"
                title: "Chengkan travel guide"
                ---

                # 要点

                1. First point
                2. Second point

                # 短文本
                Chengkan works well as a half-day walking destination.
                """
            ),
        )
        _touch_images(self.tmp_path / "images", 3)

        payload = toutiao_micro.prepare_micro_post_payload(brief_path)

        self.assertEqual(payload["title"], "Chengkan travel guide")
        self.assertIn("half-day", payload["content"])
        self.assertEqual(len(payload["images"]), 3)
        self.assertTrue(payload["images"][0].endswith("01.png"))

    def test_prepare_payload_truncates_images_to_max(self):
        import toutiao_micro

        brief_path = _write_brief(
            self.tmp_path,
            textwrap.dedent(
                """\
                ---
                topic: "Test"
                ---

                # 要点

                1. First point

                # 短文本
                A short text suitable for a micro post.
                """
            ),
        )
        _touch_images(self.tmp_path / "images", 12)

        payload = toutiao_micro.prepare_micro_post_payload(brief_path, max_images=9)

        self.assertEqual(len(payload["images"]), 9)
        self.assertTrue(payload["images"][-1].endswith("09.png"))

    def test_prepare_payload_allows_text_only(self):
        import toutiao_micro

        brief_path = _write_brief(
            self.tmp_path,
            textwrap.dedent(
                """\
                ---
                topic: "Text only"
                ---

                # 要点

                1. First point

                # 短文本
                Text-only content should still be publishable.
                """
            ),
        )

        payload = toutiao_micro.prepare_micro_post_payload(brief_path)

        self.assertEqual(payload["images"], [])
        self.assertEqual(payload["content"], "Text-only content should still be publishable.")

    def test_prepare_payload_prefers_content_override(self):
        import toutiao_micro

        brief_path = _write_brief(
            self.tmp_path,
            textwrap.dedent(
                """\
                ---
                topic: "Override"
                ---

                # 要点

                1. First point

                # 短文本
                Original copy.
                """
            ),
        )

        payload = toutiao_micro.prepare_micro_post_payload(
            brief_path,
            content_override="Manual override copy",
        )

        self.assertEqual(payload["content"], "Manual override copy")

    def test_prepare_payload_raises_when_content_missing(self):
        import toutiao_micro

        brief_path = _write_brief(
            self.tmp_path,
            textwrap.dedent(
                """\
                ---
                topic: "Missing text"
                ---

                # 要点

                1. First point
                """
            ),
        )
        _touch_images(self.tmp_path / "images", 2)

        with self.assertRaisesRegex(ValueError, "short text"):
            toutiao_micro.prepare_micro_post_payload(brief_path)

    def test_cookie_status_detects_existing_cookie_file(self):
        import toutiao_micro

        cookie_path = self.tmp_path / "cookies.json"
        cookie_path.write_text(
            json.dumps({"cookies": [{"name": "sid", "value": "1"}]}),
            encoding="utf-8",
        )

        status = toutiao_micro.get_cookie_file_status(cookie_path)

        self.assertTrue(status["exists"])
        self.assertEqual(status["cookie_count"], 1)
        self.assertEqual(status["path"], str(cookie_path))


if __name__ == "__main__":
    unittest.main()
