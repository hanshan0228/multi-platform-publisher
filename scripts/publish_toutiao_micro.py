#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from toutiao_micro import (
    DEFAULT_COOKIE_PATH,
    DEFAULT_MAX_IMAGES,
    get_cookie_file_status,
    prepare_micro_post_payload,
    publish_with_node,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish a Toutiao micro post from brief.md + images/"
    )
    parser.add_argument("--brief", required=True, help="Path to brief.md")
    parser.add_argument("--content", help="Override the short text from brief.md")
    parser.add_argument("--images-dir", help="Override the default images/ directory")
    parser.add_argument(
        "--cookie-path",
        default=str(DEFAULT_COOKIE_PATH),
        help="Path to Toutiao cookies.json",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=DEFAULT_MAX_IMAGES,
        help="Maximum image count to include. Default: 9",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate inputs and login state without publishing",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Show the browser while publishing for debugging",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    payload = prepare_micro_post_payload(
        brief_path=Path(args.brief),
        content_override=args.content,
        images_dir_override=args.images_dir,
        max_images=args.max_images,
        cookie_path=args.cookie_path,
    )
    cookie_status = get_cookie_file_status(args.cookie_path)
    result = publish_with_node(
        payload,
        dry_run=args.dry_run,
        show_browser=args.show_browser,
    )
    result["cookie_status"] = cookie_status
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
