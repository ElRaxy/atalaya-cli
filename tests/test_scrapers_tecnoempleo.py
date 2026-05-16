"""Tests del parser HTML de Tecnoempleo usando fixture estática."""

from __future__ import annotations

from pathlib import Path

from atalaya.scrapers.tecnoempleo import TecnoempleoScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load_html() -> str:
    return (FIXTURES / "tecnoempleo_sample.html").read_text(encoding="utf-8")


def test_parse_listing_extracts_offers() -> None:
    offers = TecnoempleoScraper._parse_listing(_load_html())
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "tecnoempleo"
        assert offer.url.startswith("https://www.tecnoempleo.com/")
        assert "/rf-" in offer.url
        assert offer.remote is True


def test_parse_listing_dedupes_urls() -> None:
    offers = TecnoempleoScraper._parse_listing(_load_html())
    urls = [o.url for o in offers]
    assert len(urls) == len(set(urls))


def test_parse_listing_detects_stack() -> None:
    offers = TecnoempleoScraper._parse_listing(_load_html())
    python_offer = next(
        (o for o in offers if "python" in o.title.lower()), None
    )
    assert python_offer is not None
    assert "python" in python_offer.stack


def test_parse_listing_detects_seniority() -> None:
    offers = TecnoempleoScraper._parse_listing(_load_html())
    senior_python = next(
        (o for o in offers if "senior" in o.title.lower()), None
    )
    junior_vue = next(
        (o for o in offers if "junior" in o.title.lower()), None
    )
    assert senior_python is not None
    assert senior_python.seniority == "senior"
    assert junior_vue is not None
    assert junior_vue.seniority == "junior"


def test_parse_listing_handles_empty_html() -> None:
    assert TecnoempleoScraper._parse_listing("<html></html>") == []
    assert TecnoempleoScraper._parse_listing("") == []
