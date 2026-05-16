"""Tests del storage email_seen (idempotencia ingesta)."""

from __future__ import annotations

from pathlib import Path

from atalaya.storage import init_db, is_email_seen, mark_email_seen


def test_email_seen_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "atalaya.db"
    init_db(db)
    mid = "msg-001@example.com"
    assert not is_email_seen(mid, db_path=db)
    mark_email_seen(mid, "INBOX", "jobs@example.com", 3, db_path=db)
    assert is_email_seen(mid, db_path=db)


def test_email_seen_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "atalaya.db"
    init_db(db)
    mid = "msg-002@example.com"
    mark_email_seen(mid, "INBOX", "jobs@example.com", 1, db_path=db)
    # Re-marca con count distinto: INSERT OR IGNORE → no crashea.
    mark_email_seen(mid, "INBOX", "jobs@example.com", 99, db_path=db)
    assert is_email_seen(mid, db_path=db)


def test_email_seen_empty_id_noop(tmp_path: Path) -> None:
    db = tmp_path / "atalaya.db"
    init_db(db)
    mark_email_seen("", "INBOX", "x@y.com", 1, db_path=db)
    assert not is_email_seen("", db_path=db)
