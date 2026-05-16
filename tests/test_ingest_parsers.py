"""Tests de los 4 parsers de alertas email contra fixtures .eml."""

from __future__ import annotations

from pathlib import Path

from atalaya.ingest import (
    InfoJobsAlertParser,
    LinkedInAlertParser,
    RemoteOkAlertParser,
    TecnoempleoAlertParser,
    find_parser,
)
from atalaya.ingest.imap_client import parse_message

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return parse_message((FIXTURES / name).read_bytes(), folder="INBOX")


def test_linkedin_parser_extracts_three_offers() -> None:
    parsed = _load("email_linkedin_alert.eml")
    offers = LinkedInAlertParser().parse(parsed)
    titles = [o.title for o in offers]
    assert "Full Stack Developer (Junior)" in titles
    assert "Senior Python Engineer" in titles
    assert "React Frontend Developer" in titles
    # "View job" filtrado (botón sin contenido útil)
    assert len(offers) == 3


def test_linkedin_parser_extracts_company() -> None:
    parsed = _load("email_linkedin_alert.eml")
    offers = LinkedInAlertParser().parse(parsed)
    by_title = {o.title: o for o in offers}
    assert "MVST" in by_title["Full Stack Developer (Junior)"].company
    assert "Acme Tech" in by_title["Senior Python Engineer"].company


def test_linkedin_parser_detects_seniority_and_stack() -> None:
    parsed = _load("email_linkedin_alert.eml")
    offers = LinkedInAlertParser().parse(parsed)
    by_title = {o.title: o for o in offers}
    assert by_title["Senior Python Engineer"].seniority == "senior"
    assert by_title["Full Stack Developer (Junior)"].seniority == "junior"
    assert "python" in by_title["Senior Python Engineer"].stack
    assert "react" in by_title["React Frontend Developer"].stack


def test_linkedin_parser_canonical_url() -> None:
    parsed = _load("email_linkedin_alert.eml")
    offers = LinkedInAlertParser().parse(parsed)
    urls = {o.url for o in offers}
    assert "https://www.linkedin.com/jobs/view/4389789491" in urls
    assert "https://www.linkedin.com/jobs/view/4410570850" in urls
    # No tracking params
    for o in offers:
        assert "trk=" not in o.url


def test_infojobs_parser_extracts_offers() -> None:
    parsed = _load("email_infojobs_alert.eml")
    offers = InfoJobsAlertParser().parse(parsed)
    titles = [o.title for o in offers]
    assert "Programador Backend Python Junior" in titles
    assert "Desarrollador Fullstack React + Node" in titles
    assert "Junior Frontend Vue" in titles
    assert "Ver oferta" not in titles


def test_infojobs_parser_extracts_company_and_location() -> None:
    parsed = _load("email_infojobs_alert.eml")
    offers = InfoJobsAlertParser().parse(parsed)
    by_title = {o.title: o for o in offers}
    assert "Innovatech" in by_title["Programador Backend Python Junior"].company
    assert "Madrid" in by_title["Programador Backend Python Junior"].location


def test_infojobs_parser_dedupes_url() -> None:
    parsed = _load("email_infojobs_alert.eml")
    offers = InfoJobsAlertParser().parse(parsed)
    urls = [o.url for o in offers]
    assert len(urls) == len(set(urls))


def test_tecnoempleo_parser_extracts_offers() -> None:
    parsed = _load("email_tecnoempleo_alert.eml")
    offers = TecnoempleoAlertParser().parse(parsed)
    titles = [o.title for o in offers]
    assert any("Python" in t for t in titles)
    assert any("TypeScript" in t for t in titles)
    assert any("React" in t for t in titles)


def test_tecnoempleo_parser_detects_remote() -> None:
    parsed = _load("email_tecnoempleo_alert.eml")
    offers = TecnoempleoAlertParser().parse(parsed)
    remote_offers = [o for o in offers if o.remote]
    assert len(remote_offers) >= 1


def test_remoteok_parser_extracts_company_from_title() -> None:
    parsed = _load("email_remoteok_alert.eml")
    offers = RemoteOkAlertParser().parse(parsed)
    by_url = {o.url: o for o in offers}
    senior = next(o for o in offers if "Senior" in o.title)
    assert senior.company == "Acme"
    assert senior.remote is True
    # "Apply" anchor filtrado
    assert all(o.title.lower() != "apply" for o in offers)
    assert "https://remoteok.com/remote-jobs/100001" in by_url


def test_remoteok_parser_canonical_url() -> None:
    parsed = _load("email_remoteok_alert.eml")
    offers = RemoteOkAlertParser().parse(parsed)
    for o in offers:
        assert o.url.startswith("https://remoteok.com/remote-jobs/")
        assert "?" not in o.url


def test_find_parser_dispatch() -> None:
    assert isinstance(
        find_parser("LinkedIn <jobs-noreply@linkedin.com>"), LinkedInAlertParser
    )
    assert isinstance(
        find_parser("InfoJobs <noreply@infojobs.net>"), InfoJobsAlertParser
    )
    assert isinstance(
        find_parser("Tecnoempleo <alertas@tecnoempleo.com>"),
        TecnoempleoAlertParser,
    )
    assert isinstance(
        find_parser("RemoteOK <jobs@remoteok.com>"), RemoteOkAlertParser
    )
    assert find_parser("Random <foo@bar.com>") is None


def test_parse_message_extracts_headers() -> None:
    parsed = _load("email_linkedin_alert.eml")
    assert parsed.message_id == "linkedin-test-001@linkedin.com"
    assert "jobs-noreply@linkedin.com" in parsed.sender
    assert parsed.subject.startswith("Nuevas ofertas")
    assert parsed.html_body  # tiene cuerpo HTML
    assert parsed.date is not None
