#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).parent
SCRIPTS_DIR = ROOT / "scripts"

TARGETS = {
    "wechat": ROOT / "publish_wechat.py",
    "toutiao": ROOT / "publish_toutiao.py",
    "xiaohongshu": ROOT / "publish_xiaohongshu.py",
}


def _print_help() -> None:
    print(
        "Usage:\n"
        "  python publish.py wechat [wechat publish args]\n"
        "  python publish.py toutiao [toutiao publish args]\n"
        "  python publish.py xiaohongshu [xiaohongshu publish args]\n\n"
        "Examples:\n"
        "  python publish.py wechat --input article.md --cover cover.jpg --account main\n"
        "  python publish.py toutiao --brief examples/brief-demo/brief.md\n"
        "  python publish.py xiaohongshu publish --input ../xhs-posts/ai-tools-guide --dry-run\n"
    )


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        _print_help()
        return 0

    target_name = sys.argv[1].lower()
    target = TARGETS.get(target_name)
    if target is None:
        print(f"Unknown platform: {sys.argv[1]}\n")
        _print_help()
        return 1

    sys.path.insert(0, str(SCRIPTS_DIR))
    sys.argv = [str(target)] + sys.argv[2:]
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
