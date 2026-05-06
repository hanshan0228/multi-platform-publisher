#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError as exc:
    raise ImportError("Missing dependency pyyaml. Run: pip install pyyaml") from exc

from config import get_xiaohongshu_config

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
DEFAULT_ARTICLE_NAME = "article.md"

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _split_frontmatter(raw_text: str) -> tuple[Dict[str, Any], str]:
    if not raw_text.startswith("---"):
        return {}, raw_text

    lines = raw_text.splitlines()
    if len(lines) < 3:
        return {}, raw_text

    try:
        end_index = lines[1:].index("---") + 1
    except ValueError:
        return {}, raw_text

    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).lstrip()
    data = yaml.safe_load(frontmatter_text) or {}
    return (data if isinstance(data, dict) else {}), body


def _extract_title(body: str, frontmatter: Dict[str, Any]) -> str:
    for key in ("xhs_title", "title", "topic"):
        value = str(frontmatter.get(key, "") or "").strip()
        if value:
            return value

    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()

    raise ValueError("Unable to determine Xiaohongshu title from markdown input")


def _strip_markdown_heading(line: str) -> str:
    return line.lstrip("#").strip()


def _extract_content(body: str) -> str:
    lines = body.splitlines()
    selected: List[str] = []
    capture = False

    for raw_line in lines:
        line = raw_line.rstrip()
        heading = _strip_markdown_heading(line)
        if heading in {"小红书文案备选", "正文", "短文案", "内容"}:
            capture = True
            continue
        if capture and line.startswith("#"):
            break
        if capture:
            selected.append(line)

    content = "\n".join(selected).strip()
    if content:
        return content

    filtered = []
    skip_titles = {"封面标题", "适合人群", "核心观点", "可拆卡要点"}
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            filtered.append("")
            continue
        if line.startswith("#"):
            heading = _strip_markdown_heading(line)
            if heading in skip_titles:
                continue
        filtered.append(line)

    content = "\n".join(filtered).strip()
    if not content:
        raise ValueError("Unable to determine Xiaohongshu content from markdown input")
    return content


def _resolve_input_paths(input_path: Path, images_dir: Optional[str]) -> tuple[Path, Path]:
    if input_path.is_dir():
        article_path = input_path / DEFAULT_ARTICLE_NAME
        default_images_dir = input_path / "images"
    else:
        article_path = input_path
        default_images_dir = input_path.parent / "images"

    if not article_path.exists():
        raise FileNotFoundError(f"Article file not found: {article_path}")

    image_dir_path = Path(images_dir).expanduser() if images_dir else default_images_dir
    return article_path, image_dir_path


def collect_image_paths(image_dir: Path) -> List[str]:
    if not image_dir.exists():
        return []
    paths = [
        str(path.resolve())
        for path in sorted(image_dir.iterdir())
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return paths


def prepare_xiaohongshu_payload(
    input_path: Path,
    images_dir: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    article_path, image_dir_path = _resolve_input_paths(input_path.expanduser(), images_dir)
    raw_text = _read_text(article_path)
    frontmatter, body = _split_frontmatter(raw_text)

    payload = {
        "title": _extract_title(body, frontmatter),
        "content": _extract_content(body),
        "images": collect_image_paths(image_dir_path),
        "article_path": str(article_path.resolve()),
        "images_dir": str(image_dir_path.resolve()),
        "tags": tags or [],
    }
    return payload


def build_publish_command(
    cli_script: Path,
    *,
    bridge_url: str,
    action: str,
    title_file: Path,
    content_file: Path,
    images: List[str],
    tags: List[str],
) -> List[str]:
    command = [
        "python",
        str(cli_script),
        "--bridge-url",
        bridge_url,
        action,
        "--title-file",
        str(title_file),
        "--content-file",
        str(content_file),
        "--images",
        *images,
    ]
    if tags:
        command.extend(["--tags", *tags])
    return command


def _run_subprocess(command: List[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def _is_bridge_extension_connected(bridge_url: str) -> bool:
    cli_script = (
        Path(__file__).resolve().parents[2]
        / ".tmp"
        / "xiaohongshu-skills-inspect"
        / "scripts"
        / "cli.py"
    )
    if not cli_script.exists():
        return False

    try:
        process = subprocess.run(
            ["python", str(cli_script), "--bridge-url", bridge_url, "check-login"],
            cwd=str(cli_script.parent.parent),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception:
        return False

    combined = f"{process.stdout}\n{process.stderr}"
    return "Extension 未连接" not in combined


def _default_edge_candidates() -> List[str]:
    return [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]


def _resolve_browser_executable(configured_path: str) -> Optional[Path]:
    candidates: List[str] = []
    if configured_path:
        candidates.append(configured_path)
    candidates.extend(_default_edge_candidates())

    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    return None


def ensure_browser_bridge_ready(config: Dict[str, Any]) -> Dict[str, Any]:
    bridge_url = config["bridge_url"]
    if _is_bridge_extension_connected(bridge_url):
        return {"started": False, "connected": True, "browser": "existing"}

    browser_path = _resolve_browser_executable(config.get("browser_executable", ""))
    if browser_path is None:
        return {
            "started": False,
            "connected": False,
            "error": "No Edge executable found for Xiaohongshu bridge startup",
        }

    profile_dir = (
        Path(config.get("browser_profile_dir") or "")
        if config.get("browser_profile_dir")
        else Path(__file__).resolve().parents[2] / ".tmp" / "xhs-edge-profile"
    )
    extension_path = (
        Path(config.get("extension_path") or "")
        if config.get("extension_path")
        else Path(config["skill_root"]) / "extension"
    )
    profile_dir.mkdir(parents=True, exist_ok=True)

    subprocess.Popen(
        [
            str(browser_path),
            f"--user-data-dir={profile_dir}",
            f"--load-extension={extension_path}",
            "--no-first-run",
            "--new-window",
            "https://www.xiaohongshu.com/",
        ]
    )

    deadline = time.time() + 25
    while time.time() < deadline:
        time.sleep(2)
        if _is_bridge_extension_connected(bridge_url):
            return {
                "started": True,
                "connected": True,
                "browser": str(browser_path),
                "profile_dir": str(profile_dir),
                "extension_path": str(extension_path),
            }

    return {
        "started": True,
        "connected": False,
        "browser": str(browser_path),
        "profile_dir": str(profile_dir),
        "extension_path": str(extension_path),
        "error": "Browser started but XHS Bridge extension did not connect in time",
    }


def _parse_json_output(stdout: str) -> Dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"raw_output": data}
    except json.JSONDecodeError:
        return {"raw_output": text}


def run_xiaohongshu_publish(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = get_xiaohongshu_config()
    skill_root = Path(args.skill_root or cfg["skill_root"]).expanduser()
    cli_script = skill_root / "scripts" / "cli.py"
    if not cli_script.exists():
        raise FileNotFoundError(f"Xiaohongshu CLI not found: {cli_script}")

    mode = (args.mode or cfg["default_mode"]).strip().lower()
    if mode not in {"fill", "publish"}:
        raise ValueError("mode must be 'fill' or 'publish'")
    action = "fill-publish" if mode == "fill" else "publish"

    browser_status = ensure_browser_bridge_ready(
        {
            **cfg,
            "skill_root": str(skill_root),
            "bridge_url": args.bridge_url or cfg["bridge_url"],
        }
    )

    merged_tags = list(cfg["default_tags"])
    for tag in args.tags or []:
        if tag not in merged_tags:
            merged_tags.append(tag)

    payload = prepare_xiaohongshu_payload(
        input_path=Path(args.input),
        images_dir=args.images_dir,
        tags=merged_tags,
    )
    if not payload["images"]:
        raise ValueError("No publishable images found. Put images under the images/ directory.")

    with tempfile.TemporaryDirectory(prefix="xhs-publish-") as temp_dir:
        temp_path = Path(temp_dir)
        title_file = temp_path / "title.txt"
        content_file = temp_path / "content.txt"
        title_file.write_text(payload["title"], encoding="utf-8")
        content_file.write_text(payload["content"], encoding="utf-8")

        command = build_publish_command(
            cli_script,
            bridge_url=args.bridge_url or cfg["bridge_url"],
            action=action,
            title_file=title_file,
            content_file=content_file,
            images=payload["images"],
            tags=payload["tags"],
        )

        result: Dict[str, Any] = {
            "success": True,
            "mode": mode,
            "action": action,
            "payload": payload,
            "skill_root": str(skill_root.resolve()),
            "cli_script": str(cli_script.resolve()),
            "command": command,
            "browser_status": browser_status,
        }

        if args.dry_run:
            result["status"] = "dry-run"
            return result

        publish_result = _run_subprocess(command, cwd=skill_root)
        result["publish_exit_code"] = publish_result.returncode
        result["publish_stdout"] = publish_result.stdout.strip()
        result["publish_stderr"] = publish_result.stderr.strip()
        result["publish_response"] = _parse_json_output(publish_result.stdout)
        result["success"] = publish_result.returncode == 0

        if result["success"] and args.save_draft and mode == "fill":
            draft_command = [
                "python",
                str(cli_script),
                "--bridge-url",
                args.bridge_url or cfg["bridge_url"],
                "save-draft",
            ]
            draft_result = _run_subprocess(draft_command, cwd=skill_root)
            result["save_draft_command"] = draft_command
            result["save_draft_exit_code"] = draft_result.returncode
            result["save_draft_stdout"] = draft_result.stdout.strip()
            result["save_draft_stderr"] = draft_result.stderr.strip()
            result["save_draft_response"] = _parse_json_output(draft_result.stdout)
            result["success"] = draft_result.returncode == 0

        return result


def run_simple_cli_command(
    action: str,
    skill_root: Path,
    bridge_url: str,
    extra_args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    cli_script = skill_root / "scripts" / "cli.py"
    if not cli_script.exists():
        raise FileNotFoundError(f"Xiaohongshu CLI not found: {cli_script}")

    browser_status = ensure_browser_bridge_ready(
        {
            **get_xiaohongshu_config(),
            "skill_root": str(skill_root),
            "bridge_url": bridge_url,
        }
    )

    command = ["python", str(cli_script), "--bridge-url", bridge_url, action]
    if extra_args:
        command.extend(extra_args)
    process = _run_subprocess(command, cwd=skill_root)
    return {
        "success": process.returncode == 0,
        "action": action,
        "command": command,
        "browser_status": browser_status,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "response": _parse_json_output(process.stdout),
    }


def build_parser() -> argparse.ArgumentParser:
    cfg = get_xiaohongshu_config()
    parser = argparse.ArgumentParser(
        description="Publish Xiaohongshu image posts through xiaohongshu-skills"
    )
    subparsers = parser.add_subparsers(dest="command")

    publish_parser = subparsers.add_parser(
        "publish",
        help="Prepare and publish/fill a Xiaohongshu post from article.md + images/",
    )
    publish_parser.add_argument(
        "--input",
        required=True,
        help="Path to article.md or a content directory containing article.md and images/",
    )
    publish_parser.add_argument("--images-dir", help="Override the default images/ directory")
    publish_parser.add_argument(
        "--mode",
        default=cfg["default_mode"],
        help="fill or publish. Default comes from config and should usually stay fill.",
    )
    publish_parser.add_argument("--tags", nargs="*", default=[], help="Extra Xiaohongshu tags")
    publish_parser.add_argument(
        "--skill-root",
        help="Path to the xiaohongshu-skills repository",
    )
    publish_parser.add_argument(
        "--bridge-url",
        default=cfg["bridge_url"],
        help="Bridge server WebSocket URL",
    )
    publish_parser.add_argument(
        "--save-draft",
        action="store_true",
        help="After fill mode completes, try saving the current form into drafts",
    )
    publish_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only prepare payload and show the generated command without invoking the CLI",
    )

    for name, help_text in (
        ("check-login", "Check current Xiaohongshu login state"),
        ("login", "Trigger Xiaohongshu login flow"),
        ("wait-login", "Wait for QR-code login to complete"),
        ("save-draft", "Save the currently filled Xiaohongshu form as a draft"),
        ("click-publish", "Click the final publish button on an already filled form"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--skill-root", help="Path to the xiaohongshu-skills repository")
        sub.add_argument(
            "--bridge-url",
            default=cfg["bridge_url"],
            help="Bridge server WebSocket URL",
        )
        if name == "wait-login":
            sub.add_argument(
                "--timeout",
                default="120",
                help="Seconds to wait for QR-code login completion",
            )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    cfg = get_xiaohongshu_config()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "publish":
        result = run_xiaohongshu_publish(args)
    else:
        skill_root = Path(args.skill_root or cfg["skill_root"]).expanduser()
        extra_args: List[str] = []
        if args.command == "wait-login":
            extra_args = ["--timeout", str(args.timeout)]
        result = run_simple_cli_command(args.command, skill_root, args.bridge_url, extra_args)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success", False) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
