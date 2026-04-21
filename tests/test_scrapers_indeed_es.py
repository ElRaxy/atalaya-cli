"""Tests del parser de Indeed ES + deteccion de bloqueo anti-bot."""

from __future__ import annotations

from pathlib import Path

from atalaya.scrapers.indeed_es import IndeedEsScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_detect_cloudflare_blocked_html() -> None:
    blocked = (FIXTURES / "indeed_blocked_sample.html").read_text(encoding="utf-8")
    assert IndeedEsScraper._is_blocked(blocked) is True


def test_detect_non_blocked_html() -> None:
    sample = (FIXTURES / "indeed_sample.html").read_text(encoding="utf-8")
    assert IndeedEsScraper._is_blocked(sample) is False


def test_parse_listing_extracts_cards() -> None:
    html = (FIXTURES / "indeed_sample.html").read_text(encoding="utf-8")
    offers = IndeedEsScraper._parse_listing(html)
    assert len(offers) == 2
    first = offers[0]
    assert first.source == "indeed_es"
    assert first.url.startswith("https://es.indeed.com/rc/clk")
    assert "Full Stack" in first.title
    assert first.company == "Acme Spain SL"
    assert first.remote is True
    assert "react" in first.stack
    assert "node" in first.stack


def test_parse_listing_detects_seniority_and_hybrid() -> None:
    html = (FIXTURES / "indeed_sample.html").read_text(encoding="utf-8")
    offers = IndeedEsScraper._parse_listing(html)
    second = offers[1]
    assert second.seniority == "senior"
    assert "python" in second.stack
    assert "django" in second.stack
    assert second.location == "Madrid (Hibrido)"


def test_parse_listing_empty_when_no_cards() -> None:
    empty = "<html><body><p>nothing here</p></body></html>"
    assert IndeedEsScraper._parse_listing(empty) == []
