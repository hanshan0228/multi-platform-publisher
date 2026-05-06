from __future__ import annotations

import pytest


def test_route_api_mode_uses_api(monkeypatch):
    import publish_wechat_router as router

    called = {"api": 0, "browser": 0}

    def fake_api(**kwargs):
        called["api"] += 1
        return {"status": "success", "media_id": "api-1"}

    def fake_browser(**kwargs):
        called["browser"] += 1
        return {"status": "success", "draft_saved": True}

    monkeypatch.setattr(router, "publish_via_api", fake_api)
    monkeypatch.setattr(router, "publish_via_browser", fake_browser)

    result = router.publish_news_draft(mode="api", title="t", html_content="<p>x</p>", cover_image_path="cover.png")

    assert result["mode_requested"] == "api"
    assert result["mode_used"] == "api"
    assert called == {"api": 1, "browser": 0}


def test_route_browser_mode_uses_browser(monkeypatch):
    import publish_wechat_router as router

    called = {"api": 0, "browser": 0}

    def fake_api(**kwargs):
        called["api"] += 1
        return {"status": "success", "media_id": "api-1"}

    def fake_browser(**kwargs):
        called["browser"] += 1
        return {"status": "success", "draft_saved": True}

    monkeypatch.setattr(router, "publish_via_api", fake_api)
    monkeypatch.setattr(router, "publish_via_browser", fake_browser)

    result = router.publish_news_draft(mode="browser", title="t", html_content="<p>x</p>", cover_image_path="cover.png")

    assert result["mode_requested"] == "browser"
    assert result["mode_used"] == "browser"
    assert called == {"api": 0, "browser": 1}


def test_route_auto_mode_falls_back_to_browser(monkeypatch):
    import publish_wechat_router as router

    called = {"api": 0, "browser": 0}

    def fake_api(**kwargs):
        called["api"] += 1
        raise RuntimeError("api failed")

    def fake_browser(**kwargs):
        called["browser"] += 1
        return {"status": "success", "draft_saved": True}

    monkeypatch.setattr(router, "publish_via_api", fake_api)
    monkeypatch.setattr(router, "publish_via_browser", fake_browser)

    result = router.publish_news_draft(mode="auto", title="t", html_content="<p>x</p>", cover_image_path="cover.png")

    assert result["mode_requested"] == "auto"
    assert result["mode_used"] == "browser"
    assert "api failed" in result["api_error"]
    assert called == {"api": 1, "browser": 1}


def test_route_auto_mode_raises_when_all_publishers_fail(monkeypatch):
    import publish_wechat_router as router

    monkeypatch.setattr(router, "publish_via_api", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("api failed")))
    monkeypatch.setattr(router, "publish_via_browser", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("browser failed")))

    with pytest.raises(RuntimeError) as exc:
        router.publish_news_draft(mode="auto", title="t", html_content="<p>x</p>", cover_image_path="cover.png")

    message = str(exc.value)
    assert "api failed" in message
    assert "browser failed" in message
