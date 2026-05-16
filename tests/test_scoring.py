"""Tests de scoring: boundaries de los cuatro ejes."""

from __future__ import annotations

from datetime import UTC, datetime

from atalaya.models import Offer, Profile
from atalaya.scoring import _freshness_modifier, score_offer


def _profile() -> Profile:
    return Profile(
        name="Test",
        email="test@example.com",
        stack_core=["react", "node", "mongodb"],
        stack_extra=["python", "typescript"],
        location="Espana",
        seniority="junior",
        availability="2026-06",
        modes=["remote"],
        languages=["es", "en"],
    )


def _offer(**overrides: object) -> Offer:
    base = {
        "source": "t",
        "title": "Desarrollador",
        "company": "Acme",
        "location": "Espana",
        "remote": True,
        "stack": ["react", "node", "mongodb"],
        "url": "https://example.com/job/x",
        "description": "Buscamos desarrollador espanol",
        "posted_at": datetime(2026, 4, 20),
        "seniority": "junior",
    }
    base.update(overrides)
    return Offer(**base)  # type: ignore[arg-type]


def test_perfect_match_yields_high_score() -> None:
    offer = _offer()
    breakdown = score_offer(offer, _profile())
    assert breakdown.total >= 90
    assert breakdown.stack_match >= 80
    assert breakdown.remote_match == 100
    assert breakdown.seniority_match == 100
    assert breakdown.language_match == 100


def test_no_remote_drops_remote_axis() -> None:
    offer = _offer(remote=False)
    breakdown = score_offer(offer, _profile())
    assert breakdown.remote_match == 0


def test_senior_offer_penalizes_junior() -> None:
    offer = _offer(seniority="senior")
    breakdown = score_offer(offer, _profile())
    assert breakdown.seniority_match == 0


def test_adjacent_seniority_partial() -> None:
    offer = _offer(seniority="mid")
    breakdown = score_offer(offer, _profile())
    assert breakdown.seniority_match == 60


def test_empty_stack_zero() -> None:
    offer = _offer(stack=[])
    breakdown = score_offer(offer, _profile())
    assert breakdown.stack_match == 0


def test_only_extra_stack_no_bonus() -> None:
    offer = _offer(stack=["python", "typescript"])
    breakdown = score_offer(offer, _profile())
    # Sin overlap con core => sin bonus +20
    assert 0 < breakdown.stack_match <= 60


def test_total_bounds_0_100() -> None:
    offer = _offer(stack=[], remote=False, seniority="senior", description="")
    breakdown = score_offer(offer, _profile())
    assert 0 <= breakdown.total <= 100


def test_freshness_boost_for_recent_offer() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    offer = _offer(posted_at=datetime(2026, 5, 13, tzinfo=UTC))
    assert _freshness_modifier(offer, now=now) == 5


def test_freshness_penalty_for_stale_offer() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    offer = _offer(posted_at=datetime(2026, 4, 10, tzinfo=UTC))
    assert _freshness_modifier(offer, now=now) == -5


def test_freshness_neutral_for_mid_age() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    offer = _offer(posted_at=datetime(2026, 4, 28, tzinfo=UTC))
    assert _freshness_modifier(offer, now=now) == 0


def test_freshness_handles_missing_date() -> None:
    offer = _offer(posted_at=None)
    assert _freshness_modifier(offer) == 0


def test_freshness_handles_naive_datetime() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    offer = _offer(posted_at=datetime(2026, 5, 14))  # naive
    assert _freshness_modifier(offer, now=now) == 5


def test_total_includes_freshness_modifier() -> None:
    now_fresh = datetime(2026, 5, 16, tzinfo=UTC)
    fresh = _offer(posted_at=datetime(2026, 5, 14, tzinfo=UTC))
    stale = _offer(posted_at=datetime(2026, 1, 1, tzinfo=UTC))
    # Mismas características salvo fecha → freshness mueve total
    b_fresh = score_offer(fresh, _profile())
    b_stale = score_offer(stale, _profile())
    assert b_fresh.total > b_stale.total
    # Cuando se filtra ahora _freshness_modifier internamente:
    assert _freshness_modifier(fresh, now=now_fresh) == 5
