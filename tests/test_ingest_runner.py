"""Tests del runner ingest sin tocar IMAP (process_email aislado)."""

from __future__ import annotations

from pathlib import Path

import pytest

from atalaya.ingest.imap_client import parse_message
from atalaya.ingest.runner import (
    IngestResult,
    _offer_from_ingested,
    ingest,
    load_imap_config,
    process_email,
)
from atalaya.profile import default_profile
from atalaya.storage import init_db, is_email_seen, mark_email_seen

FIXTURES = Path(__file__).parent / "fixtures"


def test_process_email_linkedin(tmp_path: Path) -> None:
    db = tmp_path / "atalaya.db"
    init_db(db)
    raw = (FIXTURES / "email_linkedin_alert.eml").read_bytes()
    parsed = parse_message(raw, folder="INBOX")
    profile = default_profile()
    inserted, updated, parser_name = process_email(parsed, profile, db_path=db)
    assert parser_name == "email_linkedin"
    assert inserted == 3
    assert updated == 0


def test_process_email_idempotent_on_rerun(tmp_path: Path) -> None:
    """Re-procesar el mismo email: 0 inserts, N updates."""
    db = tmp_path / "atalaya.db"
    init_db(db)
    raw = (FIXTURES / "email_infojobs_alert.eml").read_bytes()
    parsed = parse_message(raw, folder="INBOX")
    profile = default_profile()
    inserted1, _u1, _ = process_email(parsed, profile, db_path=db)
    inserted2, updated2, _ = process_email(parsed, profile, db_path=db)
    assert inserted1 >= 1
    assert inserted2 == 0
    assert updated2 == inserted1


def test_process_email_unknown_sender_returns_none(tmp_path: Path) -> None:
    db = tmp_path / "atalaya.db"
    init_db(db)
    from atalaya.ingest.base import ParsedEmail

    parsed = ParsedEmail(
        message_id="x@y",
        sender="random@example.com",
        subject="hi",
        date=None,
        folder="INBOX",
        text_body="",
        html_body="",
    )
    inserted, updated, parser_name = process_email(parsed, default_profile(), db_path=db)
    assert parser_name is None
    assert inserted == 0
    assert updated == 0


def test_offer_from_ingested_builds_valid_offer() -> None:
    from atalaya.ingest.base import IngestedOffer

    ingested = IngestedOffer(
        title="Backend Engineer",
        company="Acme",
        url="https://example.com/jobs/1",
        location="Remote",
        remote=True,
        stack=["python", "django"],
    )
    offer = _offer_from_ingested(ingested, "email_test")
    assert offer.source == "email_test"
    assert offer.title == "Backend Engineer"
    assert offer.raw_html_hash != ""


def test_load_imap_config_missing_section() -> None:
    assert load_imap_config({}) is None
    assert load_imap_config({"imap": {}}) is None
    assert load_imap_config({"imap": {"host": "x"}}) is None


def test_load_imap_config_full() -> None:
    cfg = load_imap_config(
        {
            "imap": {
                "host": "imap.gmail.com",
                "port": 993,
                "user": "u@x.com",
                "password": "p",
            }
        }
    )
    assert cfg is not None
    assert cfg.host == "imap.gmail.com"
    assert cfg.port == 993
    assert cfg.use_ssl is True


def test_ingest_marks_email_seen_and_dedupes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simula fetch IMAP con dos fixtures; segunda pasada debe saltarlas."""
    db = tmp_path / "atalaya.db"
    init_db(db)

    parsed_a = parse_message(
        (FIXTURES / "email_linkedin_alert.eml").read_bytes(), folder="INBOX"
    )
    parsed_b = parse_message(
        (FIXTURES / "email_remoteok_alert.eml").read_bytes(), folder="INBOX"
    )

    def fake_fetch(self, **kwargs):  # type: ignore[no-untyped-def]
        return [parsed_a, parsed_b]

    monkeypatch.setattr(
        "atalaya.ingest.runner.IMAPClient.fetch_recent",
        fake_fetch,
    )

    def _seen(mid: str, db_path: Path | None = None) -> bool:
        return is_email_seen(mid, db_path=db)

    def _mark(
        message_id: str,
        folder: str,
        sender: str,
        offers_count: int,
        db_path: Path | None = None,
    ) -> None:
        mark_email_seen(message_id, folder, sender, offers_count, db_path=db)

    monkeypatch.setattr("atalaya.ingest.runner.is_email_seen", _seen)
    monkeypatch.setattr("atalaya.ingest.runner.mark_email_seen", _mark)

    from atalaya.ingest import runner as runner_mod

    original_process = runner_mod.process_email
    monkeypatch.setattr(
        runner_mod,
        "process_email",
        lambda email, profile, db_path=None: original_process(
            email, profile, db_path=db
        ),
    )

    from atalaya.ingest.imap_client import IMAPConfig

    cfg = IMAPConfig(host="fake", port=993, user="u", password="p")
    profile = default_profile()

    res1: IngestResult = ingest(cfg, profile, db_path=db)
    assert res1.emails_scanned == 2
    assert res1.emails_with_parser == 2
    assert res1.offers_inserted >= 3

    res2: IngestResult = ingest(cfg, profile, db_path=db)
    assert res2.emails_scanned == 2
    assert res2.emails_skipped == 2  # ambos ya seen
    assert res2.offers_inserted == 0
