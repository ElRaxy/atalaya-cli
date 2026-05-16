"""Persistencia SQLite: ofertas, candidaturas y auditoria de runs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from atalaya.config import get_db_path
from atalaya.models import Application, Offer, ScoreBreakdown

_SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    remote INTEGER NOT NULL,
    stack TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    posted_at TEXT,
    scraped_at TEXT NOT NULL,
    salary_min INTEGER,
    salary_max INTEGER,
    seniority TEXT,
    raw_html_hash TEXT NOT NULL DEFAULT '',
    score INTEGER,
    score_json TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    offer_id INTEGER PRIMARY KEY,
    status TEXT NOT NULL,
    letter_md TEXT NOT NULL DEFAULT '',
    cv_variant_md TEXT NOT NULL DEFAULT '',
    applied_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (offer_id) REFERENCES offers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    new_count INTEGER NOT NULL,
    updated_count INTEGER NOT NULL,
    errors INTEGER NOT NULL,
    ran_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_seen (
    message_id TEXT PRIMARY KEY,
    folder TEXT NOT NULL,
    sender TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    offers_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_offers_score ON offers(score DESC);
CREATE INDEX IF NOT EXISTS idx_offers_posted ON offers(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_seen_folder ON email_seen(folder, ingested_at DESC);
"""


@contextmanager
def get_conn(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    target = db_path if db_path is not None else get_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> Path:
    target = db_path if db_path is not None else get_db_path()
    with get_conn(target) as conn:
        conn.executescript(_SCHEMA)
    return target


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def upsert_offer(
    offer: Offer,
    score: ScoreBreakdown | None = None,
    db_path: Path | None = None,
) -> tuple[int, bool]:
    """Inserta o actualiza una oferta. Devuelve (id, created)."""
    stack_json = json.dumps(offer.stack, ensure_ascii=False)
    score_value = score.total if score is not None else None
    score_json = score.model_dump_json() if score is not None else None
    with get_conn(db_path) as conn:
        cur = conn.execute("SELECT id FROM offers WHERE url = ?", (offer.url,))
        row = cur.fetchone()
        if row is None:
            cur = conn.execute(
                """
                INSERT INTO offers (
                    source, title, company, location, remote, stack, url, description,
                    posted_at, scraped_at, salary_min, salary_max, seniority,
                    raw_html_hash, score, score_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    offer.source,
                    offer.title,
                    offer.company,
                    offer.location,
                    int(offer.remote),
                    stack_json,
                    offer.url,
                    offer.description,
                    _iso(offer.posted_at),
                    _iso(offer.scraped_at),
                    offer.salary_min,
                    offer.salary_max,
                    offer.seniority,
                    offer.raw_html_hash,
                    score_value,
                    score_json,
                ),
            )
            new_id = cur.lastrowid
            assert new_id is not None
            return new_id, True
        offer_id = int(row["id"])
        conn.execute(
            """
            UPDATE offers SET
                source = ?, title = ?, company = ?, location = ?, remote = ?,
                stack = ?, description = ?, posted_at = COALESCE(?, posted_at),
                scraped_at = ?, salary_min = ?, salary_max = ?, seniority = ?,
                raw_html_hash = ?, score = COALESCE(?, score),
                score_json = COALESCE(?, score_json)
            WHERE id = ?
            """,
            (
                offer.source,
                offer.title,
                offer.company,
                offer.location,
                int(offer.remote),
                stack_json,
                offer.description,
                _iso(offer.posted_at),
                _iso(offer.scraped_at),
                offer.salary_min,
                offer.salary_max,
                offer.seniority,
                offer.raw_html_hash,
                score_value,
                score_json,
                offer_id,
            ),
        )
        return offer_id, False


def _row_to_offer(row: sqlite3.Row) -> Offer:
    posted = row["posted_at"]
    scraped = row["scraped_at"]
    return Offer(
        id=row["id"],
        source=row["source"],
        title=row["title"],
        company=row["company"],
        location=row["location"],
        remote=bool(row["remote"]),
        stack=json.loads(row["stack"]) if row["stack"] else [],
        url=row["url"],
        description=row["description"] or "",
        posted_at=datetime.fromisoformat(posted) if posted else None,
        scraped_at=datetime.fromisoformat(scraped) if scraped else datetime.now(UTC),
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
        seniority=row["seniority"],
        raw_html_hash=row["raw_html_hash"] or "",
    )


def list_offers(
    min_score: int = 0,
    limit: int = 20,
    status_filter: str | None = None,
    db_path: Path | None = None,
) -> list[tuple[Offer, int | None, str | None]]:
    """Lista ofertas ordenadas por score desc. Devuelve (offer, score, status)."""
    query = [
        "SELECT o.*, a.status AS app_status FROM offers o",
        "LEFT JOIN applications a ON a.offer_id = o.id",
        "WHERE COALESCE(o.score, 0) >= ?",
    ]
    params: list[object] = [min_score]
    if status_filter is not None:
        query.append("AND a.status = ?")
        params.append(status_filter)
    query.append("ORDER BY o.score DESC, o.posted_at DESC")
    query.append("LIMIT ?")
    params.append(limit)
    sql = "\n".join(query)
    out: list[tuple[Offer, int | None, str | None]] = []
    with get_conn(db_path) as conn:
        for row in conn.execute(sql, params):
            offer = _row_to_offer(row)
            out.append((offer, row["score"], row["app_status"]))
    return out


def get_offer(offer_id: int, db_path: Path | None = None) -> Offer | None:
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        return _row_to_offer(row) if row is not None else None


def save_application(app: Application, db_path: Path | None = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO applications (offer_id, status, letter_md, cv_variant_md, applied_at, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(offer_id) DO UPDATE SET
                status = excluded.status,
                letter_md = excluded.letter_md,
                cv_variant_md = excluded.cv_variant_md,
                applied_at = excluded.applied_at,
                notes = excluded.notes
            """,
            (
                app.offer_id,
                app.status.value,
                app.letter_md,
                app.cv_variant_md,
                _iso(app.applied_at),
                app.notes,
            ),
        )


def is_email_seen(message_id: str, db_path: Path | None = None) -> bool:
    """Comprueba si un Message-ID ya fue procesado por la ingesta email."""
    if not message_id:
        return False
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM email_seen WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        return row is not None


def mark_email_seen(
    message_id: str,
    folder: str,
    sender: str,
    offers_count: int,
    db_path: Path | None = None,
) -> None:
    """Registra un email como procesado. Idempotente (INSERT OR IGNORE)."""
    if not message_id:
        return
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO email_seen (
                message_id, folder, sender, ingested_at, offers_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                message_id,
                folder,
                sender,
                datetime.now(UTC).isoformat(),
                offers_count,
            ),
        )


def record_run(
    source: str,
    new_count: int,
    updated_count: int,
    errors: int,
    db_path: Path | None = None,
) -> None:
    sql = (
        "INSERT INTO runs (source, new_count, updated_count, errors, ran_at) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    with get_conn(db_path) as conn:
        conn.execute(
            sql,
            (source, new_count, updated_count, errors, datetime.now(UTC).isoformat()),
        )
