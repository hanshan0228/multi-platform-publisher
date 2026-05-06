#!/usr/bin/env python3

from __future__ import annotations

from typing import Any, Dict, Optional

from wechat_api import publish_article


def publish_news_draft(
    *,
    title: str,
    html_content: str,
    cover_image_path: str,
    author: str = "",
    digest: str = "",
    source_url: str = "",
    account_name: Optional[str] = None,
) -> Dict[str, Any]:
    result = publish_article(
        title=title,
        html_content=html_content,
        cover_image_path=cover_image_path,
        author=author,
        digest=digest,
        source_url=source_url,
        account_name=account_name,
    )
    result["draft_saved"] = True
    result["mode_used"] = "api"
    return result
