"""Tests del backend ClaudeCodeClient (subprocess) y la factory make_client."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest

from atalaya.generators.claude_client import (
    DEFAULT_MODEL,
    ClaudeApiClient,
    ClaudeCodeClient,
    ConfigError,
    make_client,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _success_payload(result: str) -> str:
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": result,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 200,
                "cache_read_input_tokens": 0,
            },
        }
    )


def test_claude_code_client_happy_path(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return _FakeCompleted(_success_payload("Carta tailored OK"))

    monkeypatch.setattr(subprocess, "run", _fake_run)

    client = ClaudeCodeClient(executable="/fake/claude", model="claude-sonnet-4-6")
    out = client.generate(system="SYS", user="USER", max_tokens=1500)

    assert out == "Carta tailored OK"
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[0] == "/fake/claude"
    assert "-p" in cmd
    assert "--output-format" in cmd and "json" in cmd
    assert "--model" in cmd and "claude-sonnet-4-6" in cmd
    assert "--system-prompt" in cmd
    assert "SYS" in cmd
    assert "--no-session-persistence" in cmd
    assert captured["input"] == "USER"

    assert client.last_usage is not None
    assert client.last_usage.input_tokens == 100
    assert client.last_usage.output_tokens == 50
    assert client.last_usage.cache_creation_input_tokens == 200


def test_claude_code_client_raises_when_executable_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(ConfigError, match=r"claude.*PATH"):
        ClaudeCodeClient()


def test_claude_code_client_raises_on_non_zero_exit(monkeypatch: MonkeyPatch) -> None:
    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeCompleted("", returncode=1, stderr="boom")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    client = ClaudeCodeClient(executable="/fake/claude")
    with pytest.raises(ConfigError, match="exit 1"):
        client.generate(system="S", user="U")


def test_claude_code_client_raises_on_invalid_json(monkeypatch: MonkeyPatch) -> None:
    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeCompleted("not json at all")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    client = ClaudeCodeClient(executable="/fake/claude")
    with pytest.raises(ConfigError, match="JSON"):
        client.generate(system="S", user="U")


def test_claude_code_client_raises_when_is_error_true(monkeypatch: MonkeyPatch) -> None:
    err_payload = json.dumps(
        {"type": "result", "is_error": True, "result": "Not logged in · Please run /login"}
    )

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeCompleted(err_payload)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    client = ClaudeCodeClient(executable="/fake/claude")
    with pytest.raises(ConfigError, match="Not logged in"):
        client.generate(system="S", user="U")


def test_claude_code_client_raises_on_timeout(monkeypatch: MonkeyPatch) -> None:
    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd, timeout=5)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    client = ClaudeCodeClient(executable="/fake/claude", timeout_s=5)
    with pytest.raises(ConfigError, match="timeout"):
        client.generate(system="S", user="U")


def test_make_client_default_is_cli(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("atalaya.generators.claude_client.load_config", lambda: {})
    monkeypatch.delenv("ATALAYA_CLAUDE_BACKEND", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: "/fake/claude")
    client = make_client()
    assert isinstance(client, ClaudeCodeClient)
    assert client.model == DEFAULT_MODEL


def test_make_client_respects_config_backend(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "atalaya.generators.claude_client.load_config",
        lambda: {"claude": {"backend": "cli", "model": "claude-haiku-4-5-20251001"}},
    )
    monkeypatch.delenv("ATALAYA_CLAUDE_BACKEND", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: "/fake/claude")
    client = make_client()
    assert isinstance(client, ClaudeCodeClient)
    assert client.model == "claude-haiku-4-5-20251001"


def test_make_client_env_override(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "atalaya.generators.claude_client.load_config",
        lambda: {"claude": {"backend": "api"}},
    )
    monkeypatch.setenv("ATALAYA_CLAUDE_BACKEND", "cli")
    monkeypatch.setattr("shutil.which", lambda _: "/fake/claude")
    client = make_client()
    assert isinstance(client, ClaudeCodeClient)


def test_make_client_unknown_backend_raises(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("atalaya.generators.claude_client.load_config", lambda: {})
    monkeypatch.setenv("ATALAYA_CLAUDE_BACKEND", "weird")
    with pytest.raises(ConfigError, match="backend desconocido"):
        make_client()


def test_make_client_api_requires_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("atalaya.generators.claude_client.load_config", lambda: {})
    monkeypatch.setenv("ATALAYA_CLAUDE_BACKEND", "api")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "atalaya.generators.claude_client.load_api_key", lambda: None
    )
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        make_client()


def test_claude_api_client_alias_exists() -> None:
    """Retrocompat: ClaudeClient sigue siendo importable como alias."""
    from atalaya.generators.claude_client import ClaudeClient

    assert ClaudeClient is ClaudeApiClient
