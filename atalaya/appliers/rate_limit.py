"""Rate limiter persistente entre invocaciones del CLI.

Stateful en disco (`<data_dir>/rate_limit.json`). Cada `acquire()`:
- Si último apply fue hace >= `min_interval_s` → marca timestamp y devuelve True.
- Si fue antes → devuelve False sin marcar.

Default: 300s entre applies (5 min). Suficiente para evitar detección obvia como bot.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from atalaya.config import get_data_dir

DEFAULT_MIN_INTERVAL_S = 300.0  # 5 min
JITTER_MAX_S = 90.0  # ± 90s aleatorio para evitar pattern detectable


class RateLimiter:
    """Token-bucket simple con 1 slot, persiste último timestamp en disco."""

    def __init__(
        self,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        jitter_s: float = JITTER_MAX_S,
        state_path: Path | None = None,
    ) -> None:
        self.min_interval_s = min_interval_s
        self.jitter_s = jitter_s
        self._path = state_path or (get_data_dir() / "rate_limit.json")

    def _load_last(self) -> datetime | None:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            iso = data.get("last_applied_at")
            return datetime.fromisoformat(iso) if iso else None
        except (json.JSONDecodeError, ValueError, OSError):
            return None

    def _save_last(self, ts: datetime) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"last_applied_at": ts.isoformat()}),
            encoding="utf-8",
        )

    def seconds_until_next(self) -> float:
        """Segundos restantes hasta poder aplicar de nuevo. 0 = ya."""
        last = self._load_last()
        if last is None:
            return 0.0
        elapsed = (datetime.now(UTC) - last).total_seconds()
        remaining = self.min_interval_s - elapsed
        return max(0.0, remaining)

    def acquire(self) -> bool:
        """Intenta reservar un slot. True = puedes aplicar ahora, False = rate-limited."""
        if self.seconds_until_next() > 0:
            return False
        # Jitter: añade random 0-jitter_s al timestamp para que el próximo intervalo
        # efectivo sea min_interval_s + random(0, jitter_s).
        jitter = random.uniform(0, self.jitter_s)
        ts = datetime.now(UTC) + timedelta(seconds=jitter)
        self._save_last(ts)
        return True

    def reset(self) -> None:
        """Borra el estado. Útil en tests."""
        if self._path.exists():
            self._path.unlink()
