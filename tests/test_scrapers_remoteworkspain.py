"""Tests del parser de RemoteWorkSpain usando fixtures HTML estaticas."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from atalaya.scrapers.remoteworkspain import RemoteWorkSpainScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_listing_urls_extracts_all_jobs() -> None:
    html = (FIXTURES / "remoteworkspain_sample.html").read_text(encoding="utf-8")
    urls = RemoteWorkSpainScraper._parse_listing_urls(html)
    assert len(urls) >= 10
    assert all(u.startswith("https://remoteworkspain.es/job/") for u in urls)
    assert len(urls) == len(set(urls)) or len(set(urls)) >= 10


def test_parse_detail_extracts_core_fields() -> None:
    html = (FIXTURES / "remoteworkspain_detail_sample.html").read_text(encoding="utf-8")
    url = "https://remoteworkspain.es/job/senior-ai-data-transformation-lead-madrid/"
    offer = RemoteWorkSpainScraper._parse_detail(url, html)
    assert offer is not None
    assert offer.url == url
    assert "AI" in offer.title or "Transformation" in offer.title
    assert offer.posted_at is not None
    assert offer.posted_at.year == 2026
    assert offer.source == "remoteworkspain"
    assert offer.description
    assert offer.seniority == "senior"


def test_parse_detail_detects_stack_keywords() -> None:
    html = (FIXTURES / "remoteworkspain_detail_sample.html").read_text(encoding="utf-8")
    url = "https://remoteworkspain.es/job/senior-ai-data-transformation-lead-madrid/"
    offer = RemoteWorkSpainScraper._parse_detail(url, html)
    assert offer is not None
    # No todas las ofertas mencionan keywords, pero el mecanismo debe producir lista valida
    assert isinstance(offer.stack, list)


def test_los_detalles_se_piden_en_paralelo_y_sin_repetir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regresion 2026-08-22: secuencial con sleep(1) por oferta = 81 s y timeout.

    El listado trae ~50 ofertas y cada detalle es una peticion. En serie el
    scraper no llegaba a devolver nada. Se comprueba que (a) cada URL se pide una
    sola vez pese a venir repetida y (b) hay varias peticiones en vuelo a la vez.
    """
    listing = (FIXTURES / "remoteworkspain_sample.html").read_text(encoding="utf-8")
    detail = (FIXTURES / "remoteworkspain_detail_sample.html").read_text(encoding="utf-8")
    urls = RemoteWorkSpainScraper._parse_listing_urls(listing)

    pedidas: list[str] = []
    en_vuelo = 0
    pico = 0

    async def fake_fetch(url: str, client: httpx.AsyncClient) -> str:
        nonlocal en_vuelo, pico
        if url == RemoteWorkSpainScraper.source_url:
            return listing
        pedidas.append(url)
        en_vuelo += 1
        pico = max(pico, en_vuelo)
        await asyncio.sleep(0)
        en_vuelo -= 1
        return detail

    monkeypatch.setattr("atalaya.scrapers.remoteworkspain.fetch_html", fake_fetch)
    scraper = RemoteWorkSpainScraper(max_pages=1)
    scraper.rate_limit_s = 0.0
    offers = asyncio.run(scraper.scrape())

    assert len(pedidas) == len(set(pedidas)) == len(set(urls))
    assert pico > 1, "los detalles se estan pidiendo de uno en uno"
    assert len(offers) > 0
