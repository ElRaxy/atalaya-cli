"""Tests del enrichment de description (M-A) en RemoteOK + WWR.

Verifica que las descripciones HTML del payload se limpian y populan en
`Offer.description`, lo que permite que EmailApplier extraiga emails.
"""

from __future__ import annotations

from atalaya.appliers.email_apply import EmailApplier
from atalaya.models import Application
from atalaya.profile import default_profile
from atalaya.scrapers.remoteok import RemoteOkScraper
from atalaya.scrapers.weworkremotely import WeWorkRemotelyScraper


def test_remoteok_description_strips_html_and_keeps_email() -> None:
    payload = [
        {
            "0": "Legal",
            "legal": "By using this API you agree to RemoteOK ToS",
            "url": "https://remoteok.com/api",
        },
        {
            "id": "9001",
            "url": "https://remoteok.com/remote-jobs/9001-junior-python",
            "company": "PymeRemota",
            "position": "Junior Python Developer",
            "tags": ["python", "remote"],
            "location": "Worldwide",
            "date": "2026-05-15T10:00:00+02:00",
            "description": (
                "<p>Buscamos junior Python.</p>"
                "<p>Envia tu CV a <a href='mailto:hr@pymeremota.example'>"
                "hr@pymeremota.example</a></p>"
            ),
        },
    ]
    offers = RemoteOkScraper._parse_payload(payload)
    assert len(offers) == 1
    offer = offers[0]
    assert offer.description != ""
    assert "hr@pymeremota.example" in offer.description
    assert "<p>" not in offer.description
    assert "<a" not in offer.description


def test_remoteok_description_caps_at_5000_chars() -> None:
    big = "<p>" + ("x" * 10000) + "</p>"
    payload = [
        {
            "id": "9002",
            "url": "https://remoteok.com/remote-jobs/9002-developer",
            "company": "BigOrg",
            "position": "Senior Developer",
            "tags": ["python"],
            "location": "Worldwide",
            "date": "2026-05-15T10:00:00+02:00",
            "description": big,
        }
    ]
    offers = RemoteOkScraper._parse_payload(payload)
    assert offers[0].description != ""
    assert len(offers[0].description) <= 5000


def test_remoteok_description_handles_missing_field() -> None:
    payload = [
        {
            "id": "9003",
            "url": "https://remoteok.com/remote-jobs/9003-engineer",
            "company": "NoDesc",
            "position": "Backend Engineer",
            "tags": ["python"],
            "location": "Worldwide",
            "date": "2026-05-15T10:00:00+02:00",
        }
    ]
    offers = RemoteOkScraper._parse_payload(payload)
    assert offers[0].description == ""


def test_wwr_description_strips_html_and_keeps_email() -> None:
    desc = (
        "&lt;p&gt;Acme busca Python senior.&lt;/p&gt;"
        "&lt;p&gt;Aplica enviando CV a careers@acme.example&lt;/p&gt;"
    )
    rss = (
        '<?xml version="1.0"?>\n'
        "<rss><channel><item>"
        "<title>Acme Corp: Senior Python Developer (Europe only)</title>"
        "<link>https://weworkremotely.com/remote-jobs/9000-acme-python</link>"
        "<pubDate>Thu, 15 May 2026 10:00:00 +0000</pubDate>"
        f"<description>{desc}</description>"
        "<region>Europe</region>"
        "</item></channel></rss>"
    )
    offers = WeWorkRemotelyScraper._parse_feed(rss)
    assert len(offers) == 1
    offer = offers[0]
    assert offer.description != ""
    assert "careers@acme.example" in offer.description
    assert "<p>" not in offer.description


def test_email_applier_extracts_email_from_enriched_description() -> None:
    """Integración: oferta enriquecida → EmailApplier encuentra target."""
    payload = [
        {
            "id": "9100",
            "url": "https://remoteok.com/remote-jobs/9100-django",
            "company": "PymeAgil",
            "position": "Django Junior",
            "tags": ["python", "django"],
            "location": "Worldwide",
            "date": "2026-05-15T10:00:00+02:00",
            "description": "Junior Django remoto. CV a jobs@pymeagil.example por favor.",
        }
    ]
    offer = RemoteOkScraper._parse_payload(payload)[0]
    target = EmailApplier._extract_target_email(offer)
    assert target == "jobs@pymeagil.example"


def test_email_applier_respects_blocklist_in_enriched_description() -> None:
    """no-reply / support@ siguen filtrados aunque vengan en description enriquecida."""
    payload = [
        {
            "id": "9101",
            "url": "https://remoteok.com/remote-jobs/9101-noreply",
            "company": "BlockListedCorp",
            "position": "Developer",
            "tags": ["python"],
            "location": "Worldwide",
            "date": "2026-05-15T10:00:00+02:00",
            "description": (
                "Apply via portal. Questions: no-reply@listed.example. "
                "Real recruiter: talent@listed.example"
            ),
        }
    ]
    offer = RemoteOkScraper._parse_payload(payload)[0]
    target = EmailApplier._extract_target_email(offer)
    assert target == "talent@listed.example"


def test_full_apply_preview_extracts_email_after_enrichment() -> None:
    """E2E mini: oferta enriquecida → applier preview retorna SKIPPED_PREVIEW con target."""
    payload = [
        {
            "id": "9200",
            "url": "https://remoteok.com/remote-jobs/9200-rust",
            "company": "RustyCo",
            "position": "Rust Engineer",
            "tags": ["rust", "systems"],
            "location": "Worldwide",
            "date": "2026-05-15T10:00:00+02:00",
            "description": "Apply: rust-jobs@rustyco.example",
        }
    ]
    offer = RemoteOkScraper._parse_payload(payload)[0]
    applier = EmailApplier()
    result = applier.apply(
        offer, Application(offer_id=1), default_profile(), preview=True
    )
    assert result.status.value == "skipped_preview"
    assert "rust-jobs@rustyco.example" in result.detail
