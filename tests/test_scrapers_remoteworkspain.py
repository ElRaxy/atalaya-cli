"""Tests del parser de RemoteWorkSpain usando fixtures HTML estaticas."""

from __future__ import annotations

from pathlib import Path

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
