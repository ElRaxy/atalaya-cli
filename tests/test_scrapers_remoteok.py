"""Tests del parser de RemoteOK usando fixture JSON estática."""

from __future__ import annotations

import json
from pathlib import Path

from atalaya.scrapers.remoteok import RemoteOkScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load_payload() -> list[dict]:
    raw = (FIXTURES / "remoteok_sample.json").read_text(encoding="utf-8")
    return json.loads(raw)


def test_parse_payload_extracts_dev_offers() -> None:
    payload = _load_payload()
    offers = RemoteOkScraper._parse_payload(payload)
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "remoteok"
        assert offer.url.startswith("https://remoteok.com/")
        assert offer.remote is True


def test_parse_payload_filters_non_dev_roles() -> None:
    payload = _load_payload()
    offers = RemoteOkScraper._parse_payload(payload)
    titles_lower = {o.title.lower() for o in offers}
    assert not any("marketing manager" in t for t in titles_lower)


def test_parse_payload_filters_usa_only_location() -> None:
    payload = _load_payload()
    offers = RemoteOkScraper._parse_payload(payload)
    locations_lower = {o.location.lower() for o in offers}
    assert not any("usa only" in loc for loc in locations_lower)


def test_parse_payload_detects_stack_and_seniority() -> None:
    payload = _load_payload()
    offers = RemoteOkScraper._parse_payload(payload)
    senior_python = next((o for o in offers if "senior python" in o.title.lower()), None)
    assert senior_python is not None
    assert "python" in senior_python.stack
    assert "django" in senior_python.stack
    assert senior_python.seniority == "senior"
    assert senior_python.salary_min == 80000
    assert senior_python.salary_max == 120000


def test_parse_payload_handles_zero_salary_as_none() -> None:
    payload = _load_payload()
    offers = RemoteOkScraper._parse_payload(payload)
    globex = next((o for o in offers if "globex" in o.company.lower()), None)
    assert globex is not None
    assert globex.salary_min is None
    assert globex.salary_max is None


def test_parse_payload_handles_invalid_payload_gracefully() -> None:
    assert RemoteOkScraper._parse_payload({}) == []
    assert RemoteOkScraper._parse_payload([{"foo": "bar"}]) == []
    assert RemoteOkScraper._parse_payload(["not-a-dict"]) == []


def test_ciudad_del_publicador_no_descarta_la_oferta() -> None:
    """Regresion 2026-08-22: `location` paso a traer la ciudad de quien publica.

    Con la lista blanca vieja ("worldwide", "europe", "spain"...) pasaban 4 de 59
    ofertas dev reales; el resto se perdia por un campo que ya no habla de
    elegibilidad. RemoteOK es remote-only: la ciudad no descarta.
    """
    payload: list[dict] = [
        {"legal": "metadata"},
        {
            "position": "Senior Python Developer",
            "company": "Acme",
            "url": "https://remoteok.com/remote-jobs/1",
            "tags": ["python", "backend"],
            "location": "Dronfield, ",
        },
        {
            "position": "React Engineer",
            "company": "Globex",
            "url": "https://remoteok.com/remote-jobs/2",
            "tags": ["react"],
            "location": "",
        },
    ]
    offers = RemoteOkScraper._parse_payload(payload)
    assert len(offers) == 2


def test_restriccion_geografica_explicita_si_descarta() -> None:
    payload: list[dict] = [
        {"legal": "metadata"},
        {
            "position": "Backend Engineer",
            "company": "Acme",
            "url": "https://remoteok.com/remote-jobs/3",
            "tags": ["python"],
            "location": "US only",
        },
    ]
    assert RemoteOkScraper._parse_payload(payload) == []
