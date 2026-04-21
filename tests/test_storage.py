"""Tests de storage SQLite: upsert y list_offers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from atalaya.models import Offer, ScoreBreakdown
from atalaya.storage import init_db, list_offers, upsert_offer


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "atalaya.db"
    init_db(path)
    return path


def _offer(url: str, score_total: int = 80) -> tuple[Offer, ScoreBreakdown]:
    offer = Offer(
        source="test",
        title=f"Job {url[-3:]}",
        company="Acme",
        location="Espana",
        remote=True,
        stack=["react", "node"],
        url=url,
        description="descripcion",
        posted_at=datetime(2026, 4, 20),
        seniority="junior",
    )
    breakdown = ScoreBreakdown(
        total=score_total,
        stack_match=80,
        remote_match=100,
        seniority_match=100,
        language_match=70,
    )
    return offer, breakdown


def test_upsert_inserts_new(db_path: Path) -> None:
    offer, breakdown = _offer("https://example.com/j1")
    offer_id, created = upsert_offer(offer, score=breakdown, db_path=db_path)
    assert created is True
    assert offer_id > 0


def test_upsert_idempotent_on_same_url(db_path: Path) -> None:
    offer, breakdown = _offer("https://example.com/j2")
    id1, created1 = upsert_offer(offer, score=breakdown, db_path=db_path)
    id2, created2 = upsert_offer(offer, score=breakdown, db_path=db_path)
    assert id1 == id2
    assert created1 is True
    assert created2 is False


def test_list_offers_respects_min_score(db_path: Path) -> None:
    high, high_score = _offer("https://example.com/high", score_total=90)
    low, low_score = _offer("https://example.com/low", score_total=10)
    upsert_offer(high, score=high_score, db_path=db_path)
    upsert_offer(low, score=low_score, db_path=db_path)

    rows = list_offers(min_score=50, limit=10, db_path=db_path)
    assert len(rows) == 1
    offer, score, _ = rows[0]
    assert score == 90
    assert offer.url == "https://example.com/high"


def test_list_offers_sorted_desc(db_path: Path) -> None:
    for idx, s in enumerate([30, 80, 50]):
        offer, breakdown = _offer(f"https://example.com/o{idx}", score_total=s)
        upsert_offer(offer, score=breakdown, db_path=db_path)
    rows = list_offers(min_score=0, limit=10, db_path=db_path)
    scores = [r[1] for r in rows]
    assert scores == sorted(scores, reverse=True)
