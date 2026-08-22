"""Tests del parser de Himalayas usando fixtures HTML estaticas."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
import pytest

from atalaya.scrapers.himalayas import HimalayasScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_listing_extracts_offers() -> None:
    html = (FIXTURES / "himalayas_sample.html").read_text(encoding="utf-8")
    offers = HimalayasScraper._parse_listing(html)
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "himalayas"
        assert offer.url.startswith("https://himalayas.app/companies/")
        assert "/jobs/" in offer.url
        assert offer.remote is True
        assert offer.location == "Spain"


def test_parse_listing_extracts_company_and_title() -> None:
    html = (FIXTURES / "himalayas_sample.html").read_text(encoding="utf-8")
    offers = HimalayasScraper._parse_listing(html)
    titles = {o.title for o in offers}
    companies = {o.company for o in offers}
    assert any("analyst" in t.lower() or "developer" in t.lower() for t in titles)
    assert all(c for c in companies)


def test_parse_listing_detects_stack_from_title() -> None:
    html = (FIXTURES / "himalayas_sample.html").read_text(encoding="utf-8")
    offers = HimalayasScraper._parse_listing(html)
    laravel_offer = next((o for o in offers if "laravel" in o.title.lower()), None)
    assert laravel_offer is not None
    assert "laravel" in laravel_offer.stack
    assert "php" in laravel_offer.stack


def test_parse_listing_dedupes_urls() -> None:
    html = (FIXTURES / "himalayas_sample.html").read_text(encoding="utf-8")
    offers = HimalayasScraper._parse_listing(html)
    urls = [o.url for o in offers]
    assert len(urls) == len(set(urls))


def test_403_avisa_en_el_log_en_vez_de_devolver_cero_en_silencio(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Regresion 2026-08-22: un 403 mudo es indistinguible de "hoy no hay ofertas".

    Himalayas empezo a responder 403 tambien con UA de navegador. El scraper
    tragaba la excepcion y devolvia [] sin decir nada, asi que el probe lo daba
    por sano con 0 resultados.
    """

    async def fake_fetch(url: str, client: httpx.AsyncClient) -> str:
        request = httpx.Request("GET", url)
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("Forbidden", request=request, response=response)

    monkeypatch.setattr("atalaya.scrapers.himalayas.fetch_html", fake_fetch)

    with caplog.at_level(logging.WARNING, logger="atalaya.scrapers.himalayas"):
        offers = asyncio.run(HimalayasScraper(max_pages=1).scrape())

    assert offers == []
    assert any("403" in record.getMessage() for record in caplog.records)
