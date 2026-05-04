#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError as exc:
    raise ImportError(
        "Missing dependency pyyaml. Run: pip install pyyaml"
    ) from exc


class ConfigError(RuntimeError):
    """Raised when the unified project config is missing or invalid."""


CONFIG_CANDIDATES = (
    "multi-platform-publisher.yaml",
    "wechat-publisher.yaml",
)

DEFAULT_IMAGE_STYLE = "hand-drawn-blue"
DEFAULT_NEWSPIC_IMAGE_STYLE = "infographic-warm"

_active_account: Optional[str] = None


def set_account(account_name: Optional[str]) -> None:
    global _active_account
    _active_account = account_name


def get_account_name() -> Optional[str]:
    return _active_account


def _config_path() -> Path:
    repo_root = Path(__file__).parent.parent
    for name in CONFIG_CANDIDATES:
        candidate = repo_root / name
        if candidate.exists():
            return candidate
    return repo_root / CONFIG_CANDIDATES[0]


def _load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def _load_config_yaml(yaml_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = yaml_path or _config_path()
    if not path.exists():
        return None
    return _load_yaml(path)


def _set_env_if_present(key: str, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        os.environ.setdefault(key, text)


def load_env() -> None:
    cfg = _load_config_yaml()
    if not cfg:
        return

    integrations = cfg.get("integrations") or {}
    if isinstance(integrations, dict):
        _set_env_if_present("WECHATSYNC_MCP_TOKEN", integrations.get("wechatsync_mcp_token"))

    image = cfg.get("image_generation") or {}
    if isinstance(image, dict):
        _set_env_if_present("WECHAT_PUBLISHER_IMAGE_GENERATOR", image.get("generator"))

        provider_order = image.get("provider_order")
        if isinstance(provider_order, list):
            _set_env_if_present(
                "GEMINI_PROVIDER_ORDER",
                ",".join(str(item).strip() for item in provider_order if str(item).strip()),
            )
        elif isinstance(provider_order, str):
            _set_env_if_present("GEMINI_PROVIDER_ORDER", provider_order)

        openai = image.get("openai") or {}
        if isinstance(openai, dict):
            _set_env_if_present("OPENAI_API_KEY", openai.get("api_key"))
            _set_env_if_present("OPENAI_BASE_URL", openai.get("base_url"))
            _set_env_if_present("OPENAI_IMAGE_MODEL", openai.get("image_model"))

        gemini_proxy = image.get("gemini_proxy") or {}
        if isinstance(gemini_proxy, dict):
            _set_env_if_present("GEMINI_PROXY_API_KEY", gemini_proxy.get("api_key"))
            _set_env_if_present("GEMINI_PROXY_BASE_URL", gemini_proxy.get("base_url"))
            _set_env_if_present("GEMINI_PROXY_IMAGE_MODEL", gemini_proxy.get("image_model"))

        gemini_official = image.get("gemini_official") or {}
        if isinstance(gemini_official, dict):
            _set_env_if_present("GEMINI_OFFICIAL_API_KEY", gemini_official.get("api_key"))
            _set_env_if_present("GEMINI_OFFICIAL_BASE_URL", gemini_official.get("base_url"))
            _set_env_if_present("GEMINI_OFFICIAL_IMAGE_MODEL", gemini_official.get("image_model"))


def _get_wechat_root(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if "wechat" in cfg and isinstance(cfg["wechat"], dict):
        return cfg["wechat"]
    return cfg


def list_accounts() -> List[Dict[str, Any]]:
    cfg = _load_config_yaml()
    if not cfg:
        return []

    wechat_cfg = _get_wechat_root(cfg)
    accounts = wechat_cfg.get("accounts") or {}
    default_name = wechat_cfg.get("default")
    if not isinstance(accounts, dict):
        return []

    rows: List[Dict[str, Any]] = []
    for key, acc in accounts.items():
        if not isinstance(acc, dict):
            continue
        app_id = str(acc.get("app_id", "") or "")
        rows.append(
            {
                "key": key,
                "name": acc.get("name", key),
                "app_id": (app_id[:8] + "...") if app_id else "",
                "author": acc.get("author", "") or "",
                "is_default": key == default_name,
            }
        )
    return rows


def get_global_image_generator() -> str:
    cfg = _load_config_yaml()
    if not cfg:
        return ""
    image_generation = cfg.get("image_generation") or {}
    if not isinstance(image_generation, dict):
        return ""
    return str(image_generation.get("generator", "") or "").strip()


def get_config(account_name: Optional[str] = None) -> Dict[str, Any]:
    account_name = account_name or _active_account

    cfg = _load_config_yaml()
    if not cfg:
        raise ConfigError(
            "Missing config file. Create multi-platform-publisher.yaml from the example."
        )

    wechat_cfg = _get_wechat_root(cfg)
    accounts = wechat_cfg.get("accounts") or {}
    if not isinstance(accounts, dict) or not accounts:
        raise ConfigError("WeChat accounts are missing from config.")

    if account_name is None:
        account_name = wechat_cfg.get("default")

    if account_name is None:
        available = ", ".join(accounts.keys())
        raise ConfigError(f"No default WeChat account set. Available accounts: {available}")

    if account_name not in accounts:
        available = ", ".join(accounts.keys())
        raise ConfigError(f"Unknown WeChat account '{account_name}'. Available: {available}")

    acc = accounts[account_name]
    if not isinstance(acc, dict):
        raise ConfigError(f"WeChat account '{account_name}' is invalid.")

    app_id = str(acc.get("app_id", "") or "").strip()
    app_secret = str(acc.get("app_secret", "") or "").strip()
    if not app_id or not app_secret:
        raise ConfigError(f"WeChat account '{account_name}' is missing app_id or app_secret")

    sync_platforms = acc.get("sync_platforms")
    if isinstance(sync_platforms, str):
        sync_platforms = [part.strip() for part in sync_platforms.split(",") if part.strip()]
    elif isinstance(sync_platforms, list):
        sync_platforms = [str(part).strip() for part in sync_platforms if str(part).strip()]
    else:
        sync_platforms = None

    image_generation = cfg.get("image_generation") or {}
    if not isinstance(image_generation, dict):
        image_generation = {}

    return {
        "app_id": app_id,
        "app_secret": app_secret,
        "author": acc.get("author", "") or "",
        "account_key": account_name,
        "account_name": acc.get("name", account_name),
        "theme": acc.get("theme", "") or "",
        "image_style": acc.get("image_style", "") or "",
        "newspic_image_style": acc.get("newspic_image_style", "") or "",
        "image_generator": acc.get("image_generator", "") or image_generation.get("generator", "") or "",
        "voice": acc.get("voice", "") or "",
        "sync_platforms": sync_platforms,
    }


def get_toutiao_config() -> Dict[str, Any]:
    cfg = _load_config_yaml() or {}
    toutiao_cfg = cfg.get("toutiao") or {}
    if not isinstance(toutiao_cfg, dict):
        toutiao_cfg = {}

    cookie_path = toutiao_cfg.get("cookie_path") or (
        Path.home() / ".codex" / "data" / "toutiao" / "cookies.json"
    )
    data_dir = toutiao_cfg.get("data_dir") or (Path.home() / ".codex" / "data" / "toutiao")

    return {
        "cookie_path": str(Path(cookie_path).expanduser()),
        "data_dir": str(Path(data_dir).expanduser()),
    }


def _image_styles_dir() -> Path:
    return Path(__file__).parent.parent / "assets" / "image-styles"


def list_image_styles() -> List[str]:
    image_dir = _image_styles_dir()
    if not image_dir.exists():
        return []
    return sorted(path.stem for path in image_dir.glob("*.json"))


def get_image_style(name: Optional[str] = None) -> Dict[str, Any]:
    style_name = name or DEFAULT_IMAGE_STYLE
    path = _image_styles_dir() / f"{style_name}.json"
    if not path.exists():
        available = ", ".join(list_image_styles()) or "(none)"
        raise ConfigError(f"Unknown image style '{style_name}'. Available: {available}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Image style JSON is invalid for '{style_name}': {exc}") from exc


def resolve_image_style(
    cli_value: Optional[str] = None,
    frontmatter_value: Optional[str] = None,
    account_name: Optional[str] = None,
    mode: str = "news",
) -> Dict[str, Any]:
    for candidate in (cli_value, frontmatter_value):
        if candidate:
            return get_image_style(candidate)

    try:
        cfg = get_config(account_name)
        if mode == "newspic":
            if cfg.get("newspic_image_style"):
                return get_image_style(cfg["newspic_image_style"])
        elif cfg.get("image_style"):
            return get_image_style(cfg["image_style"])
    except ConfigError:
        pass

    fallback = DEFAULT_NEWSPIC_IMAGE_STYLE if mode == "newspic" else DEFAULT_IMAGE_STYLE
    return get_image_style(fallback)
