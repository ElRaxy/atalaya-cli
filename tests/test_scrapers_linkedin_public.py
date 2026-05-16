"""Tests del parser LinkedIn Public usando fixture HTML."""

from __future__ import annotations

from pathlib import Path

from atalaya.scrapers.linkedin_public import LinkedInPublicScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load_html() -> str:
    return (FIXTURES / "linkedin_public_sample.html").read_text(encoding="utf-8")


def test_parse_listing_extracts_offers() -> None:
    offers = LinkedInPublicScraper._parse_listing(_load_html())
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "linkedin_public"
        assert offer.url.startswith("https://www.linkedin.com/jobs/view/")
        assert offer.remote is True


def test_parse_listing_dedupes_urls() -> None:
    offers = LinkedInPublicScraper._parse_listing(_load_html())
    urls = [o.url for o in offers]
    assert len(urls) == len(set(urls))


def test_parse_listing_extracts_companies() -> None:
    offers = LinkedInPublicScraper._parse_listing(_load_html())
    companies = {o.company for o in offers}
    assert "MVST" in companies
    assert "Acme Tech" in companies
    assert "Globex" in companies


def test_parse_listing_detects_seniority() -> None:
    offers = LinkedInPublicScraper._parse_listing(_load_html())
    junior = next((o for o in offers if "junior" in o.title.lower()), None)
    senior = next((o for o in offers if "senior" in o.title.lower()), None)
    assert junior is not None
    assert junior.seniority == "junior"
    assert senior is not None
    assert senior.seniority == "senior"


def test_parse_listing_detects_stack() -> None:
    offers = LinkedInPublicScraper._parse_listing(_load_html())
    python_offer = next((o for o in offers if "python" in o.title.lower()), None)
    react_offer = next((o for o in offers if "react" in o.title.lower()), None)
    assert python_offer is not None
    assert "python" in python_offer.stack
    assert react_offer is not None
    assert "react" in react_offer.stack


def test_parse_listing_extracts_canonical_url() -> None:
    offers = LinkedInPublicScraper._parse_listing(_load_html())
    ids = {o.url.split("/")[-1] for o in offers}
    assert "4389789491" in ids
    assert "4410570850" in ids


def test_parse_listing_handles_empty_html() -> None:
    assert LinkedInPublicScraper._parse_listing("") == []
    assert LinkedInPublicScraper._parse_listing("<html></html>") == []
