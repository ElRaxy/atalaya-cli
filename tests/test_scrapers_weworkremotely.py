"""Tests del parser RSS de WeWorkRemotely usando fixture XML."""

from __future__ import annotations

from pathlib import Path

from atalaya.scrapers.weworkremotely import WeWorkRemotelyScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load_feed() -> str:
    return (FIXTURES / "weworkremotely_sample.xml").read_text(encoding="utf-8")


def test_parse_feed_extracts_offers() -> None:
    offers = WeWorkRemotelyScraper._parse_feed(_load_feed())
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "weworkremotely"
        assert offer.url.startswith("https://weworkremotely.com/remote-jobs/")
        assert offer.remote is True


def test_parse_feed_splits_company_from_title() -> None:
    offers = WeWorkRemotelyScraper._parse_feed(_load_feed())
    acme = next((o for o in offers if "acme" in o.company.lower()), None)
    assert acme is not None
    assert "senior python engineer" in acme.title.lower()
    assert acme.seniority == "senior"


def test_parse_feed_excludes_usa_only_offers() -> None:
    offers = WeWorkRemotelyScraper._parse_feed(_load_feed())
    titles = {o.title.lower() for o in offers}
    assert not any("initech" in t for t in titles)
    companies = {o.company.lower() for o in offers}
    assert "initech" not in companies


def test_parse_feed_detects_stack_from_description() -> None:
    offers = WeWorkRemotelyScraper._parse_feed(_load_feed())
    acme = next((o for o in offers if "acme" in o.company.lower()), None)
    assert acme is not None
    assert "python" in acme.stack
    assert "django" in acme.stack


def test_parse_feed_handles_malformed_xml() -> None:
    assert WeWorkRemotelyScraper._parse_feed("<not valid xml") == []
    assert WeWorkRemotelyScraper._parse_feed("") == []
