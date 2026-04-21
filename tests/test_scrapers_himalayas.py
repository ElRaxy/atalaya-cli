"""Tests del parser de Himalayas usando fixtures HTML estaticas."""

from __future__ import annotations

from pathlib import Path

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
    laravel_offer = next(
        (o for o in offers if "laravel" in o.title.lower()), None
    )
    assert laravel_offer is not None
    assert "laravel" in laravel_offer.stack
    assert "php" in laravel_offer.stack


def test_parse_listing_dedupes_urls() -> None:
    html = (FIXTURES / "himalayas_sample.html").read_text(encoding="utf-8")
    offers = HimalayasScraper._parse_listing(html)
    urls = [o.url for o in offers]
    assert len(urls) == len(set(urls))
