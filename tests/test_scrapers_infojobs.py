"""Tests del parser de InfoJobs usando fixture HTML."""

from __future__ import annotations

from pathlib import Path

from atalaya.scrapers.infojobs import InfoJobsScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load_html() -> str:
    return (FIXTURES / "infojobs_sample.html").read_text(encoding="utf-8")


def test_parse_listing_extracts_offers() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "infojobs"
        assert offer.url.startswith("https://www.infojobs.net/")
        assert "/of-i" in offer.url
        assert offer.remote is True


def test_parse_listing_dedupes_urls() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    urls = [o.url for o in offers]
    assert len(urls) == len(set(urls))


def test_parse_listing_extracts_company_from_aria_label() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    companies = {o.company for o in offers}
    assert "Luca TIC" in companies
    assert "Globex Soft" in companies
    assert "Hooli Spain" in companies


def test_parse_listing_detects_seniority() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    senior = next((o for o in offers if "senior" in o.title.lower()), None)
    junior = next((o for o in offers if "junior" in o.title.lower()), None)
    assert senior is not None
    assert senior.seniority == "senior"
    assert junior is not None
    assert junior.seniority == "junior"


def test_parse_listing_extracts_salary() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    senior = next((o for o in offers if "qlik" in o.title.lower()), None)
    assert senior is not None
    assert senior.salary_min == 35000
    assert senior.salary_max == 45000


def test_parse_listing_detects_stack_from_tags() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    fullstack = next((o for o in offers if "fullstack" in o.title.lower()), None)
    assert fullstack is not None
    assert "react" in fullstack.stack
    assert "node" in fullstack.stack
    assert "typescript" in fullstack.stack


def test_parse_listing_handles_empty_html() -> None:
    assert InfoJobsScraper._parse_listing("") == []
    assert InfoJobsScraper._parse_listing("<html></html>") == []
