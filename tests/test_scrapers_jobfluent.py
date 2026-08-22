"""Tests del parser de JobFluent usando fixtures HTML estaticas."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from atalaya.scrapers.jobfluent import JobFluentScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_listing_extracts_offers() -> None:
    html = (FIXTURES / "jobfluent_sample.html").read_text(encoding="utf-8")
    offers = JobFluentScraper._parse_listing(html)
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "jobfluent"
        assert offer.url.startswith("https://jobfluent.com/jobs/")
        assert offer.title
        assert offer.company


def test_parse_listing_splits_title_and_company() -> None:
    html = (FIXTURES / "jobfluent_sample.html").read_text(encoding="utf-8")
    offers = JobFluentScraper._parse_listing(html)
    first = offers[0]
    # Example: "Senior Software Engineer at SeQura"
    assert "at" not in first.title.lower().split()[-1]
    assert first.company.lower() == "sequra"


def test_parse_listing_extracts_stack_and_salary() -> None:
    html = (FIXTURES / "jobfluent_sample.html").read_text(encoding="utf-8")
    offers = JobFluentScraper._parse_listing(html)
    haddock = next((o for o in offers if o.company.lower() == "haddock"), None)
    assert haddock is not None
    assert "typescript" in haddock.stack
    assert "node" in haddock.stack
    assert haddock.salary_min == 40000
    assert haddock.salary_max == 55000
    assert haddock.seniority == "senior"


def test_parse_listing_detects_location_from_slug() -> None:
    html = (FIXTURES / "jobfluent_sample.html").read_text(encoding="utf-8")
    offers = JobFluentScraper._parse_listing(html)
    assert all(offer.location for offer in offers)
    # All 3 fixture offers are Barcelona
    assert any(offer.location.lower() == "barcelona" for offer in offers)


def test_pide_el_detalle_para_rellenar_la_descripcion(monkeypatch: pytest.MonkeyPatch) -> None:
    """El listado de JobFluent no trae resumen: sin el detalle la oferta es un titulo.

    Se comprueba que cada oferta se pide una sola vez, que hay varias peticiones en
    vuelo a la vez, y que una que falle no tumba a las demas.
    """
    listing = (FIXTURES / "jobfluent_sample.html").read_text(encoding="utf-8")
    detalle = (
        "<html><body><div class='job-description'>"
        + ("Buscamos una persona con experiencia en Python y React para un equipo remoto. " * 4)
        + "</div></body></html>"
    )

    pedidas: list[str] = []
    en_vuelo = 0
    pico = 0

    async def fake_fetch(url: str, client: object) -> str:
        nonlocal en_vuelo, pico
        if url.rstrip("/").endswith("/jobs"):
            return listing
        pedidas.append(url)
        en_vuelo += 1
        pico = max(pico, en_vuelo)
        await asyncio.sleep(0)
        en_vuelo -= 1
        if "fallona" in url:
            raise httpx.ConnectError("boom")
        return detalle

    monkeypatch.setattr("atalaya.scrapers.jobfluent.fetch_html", fake_fetch)
    scraper = JobFluentScraper(max_pages=1)
    scraper.rate_limit_s = 0.0
    offers = asyncio.run(scraper.scrape())

    assert offers
    assert len(pedidas) == len(set(pedidas)) == len(offers)
    assert pico > 1, "los detalles se estan pidiendo de uno en uno"
    assert all(len(o.description or "") > 100 for o in offers)


def test_una_descripcion_demasiado_corta_no_se_guarda() -> None:
    """Mejor sin descripcion que con el chrome de la pagina: un menu no es una oferta."""
    corta = "<html><body><main>Inicio</main></body></html>"
    assert JobFluentScraper._parse_description(corta) == ""
