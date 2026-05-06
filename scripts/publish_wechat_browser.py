#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from config import get_config, get_wechat_browser_config, set_account


WECHAT_HOME_URL = "https://mp.weixin.qq.com/"


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc
    return sync_playwright


def _looks_like_logged_in(page) -> bool:
    try:
        current_url = page.url or ""
    except Exception:
        current_url = ""

    try:
        body_text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        body_text = ""

    login_markers = ("扫码登录", "请使用微信扫码登录")
    expired_markers = ("登录超时", "请重新登录")
    logged_in_markers = ("首页", "新的创作", "草稿", "发表记录", "内容与互动")

    if "cgi-bin/home" in current_url or "cgi-bin/appmsg" in current_url:
        return True
    if any(marker in body_text for marker in logged_in_markers):
        return True
    if any(marker in body_text for marker in expired_markers):
        return False
    if any(marker in body_text for marker in login_markers):
        return False
    return False


def _ensure_home_page_for_login(page) -> None:
    current_url = page.url or ""
    if "cgi-bin/home" in current_url:
        return
    page.goto(WECHAT_HOME_URL, wait_until="domcontentloaded")


def _build_editor_url(home_url: str, editor_url: str) -> str:
    token = parse_qs(urlparse(home_url).query).get("token", [""])[0]
    if not token:
        return editor_url

    parsed = urlparse(editor_url)
    query = parse_qs(parsed.query)
    query["token"] = [token]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _wait_for_login(page, timeout_seconds: int) -> None:
    deadline = time.time() + max(timeout_seconds, 1)
    _ensure_home_page_for_login(page)

    if _looks_like_logged_in(page):
        return

    while time.time() < deadline:
        try:
            body_text = page.locator("body").inner_text(timeout=2000)
        except Exception:
            body_text = ""
        if "登录超时" in body_text or "请重新登录" in body_text:
            _ensure_home_page_for_login(page)
        if _looks_like_logged_in(page):
            return
        try:
            page.wait_for_timeout(1500)
        except Exception:
            time.sleep(1.5)
    raise RuntimeError("WeChat browser login timed out. Please log in to mp.weixin.qq.com in the configured profile.")


def _set_input_value(page, selectors: list[str], value: str, label: str) -> bool:
    if not value:
        return False
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count() == 0:
                continue
            locator.wait_for(timeout=3000)
            locator.click()
            locator.fill(value)
            return True
        except Exception:
            continue
    raise RuntimeError(f"Unable to fill WeChat editor field: {label}")


def _upload_cover(page, cover_image_path: str) -> None:
    cover_file = str(Path(cover_image_path).resolve())
    selectors = [
        "input[type='file']",
        "input.accept[type='file']",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count() == 0:
                continue
            locator.set_input_files(cover_file, timeout=10000)
            return
        except Exception:
            continue
    raise RuntimeError("Unable to locate WeChat cover upload input.")


def _set_editor_content(page, html_content: str) -> None:
    script = """
    (html) => {
      const candidates = Array.from(document.querySelectorAll("iframe"));
      for (const frame of candidates) {
        try {
          const doc = frame.contentDocument;
          if (!doc || !doc.body) continue;
          if (doc.body.isContentEditable || doc.querySelector("[contenteditable='true']")) {
            doc.body.innerHTML = html;
            doc.body.dispatchEvent(new Event("input", { bubbles: true }));
            return true;
          }
        } catch (err) {}
      }
      const editable = document.querySelector("[contenteditable='true']");
      if (editable) {
        editable.innerHTML = html;
        editable.dispatchEvent(new Event("input", { bubbles: true }));
        return true;
      }
      return false;
    }
    """
    success = page.evaluate(script, html_content)
    if not success:
        raise RuntimeError("Unable to locate WeChat rich text editor.")


def _click_save_draft(page) -> None:
    buttons = [
        "button:has-text('保存为草稿')",
        "button:has-text('保存')",
        "a:has-text('保存为草稿')",
        "div[role='button']:has-text('保存为草稿')",
    ]
    for selector in buttons:
        locator = page.locator(selector).first
        try:
            if locator.count() == 0:
                continue
            locator.click(timeout=5000)
            return
        except Exception:
            continue
    raise RuntimeError("Unable to find the WeChat 'save draft' button.")


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
    if account_name:
        set_account(account_name)

    browser_cfg = get_wechat_browser_config()
    if not browser_cfg["enabled"]:
        raise RuntimeError("wechat browser publishing is disabled")

    config = get_config(account_name)
    final_author = author or config.get("author", "")
    profile_dir = Path(browser_cfg["profile_dir"]).expanduser()
    profile_dir.mkdir(parents=True, exist_ok=True)

    sync_playwright = _ensure_playwright()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as handle:
        handle.write(html_content)
        temp_html_path = Path(handle.name)

    launch_kwargs: Dict[str, Any] = {
        "user_data_dir": str(profile_dir),
        "headless": browser_cfg["headless"],
    }
    if browser_cfg["browser_path"]:
        launch_kwargs["executable_path"] = browser_cfg["browser_path"]

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(**launch_kwargs)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(browser_cfg["action_timeout"] * 1000)

                _wait_for_login(page, browser_cfg["login_timeout"])
                editor_url = _build_editor_url(page.url, browser_cfg["editor_url"])
                page.goto(editor_url, wait_until="domcontentloaded")

                _set_input_value(
                    page,
                    ["textarea[name='title']", "#title", "textarea[placeholder='请在这里输入标题']"],
                    title,
                    "title",
                )
                _set_input_value(
                    page,
                    ["input[name='author']", "#author", "input[placeholder='请输入作者']"],
                    final_author,
                    "author",
                )
                _set_input_value(
                    page,
                    ["textarea[name='digest']", "#js_description", "textarea[placeholder*='摘要']"],
                    digest,
                    "digest",
                )
                if source_url:
                    _set_input_value(
                        page,
                        ["input[name='source_url']", "input[placeholder*='原文链接']", "input[placeholder*='原文']"],
                        source_url,
                        "source_url",
                    )

                _set_editor_content(page, html_content)
                _upload_cover(page, cover_image_path)
                _click_save_draft(page)

                return {
                    "status": "success",
                    "draft_saved": True,
                    "mode_used": "browser",
                    "account": config.get("account_name", account_name or ""),
                    "profile_dir": str(profile_dir),
                    "temp_html_path": str(temp_html_path),
                }
            finally:
                context.close()
    finally:
        try:
            temp_html_path.unlink(missing_ok=True)
        except Exception:
            pass
