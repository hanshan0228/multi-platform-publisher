from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


MIN_CONFIG_YAML = textwrap.dedent(
    """\
    wechat:
      default: main
      accounts:
        main:
          name: "Test Main"
          app_id: "wx_fake_main_app_id_0001"
          app_secret: "fake_main_secret"
          author: "Main Author"
          theme: "refined-blue"
          voice: "test-voice-main"

        tech:
          name: "Test Tech"
          app_id: "wx_fake_tech_app_id_0002"
          app_secret: "fake_tech_secret"
          author: "Tech Author"
          theme: "minimal-mono"
          voice: "test-voice-tech"

    toutiao:
      cookie_path: "C:/tmp/toutiao/cookies.json"
      data_dir: "C:/tmp/toutiao"
    """
)


@pytest.fixture
def tmp_config_yaml(tmp_path, monkeypatch):
    import yaml
    import config

    yaml_path = tmp_path / "multi-platform-publisher.yaml"
    yaml_path.write_text(MIN_CONFIG_YAML, encoding="utf-8")

    config.set_account(None)
    monkeypatch.setattr(config, "_config_path", lambda: yaml_path)
    data = yaml.safe_load(MIN_CONFIG_YAML)
    yield data
    config.set_account(None)


@pytest.fixture
def write_config_yaml(tmp_path, monkeypatch):
    import config

    config.set_account(None)

    def _write(yaml_text: str) -> Path:
        path = tmp_path / "multi-platform-publisher.yaml"
        path.write_text(yaml_text, encoding="utf-8")
        config.set_account(None)
        monkeypatch.setattr(config, "_config_path", lambda: path)
        return path

    yield _write
    config.set_account(None)


@pytest.fixture
def no_network(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("Accidental network call in a unit test.")

    try:
        import requests

        monkeypatch.setattr(requests, "get", _boom)
        monkeypatch.setattr(requests, "post", _boom)
        monkeypatch.setattr(requests, "request", _boom)
    except ImportError:
        pass

    yield
