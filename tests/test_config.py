from __future__ import annotations

import textwrap

import pytest


def test_get_config_default_account(tmp_config_yaml):
    import config

    cfg = config.get_config()
    assert cfg["account_key"] == "main"
    assert cfg["app_id"] == "wx_fake_main_app_id_0001"
    assert cfg["author"] == "Main Author"
    assert cfg["theme"] == "refined-blue"


def test_get_config_explicit_account(tmp_config_yaml):
    import config

    cfg = config.get_config("tech")
    assert cfg["account_key"] == "tech"
    assert cfg["app_id"] == "wx_fake_tech_app_id_0002"
    assert cfg["author"] == "Tech Author"
    assert cfg["theme"] == "minimal-mono"


def test_unified_config_reads_new_project_yaml(tmp_path, monkeypatch):
    yaml_path = tmp_path / "multi-platform-publisher.yaml"
    yaml_path.write_text(
        textwrap.dedent(
            """\
            wechat:
              default: main
              accounts:
                main:
                  name: "Unified Main"
                  app_id: "wx_unified"
                  app_secret: "unified_secret"
                  author: "Author"
                  theme: "refined-blue"
            image_generation:
              generator: "baoyu-image-gen"
            """
        ),
        encoding="utf-8",
    )

    import config

    config.set_account(None)
    monkeypatch.setattr(config, "_config_path", lambda: yaml_path)
    cfg = config.get_config()
    assert cfg["account_key"] == "main"
    assert cfg["app_id"] == "wx_unified"
    assert cfg["image_generator"] == "baoyu-image-gen"


def test_load_env_reads_image_and_integration_config(tmp_path, monkeypatch):
    for key in (
        "WECHATSYNC_MCP_TOKEN",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_IMAGE_MODEL",
        "GEMINI_PROXY_API_KEY",
        "GEMINI_PROXY_BASE_URL",
        "GEMINI_PROXY_IMAGE_MODEL",
        "WECHAT_PUBLISHER_IMAGE_GENERATOR",
    ):
        monkeypatch.delenv(key, raising=False)

    yaml_path = tmp_path / "multi-platform-publisher.yaml"
    yaml_path.write_text(
        textwrap.dedent(
            """\
            wechat:
              default: main
              accounts:
                main:
                  name: "Main"
                  app_id: "wx_main"
                  app_secret: "secret"
                  author: "Author"
            image_generation:
              generator: "baoyu-image-gen"
              openai:
                api_key: "sk_openai"
                base_url: "https://api.example/v1"
                image_model: "gpt-image-1"
              gemini_proxy:
                api_key: "cr_proxy"
                base_url: "https://proxy.example"
                image_model: "gemini-3-pro-image-preview"
            integrations:
              wechatsync_mcp_token: "sync_token"
            """
        ),
        encoding="utf-8",
    )

    import config

    monkeypatch.setattr(config, "_config_path", lambda: yaml_path)
    config.load_env()
    assert config.os.environ["WECHAT_PUBLISHER_IMAGE_GENERATOR"] == "baoyu-image-gen"
    assert config.os.environ["OPENAI_API_KEY"] == "sk_openai"
    assert config.os.environ["GEMINI_PROXY_BASE_URL"] == "https://proxy.example"
    assert config.os.environ["WECHATSYNC_MCP_TOKEN"] == "sync_token"


def test_set_account_affects_get_config(tmp_config_yaml):
    import config

    config.set_account("tech")
    try:
        cfg = config.get_config()
        assert cfg["account_key"] == "tech"
    finally:
        config.set_account(None)


def test_get_config_raises_on_missing_account(tmp_config_yaml):
    import config
    from config import ConfigError

    with pytest.raises(ConfigError) as exc:
        config.get_config("does_not_exist")

    assert "does_not_exist" in str(exc.value)


def test_get_config_raises_on_missing_yaml(tmp_path, monkeypatch):
    import config
    from config import ConfigError

    config.set_account(None)
    monkeypatch.setattr(config, "_config_path", lambda: tmp_path / "missing.yaml")

    with pytest.raises(ConfigError) as exc:
        config.get_config()

    assert "multi-platform-publisher.yaml" in str(exc.value)


def test_get_config_raises_on_missing_fields(write_config_yaml):
    write_config_yaml(
        textwrap.dedent(
            """\
            wechat:
              default: broken
              accounts:
                broken:
                  name: "Broken"
                  app_id: ""
                  app_secret: ""
            """
        )
    )

    import config
    from config import ConfigError

    with pytest.raises(ConfigError) as exc:
        config.get_config()
    assert "app_id" in str(exc.value) or "app_secret" in str(exc.value)


def test_list_accounts_shape_consistent(tmp_config_yaml):
    import config

    rows = config.list_accounts()
    assert len(rows) >= 2
    expected_keys = {"key", "name", "app_id", "author", "is_default"}
    for row in rows:
        assert set(row.keys()) == expected_keys


def test_sync_platforms_parsed_from_list(write_config_yaml):
    write_config_yaml(
        textwrap.dedent(
            """\
            wechat:
              default: main
              accounts:
                main:
                  name: "Main"
                  app_id: "wx_abc"
                  app_secret: "sec"
                  author: "x"
                  sync_platforms: [zhihu, juejin, csdn]
            """
        )
    )

    import config

    cfg = config.get_config()
    assert cfg["sync_platforms"] == ["zhihu", "juejin", "csdn"]


def test_sync_platforms_parsed_from_string(write_config_yaml):
    write_config_yaml(
        textwrap.dedent(
            """\
            wechat:
              default: main
              accounts:
                main:
                  name: "Main"
                  app_id: "wx_abc"
                  app_secret: "sec"
                  author: "x"
                  sync_platforms: "zhihu, juejin, csdn"
            """
        )
    )

    import config

    cfg = config.get_config()
    assert cfg["sync_platforms"] == ["zhihu", "juejin", "csdn"]


def test_sync_platforms_none_when_missing(write_config_yaml):
    write_config_yaml(
        textwrap.dedent(
            """\
            wechat:
              default: main
              accounts:
                main:
                  name: "Main"
                  app_id: "wx_abc"
                  app_secret: "sec"
                  author: "x"
            """
        )
    )

    import config

    cfg = config.get_config()
    assert cfg["sync_platforms"] is None


def test_get_toutiao_config_reads_nested_section(write_config_yaml):
    write_config_yaml(
        textwrap.dedent(
            """\
            wechat:
              default: main
              accounts:
                main:
                  name: "Main"
                  app_id: "wx_abc"
                  app_secret: "sec"
            toutiao:
              cookie_path: "D:/cookies.json"
              data_dir: "D:/toutiao"
            """
        )
    )

    import config

    toutiao_cfg = config.get_toutiao_config()
    assert toutiao_cfg["cookie_path"].endswith("cookies.json")
    assert toutiao_cfg["data_dir"].endswith("toutiao")
