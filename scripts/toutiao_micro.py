#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import get_toutiao_config
from newspic_build import parse_brief


DEFAULT_MAX_IMAGES = 9
DEFAULT_COOKIE_PATH = Path(get_toutiao_config()["cookie_path"])


def _normalize_text(value: Optional[str]) -> str:
    return str(value or "").strip()


def _resolve_short_text(
    sections: Dict[str, str], content_override: Optional[str] = None
) -> str:
    if _normalize_text(content_override):
        return _normalize_text(content_override)
    for key in ("短文本", "短描述"):
        if _normalize_text(sections.get(key)):
            return _normalize_text(sections.get(key))
    raise ValueError("brief.md does not contain a usable short text section")


def _resolve_images(images_dir: Path, max_images: int) -> List[str]:
    if not images_dir.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    image_paths = sorted(
        [path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in exts],
        key=lambda path: path.name,
    )
    return [str(path.resolve()) for path in image_paths[:max_images]]


def prepare_micro_post_payload(
    brief_path: Path | str,
    *,
    content_override: Optional[str] = None,
    images_dir_override: Optional[Path | str] = None,
    max_images: int = DEFAULT_MAX_IMAGES,
    cookie_path: Path | str = DEFAULT_COOKIE_PATH,
) -> Dict[str, Any]:
    brief = Path(brief_path)
    if not brief.exists():
        raise FileNotFoundError(f"brief.md not found: {brief}")

    parsed = parse_brief(brief.read_text(encoding="utf-8"))
    frontmatter = parsed["frontmatter"] or {}
    sections = parsed["sections"] or {}

    images_dir = Path(images_dir_override) if images_dir_override else brief.parent / "images"
    content = _resolve_short_text(sections, content_override=content_override)
    images = _resolve_images(images_dir, max_images=max_images)

    return {
        "brief_path": str(brief.resolve()),
        "title": _normalize_text(frontmatter.get("title")),
        "topic": _normalize_text(frontmatter.get("topic")),
        "content": content,
        "images": images,
        "images_dir": str(images_dir.resolve()),
        "max_images": max_images,
        "cookie_path": str(Path(cookie_path).resolve()),
    }


def get_cookie_file_status(cookie_path: Path | str = DEFAULT_COOKIE_PATH) -> Dict[str, Any]:
    path = Path(cookie_path)
    status: Dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "cookie_count": 0,
    }
    if not path.exists():
        return status

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cookies = data.get("cookies") if isinstance(data, dict) else None
        if isinstance(cookies, list):
            status["cookie_count"] = len(cookies)
    except Exception:
        status["cookie_count"] = 0
    return status


def _resolve_toutiao_mcp_dir() -> Path:
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm_cmd:
        fallback = Path("C:/Program Files/nodejs/npm.cmd")
        if fallback.exists():
            npm_cmd = str(fallback)
    if not npm_cmd:
        raise FileNotFoundError("Could not find npm or npm.cmd to resolve toutiao-mcp")

    result = subprocess.run(
        [npm_cmd, "root", "-g"],
        capture_output=True,
        text=True,
        check=True,
    )
    npm_root = Path(result.stdout.strip())
    module_dir = npm_root / "toutiao-mcp"
    if not module_dir.exists():
        raise FileNotFoundError(f"Global toutiao-mcp install not found: {module_dir}")
    return module_dir


def publish_with_node(
    payload: Dict[str, Any],
    *,
    dry_run: bool = False,
    show_browser: bool = False,
) -> Dict[str, Any]:
    script_path = Path(__file__).with_name("toutiao_micro_publish.cjs")
    if not script_path.exists():
        raise FileNotFoundError(f"Missing publish script: {script_path}")

    toutiao_mcp_dir = _resolve_toutiao_mcp_dir()
    with tempfile.TemporaryDirectory(prefix="toutiao-micro-") as tmp_dir:
        payload_path = Path(tmp_dir) / "payload.json"
        payload_path.write_text(
            json.dumps(
                {
                    **payload,
                    "dry_run": dry_run,
                    "headless": not show_browser,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        env = dict(os.environ)
        env["TOUTIAO_MCP_DIR"] = str(toutiao_mcp_dir)

        result = subprocess.run(
            ["node", str(script_path), str(payload_path)],
            capture_output=True,
            text=True,
            env=env,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            raise RuntimeError(stderr or stdout or "Toutiao micro post publish failed")
        if not stdout:
            raise RuntimeError("Publish script did not return a result")
        try:
            return json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Publish script returned invalid JSON: {stdout}") from exc
