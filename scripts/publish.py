#!/usr/bin/env python3
"""
Unified publishing entrypoint for multi-platform-publisher.

Supports:
- Markdown -> WeChat article draft
- HTML -> WeChat article draft
- brief.md -> WeChat newspic draft

For article drafts, publish mode can be:
- api
- browser
- auto (API first, browser fallback by config order)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from html_converter import convert_markdown_to_wechat_html, load_theme
from image_handler import process_article_images
from publish_wechat_router import publish_news_draft as publish_wechat_news_draft
from wechat_api import (
    ConfigError,
    get_access_token,
    get_config,
    get_publish_config,
    list_image_styles,
    publish_newspic,
    resolve_image_style,
    set_account,
)


_INLINE_PAIR_MARKERS = [
    (r"\*\*", r"\*\*"),
    (r"==", r"=="),
    (r"\+\+", r"\+\+"),
    (r"%%", r"%%"),
    (r"&&", r"&&"),
    (r"!!", r"!!"),
    (r"@@", r"@@"),
    (r"\^\^", r"\^\^"),
]


def _strip_inline_markers(text: str) -> str:
    for open_pat, close_pat in _INLINE_PAIR_MARKERS:
        text = re.sub(rf"{open_pat}([^\n]+?){close_pat}", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    text = re.sub(r"\*\*|==|\+\+|%%|&&|!!|@@|\^\^", "", text)
    return text.replace("`", "")


def _strip_front_matter(md_content: str) -> str:
    if md_content.lstrip().startswith("---"):
        match = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n", md_content, flags=re.DOTALL)
        if match:
            return md_content[match.end():]
    return md_content


def extract_title_from_markdown(md_content: str) -> str:
    match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
    if match:
        return _strip_inline_markers(match.group(1).strip())

    body = _strip_front_matter(md_content)
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith((">", "!", "-", "*", "+")):
            continue
        if set(line) <= {"-", "=", " "}:
            continue
        return _strip_inline_markers(line)[:50]
    return "Untitled Article"


def extract_digest_from_markdown(md_content: str) -> str:
    match = re.search(r"^>\s+(.+)$", md_content, re.MULTILINE)
    if match:
        return _strip_inline_markers(match.group(1).strip())[:120]

    text = _strip_front_matter(md_content)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = _strip_inline_markers(text)
    text = re.sub(r"[\[\]]", "", text)
    text = " ".join(text.split())
    return text[:120]


def remove_title_from_content(md_content: str) -> str:
    lines = md_content.splitlines()
    result = []
    title_removed = False
    for line in lines:
        if not title_removed and re.match(r"^#\s+", line.strip()):
            title_removed = True
            continue
        result.append(line)
    return "\n".join(result)


def _default_temp_dir() -> str:
    return tempfile.mkdtemp(prefix="wechat_images_")


def publish_from_markdown(
    md_path,
    title=None,
    author=None,
    digest=None,
    cover_path=None,
    source_url="",
    temp_dir=None,
    style_path=None,
    theme=None,
    sync_platforms=None,
    account_name: Optional[str] = None,
    ai_score_threshold: float = None,
    skip_ai_score: bool = False,
    debug: bool = False,
    publish_mode: Optional[str] = None,
):
    if account_name:
        set_account(account_name)
    if temp_dir is None:
        temp_dir = _default_temp_dir()

    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"Article file not found: {md_path}")

    md_content = md_path.read_text(encoding="utf-8")

    if not skip_ai_score:
        try:
            from ai_score import DEFAULT_THRESHOLD as _DEFAULT_THRESHOLD
            from ai_score import check_ai_score
        except ImportError:
            pass
        else:
            threshold = ai_score_threshold if ai_score_threshold is not None else _DEFAULT_THRESHOLD
            passed, report = check_ai_score(md_content, threshold)
            if not passed:
                raise SystemExit(
                    f"AI score check failed: total_score={report.get('total_score')} threshold={threshold}"
                )

    if not title:
        title = extract_title_from_markdown(md_content)
    if not digest:
        digest = extract_digest_from_markdown(md_content)

    try:
        get_access_token()
    except Exception as exc:
        print(f"API connectivity check failed: {exc}")
        print("Browser mode may still work if publish_mode is browser or auto.")

    content_md = remove_title_from_content(md_content)
    processed_md, _, first_img = process_article_images(content_md, temp_dir)

    styles, highlights, divider_text, list_style = load_theme(
        theme_name=theme,
        style_path=style_path,
    )
    html_content = convert_markdown_to_wechat_html(
        processed_md,
        styles,
        highlights,
        divider_text,
        list_style,
    )

    if debug:
        html_path = Path(temp_dir) / "article_output.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_content, encoding="utf-8")

    if cover_path and Path(cover_path).exists():
        final_cover = cover_path
    elif first_img:
        final_cover = first_img
    else:
        raise SystemExit("A cover image is required. Provide --cover or include an image in the article.")

    if author is None:
        try:
            cfg = get_config(account_name)
            author = cfg.get("author", "") or "Author"
        except ConfigError:
            author = "Author"

    result = publish_wechat_news_draft(
        mode=publish_mode,
        title=title,
        html_content=html_content,
        cover_image_path=str(final_cover),
        author=author,
        digest=digest,
        source_url=source_url,
        account_name=account_name,
    )

    if sync_platforms:
        try:
            from multi_publish import run as sync_run

            sync_result = sync_run(
                md_path=md_path,
                platforms=sync_platforms,
                title=title,
                cover_path=str(final_cover),
                strict=False,
            )
            result["sync"] = {
                "platforms": sync_platforms,
                "success": sync_result["success"],
                "returncode": sync_result["returncode"],
            }
        except Exception as exc:
            result["sync"] = {
                "platforms": sync_platforms,
                "success": False,
                "error": str(exc),
            }

    return result


def publish_from_brief(
    brief_path,
    account_name: Optional[str] = None,
    image_style: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    ai_score_threshold: float = None,
    skip_ai_score: bool = False,
):
    from newspic_build import parse_brief

    brief_path = Path(brief_path)
    if not brief_path.exists():
        raise FileNotFoundError(f"brief.md not found: {brief_path}")

    parsed = parse_brief(brief_path.read_text(encoding="utf-8"))
    fm = parsed["frontmatter"] or {}
    sections = parsed["sections"]

    final_account = account_name or fm.get("account")
    if final_account:
        set_account(final_account)

    final_title = title or fm.get("title", "") or ""
    style = resolve_image_style(
        cli_value=image_style,
        frontmatter_value=fm.get("image_style"),
        account_name=final_account,
        mode="newspic",
    )
    short_text = (sections.get("短文本") or sections.get("短描述") or "").strip()

    images_dir = brief_path.parent / "images"
    if not images_dir.exists():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")

    exts = (".png", ".jpg", ".jpeg", ".webp")
    image_paths = sorted(
        [p for p in images_dir.iterdir() if p.suffix.lower() in exts],
        key=lambda p: p.name,
    )
    if not image_paths:
        raise FileNotFoundError(f"No images found under: {images_dir}")
    if len(image_paths) > 20:
        image_paths = image_paths[:20]

    if not skip_ai_score and short_text:
        try:
            from ai_score import DEFAULT_THRESHOLD as _DEFAULT_THRESHOLD
            from ai_score import check_ai_score
        except ImportError:
            pass
        else:
            threshold = ai_score_threshold if ai_score_threshold is not None else _DEFAULT_THRESHOLD
            passed, report = check_ai_score(short_text, threshold, mode="newspic")
            if not passed:
                raise SystemExit(
                    f"AI score check failed for newspic: total_score={report.get('total_score')} threshold={threshold}"
                )

    if author is None:
        try:
            cfg = get_config(final_account)
            author = cfg.get("author", "") or ""
        except ConfigError:
            author = ""

    result = publish_newspic(
        title=final_title,
        content=short_text,
        image_paths=image_paths,
        author=author,
    )
    result["image_style"] = style["style_name"]
    result["type"] = "newspic"
    result["cards"] = len(image_paths)
    result["brief_path"] = str(brief_path)
    result["mode_requested"] = "api"
    result["mode_used"] = "api"
    return result


def publish_from_html(
    html_path,
    title,
    cover_path,
    author=None,
    digest="",
    source_url="",
    account_name: Optional[str] = None,
    publish_mode: Optional[str] = None,
):
    if account_name:
        set_account(account_name)

    html_content = Path(html_path).read_text(encoding="utf-8")

    if author is None:
        try:
            cfg = get_config(account_name)
            author = cfg.get("author", "") or "Author"
        except ConfigError:
            author = "Author"

    return publish_wechat_news_draft(
        mode=publish_mode,
        title=title,
        html_content=html_content,
        cover_image_path=cover_path,
        author=author,
        digest=digest,
        source_url=source_url,
        account_name=account_name,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish WeChat drafts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python publish.py --input article.md
  python publish.py --input article.md --publish-mode auto
  python publish.py --html article.html --cover cover.jpg --title "Title"
  python publish.py --brief brief.md --type newspic
        """,
    )
    parser.add_argument("--input", "-i", help="Markdown file path")
    parser.add_argument("--html", help="Pre-rendered HTML file path")
    parser.add_argument("--brief", help="brief.md path for newspic mode")
    parser.add_argument("--type", choices=["news", "newspic"], default=None, help="Publish type")
    parser.add_argument("--title", "-t", help="Article title")
    parser.add_argument("--cover", "-c", help="Cover image path")
    parser.add_argument("--author", "-a", default=None, help="Author name")
    parser.add_argument("--digest", "-d", help="Article digest")
    parser.add_argument("--source-url", default="", help="Source URL")
    parser.add_argument("--style", help="Custom style JSON path")
    parser.add_argument("--theme", help="Theme name")
    parser.add_argument("--image-style", help=f"Image style, available examples: {', '.join(list_image_styles()[:8])}")
    parser.add_argument("--temp-dir", default=None, help="Temporary file directory")
    parser.add_argument("--account", help="WeChat account name")
    parser.add_argument("--publish-mode", choices=["api", "browser", "auto"], default=None, help="Draft publish mode")
    parser.add_argument("--sync", help="Comma-separated sync platform list")
    parser.add_argument("--sync-from-config", action="store_true", help="Read sync_platforms from config")
    parser.add_argument("--ai-score-threshold", type=float, default=None, help="AI score threshold")
    parser.add_argument("--skip-ai-score", action="store_true", help="Skip AI score check")
    parser.add_argument("--debug", action="store_true", help="Keep generated HTML for debugging")
    return parser


def _resolve_config(args):
    config_sync_platforms = None
    needs_config = (
        args.author is None
        or args.theme is None
        or args.sync_from_config
        or args.publish_mode is None
    )
    if not needs_config:
        return config_sync_platforms

    try:
        config = get_config()
    except ConfigError as exc:
        if args.sync_from_config:
            print(f"[config error] {exc}", file=sys.stderr)
            print("--sync-from-config requires a valid multi-platform-publisher.yaml", file=sys.stderr)
            sys.exit(1)
        if args.author is None:
            args.author = "Author"
        if args.publish_mode is None:
            args.publish_mode = get_publish_config().get("default_mode", "auto")
        return config_sync_platforms

    if args.author is None:
        args.author = config.get("author", "") or "Author"
    if args.theme is None:
        args.theme = config.get("theme", "") or None
    if args.publish_mode is None:
        args.publish_mode = get_publish_config().get("default_mode", "auto")
    config_sync_platforms = config.get("sync_platforms") or None
    return config_sync_platforms


def _resolve_sync_platforms(args, config_sync_platforms):
    if args.sync:
        return [p.strip() for p in args.sync.split(",") if p.strip()]
    if args.sync_from_config and config_sync_platforms:
        if isinstance(config_sync_platforms, str):
            return [p.strip() for p in config_sync_platforms.split(",") if p.strip()]
        return [str(p).strip() for p in config_sync_platforms if str(p).strip()]
    return None


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.account:
        set_account(args.account)
    if args.publish_mode is None:
        args.publish_mode = get_publish_config().get("default_mode", "auto")

    config_sync_platforms = _resolve_config(args)
    sync_platforms = _resolve_sync_platforms(args, config_sync_platforms)

    if args.brief or args.type == "newspic":
        if not args.brief:
            parser.error("--type newspic requires --brief <brief.md>")
        if args.sync or args.sync_from_config:
            parser.error("newspic mode does not support multi-platform sync")
        result = publish_from_brief(
            brief_path=args.brief,
            account_name=args.account,
            image_style=args.image_style,
            title=args.title,
            author=args.author,
            ai_score_threshold=args.ai_score_threshold,
            skip_ai_score=args.skip_ai_score,
        )
    elif args.html:
        if not args.title or not args.cover:
            parser.error("--html mode requires --title and --cover")
        if args.sync or args.sync_from_config:
            parser.error("--html mode does not support multi-platform sync")
        result = publish_from_html(
            html_path=args.html,
            title=args.title,
            cover_path=args.cover,
            author=args.author,
            digest=args.digest or "",
            source_url=args.source_url,
            account_name=args.account,
            publish_mode=args.publish_mode,
        )
    elif args.input:
        result = publish_from_markdown(
            md_path=args.input,
            title=args.title,
            author=args.author,
            digest=args.digest,
            cover_path=args.cover,
            source_url=args.source_url,
            temp_dir=args.temp_dir,
            style_path=args.style,
            theme=args.theme,
            sync_platforms=sync_platforms,
            account_name=args.account,
            ai_score_threshold=args.ai_score_threshold,
            skip_ai_score=args.skip_ai_score,
            debug=args.debug,
            publish_mode=args.publish_mode,
        )
    else:
        parser.error("Please provide --input, --html, or --brief")

    print("\n" + json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
