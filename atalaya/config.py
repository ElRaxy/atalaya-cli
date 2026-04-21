"""Carga y persistencia de configuracion y perfil en disco."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w
from platformdirs import user_config_dir, user_data_dir

from atalaya.models import Profile
from atalaya.profile import default_profile

APP_NAME = "atalaya"


def get_config_dir() -> Path:
    path = Path(user_config_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    return get_config_dir() / "config.toml"


def get_profile_path() -> Path:
    return get_config_dir() / "profile.toml"


def get_db_path() -> Path:
    return get_data_dir() / "atalaya.db"


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config() -> dict[str, Any]:
    path = get_config_path()
    if not path.exists():
        return {}
    return _load_toml(path)


def load_profile() -> Profile:
    path = get_profile_path()
    if not path.exists():
        return default_profile()
    data = _load_toml(path)
    return Profile.model_validate(data)


def save_profile(profile: Profile) -> Path:
    path = get_profile_path()
    payload = profile.model_dump(mode="json", exclude_none=True)
    with path.open("wb") as fh:
        tomli_w.dump(payload, fh)
    return path


def save_config(config: dict[str, Any]) -> Path:
    path = get_config_path()
    with path.open("wb") as fh:
        tomli_w.dump(config, fh)
    return path


def load_api_key() -> str | None:
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        return env_key
    cfg = load_config()
    anthropic = cfg.get("anthropic")
    if isinstance(anthropic, dict):
        value = anthropic.get("api_key")
        if isinstance(value, str) and value:
            return value
    return None
