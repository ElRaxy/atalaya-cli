"""Fixtures globales de pytest."""

from __future__ import annotations

import pytest


# Rich decide el ancho por el terminal: en CI es estrecho y parte la salida
# a media palabra, rompiendo asserts que buscan literales. Ancho fijo = salida
# identica en local y en CI.
@pytest.fixture(autouse=True)
def _fixed_terminal_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("TERM", "dumb")
