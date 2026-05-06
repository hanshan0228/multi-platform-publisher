from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class XiaohongshuPublishTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory(prefix="xhs-publish-test-")
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_article(self, body: str) -> Path:
        article_path = self.tmp_path / "article.md"
        article_path.write_text(body, encoding="utf-8")
        return article_path

    def _touch_images(self, count: int) -> Path:
        images_dir = self.tmp_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, count + 1):
            (images_dir / f"{index:02d}.png").write_bytes(b"fake")
        return images_dir

    def test_prepare_payload_uses_frontmatter_title_and_selected_section(self):
        import publish_xiaohongshu

        article_path = self._write_article(
            textwrap.dedent(
                """\
                ---
                title: 呈坎旅游攻略
                ---

                # 正文

                这里是长文，不作为小红书正文。

                ## 小红书文案备选

                呈坎真的适合周末慢逛。
                徽派建筑很出片，建议穿浅色衣服。
                """
            )
        )
        self._touch_images(2)

        payload = publish_xiaohongshu.prepare_xiaohongshu_payload(article_path)

        self.assertEqual(payload["title"], "呈坎旅游攻略")
        self.assertIn("周末慢逛", payload["content"])
        self.assertEqual(len(payload["images"]), 2)

    def test_prepare_payload_accepts_directory_input(self):
        import publish_xiaohongshu

        post_dir = self.tmp_path / "post"
        post_dir.mkdir()
        (post_dir / "article.md").write_text(
            "# 标题\n\n适合直接发小红书的内容。",
            encoding="utf-8",
        )
        images_dir = post_dir / "images"
        images_dir.mkdir()
        (images_dir / "cover.jpg").write_bytes(b"fake")

        payload = publish_xiaohongshu.prepare_xiaohongshu_payload(post_dir)

        self.assertEqual(payload["title"], "标题")
        self.assertEqual(len(payload["images"]), 1)
        self.assertTrue(payload["images"][0].endswith("cover.jpg"))

    def test_collect_image_paths_filters_non_images(self):
        import publish_xiaohongshu

        images_dir = self._touch_images(1)
        (images_dir / "README.md").write_text("ignore", encoding="utf-8")

        paths = publish_xiaohongshu.collect_image_paths(images_dir)

        self.assertEqual(len(paths), 1)
        self.assertTrue(paths[0].endswith("01.png"))

    def test_build_publish_command_includes_tags(self):
        import publish_xiaohongshu

        command = publish_xiaohongshu.build_publish_command(
            Path("cli.py"),
            bridge_url="ws://localhost:9333",
            action="fill-publish",
            title_file=Path("title.txt"),
            content_file=Path("content.txt"),
            images=["a.png", "b.png"],
            tags=["旅行", "攻略"],
        )

        self.assertIn("fill-publish", command)
        self.assertIn("--tags", command)
        self.assertEqual(command[-2:], ["旅行", "攻略"])


if __name__ == "__main__":
    unittest.main()
