"""Tests del parser de JobFluent usando fixtures HTML estaticas."""

from __future__ import annotations

from pathlib import Path

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
