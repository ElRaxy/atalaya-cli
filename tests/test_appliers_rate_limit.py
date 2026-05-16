"""Tests del RateLimiter persistente."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from atalaya.appliers.rate_limit import RateLimiter


def test_acquire_first_call_succeeds(tmp_path: Path) -> None:
    state = tmp_path / "rl.json"
    limiter = RateLimiter(min_interval_s=60, jitter_s=0, state_path=state)
    assert limiter.acquire() is True
    assert state.exists()


def test_acquire_second_immediate_call_blocked(tmp_path: Path) -> None:
    state = tmp_path / "rl.json"
    limiter = RateLimiter(min_interval_s=60, jitter_s=0, state_path=state)
    limiter.acquire()
    assert limiter.acquire() is False
    assert limiter.seconds_until_next() > 0


def test_acquire_after_interval_succeeds(tmp_path: Path) -> None:
    state = tmp_path / "rl.json"
    # Pre-set last_applied_at to 2 hours ago
    past = datetime.now(UTC) - timedelta(hours=2)
    state.write_text(
        json.dumps({"last_applied_at": past.isoformat()}), encoding="utf-8"
    )
    limiter = RateLimiter(min_interval_s=60, jitter_s=0, state_path=state)
    assert limiter.seconds_until_next() == 0.0
    assert limiter.acquire() is True


def test_reset_clears_state(tmp_path: Path) -> None:
    state = tmp_path / "rl.json"
    limiter = RateLimiter(min_interval_s=60, jitter_s=0, state_path=state)
    limiter.acquire()
    assert state.exists()
    limiter.reset()
    assert not state.exists()
    # Reacquire works
    assert limiter.acquire() is True


def test_acquire_handles_corrupt_state_file(tmp_path: Path) -> None:
    state = tmp_path / "rl.json"
    state.write_text("not-valid-json", encoding="utf-8")
    limiter = RateLimiter(min_interval_s=60, jitter_s=0, state_path=state)
    # Treats as no prior state → allows acquire.
    assert limiter.acquire() is True
