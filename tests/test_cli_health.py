"""Tests del comando `bhound health` con scrapers falsos.

El comando existe para poder citar una cifra de scrapers vivos con procedencia:
cualquiera puede reejecutarlo. Lo que se comprueba aqui es que reporta lo que
observa, incluidos los ceros y los fallos, y que no compone ningun veredicto.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from atalaya.cli import app
from atalaya.models import Offer

runner = CliRunner()


def _offer(source: str) -> Offer:
    return Offer(
        source=source,
        title="Python Developer",
        company="Acme",
        location="Remoto",
        remote=True,
        stack=["python"],
        url=f"https://example.com/{source}/1",
        description="",
        raw_html_hash="deadbeef",
    )


class _Vivo:
    name = "vivo"
    source_url = "https://example.com"

    def __init__(self, max_pages: int = 1) -> None:
        self.max_pages = max_pages

    async def scrape(self) -> list[Offer]:
        return [_offer("vivo"), _offer("vivo")]


class _Mudo:
    """Devuelve cero SIN lanzar: el caso que un probe ingenuo da por sano."""

    name = "mudo"
    source_url = "https://example.com"

    def __init__(self, max_pages: int = 1) -> None:
        self.max_pages = max_pages

    async def scrape(self) -> list[Offer]:
        return []


class _Roto:
    name = "roto"
    source_url = "https://example.com"

    def __init__(self, max_pages: int = 1) -> None:
        self.max_pages = max_pages

    async def scrape(self) -> list[Offer]:
        raise ConnectionError("boom")


@pytest.fixture(autouse=True)
def _fake_scrapers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "atalaya.cli.SCRAPERS",
        {"vivo": _Vivo, "mudo": _Mudo, "roto": _Roto},
    )


def test_health_json_reporta_hechos_y_no_veredicto() -> None:
    result = runner.invoke(app, ["health", "--fmt", "json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    facts = {f["scraper"]: f for f in payload["scrapers"]}

    assert facts["vivo"]["offers"] == 2
    assert facts["vivo"]["error_type"] is None
    # Cero y fallo se distinguen: uno tiene recuento, el otro no.
    assert facts["mudo"]["offers"] == 0
    assert facts["mudo"]["error_type"] is None
    assert facts["roto"]["offers"] is None
    assert facts["roto"]["error_type"] == "ConnectionError"

    assert "measured_at" in payload
    assert not any(k in payload for k in ("ok", "healthy", "status", "passed"))


def test_health_tabla_cuenta_solo_los_que_devuelven_ofertas() -> None:
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "1 of 3 scrapers returned offers, 2 in total" in result.stdout


def test_health_rechaza_un_formato_desconocido() -> None:
    result = runner.invoke(app, ["health", "--fmt", "yaml"])
    assert result.exit_code == 2
