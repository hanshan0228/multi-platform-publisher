#!/usr/bin/env python3

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import get_publish_config
from publish_wechat_api import publish_news_draft as publish_via_api
from publish_wechat_browser import publish_news_draft as publish_via_browser


def _resolve_mode(mode: Optional[str]) -> str:
    if mode:
        normalized = mode.strip().lower()
        if normalized in {"api", "browser", "auto"}:
            return normalized
    return get_publish_config()["default_mode"]


def _resolve_order(mode: str) -> List[str]:
    if mode == "api":
        return ["api"]
    if mode == "browser":
        return ["browser"]

    publish_cfg = get_publish_config()
    order = [
        item for item in publish_cfg.get("fallback_order", ["api", "browser"])
        if item in {"api", "browser"}
    ]
    return order or ["api", "browser"]


def publish_news_draft(
    *,
    mode: Optional[str] = None,
    title: str,
    html_content: str,
    cover_image_path: str,
    author: str = "",
    digest: str = "",
    source_url: str = "",
    account_name: Optional[str] = None,
) -> Dict[str, Any]:
    requested_mode = _resolve_mode(mode)
    errors: Dict[str, str] = {}

    payload = {
        "title": title,
        "html_content": html_content,
        "cover_image_path": cover_image_path,
        "author": author,
        "digest": digest,
        "source_url": source_url,
        "account_name": account_name,
    }

    for candidate in _resolve_order(requested_mode):
        try:
            result = (
                publish_via_api(**payload)
                if candidate == "api"
                else publish_via_browser(**payload)
            )
            result["mode_requested"] = requested_mode
            result["mode_used"] = candidate
            if "api" in errors:
                result["api_error"] = errors["api"]
            if "browser" in errors:
                result["browser_error"] = errors["browser"]
            return result
        except Exception as exc:
            errors[candidate] = str(exc)
            if requested_mode != "auto":
                raise

    parts = [f"{name}: {message}" for name, message in errors.items()]
    raise RuntimeError("WeChat draft publish failed for all modes. " + " | ".join(parts))
