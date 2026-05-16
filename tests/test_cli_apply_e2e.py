"""Tests E2E del flujo `bhound letter → cv → apply`.

Atrapa regresiones de:
- Bug #1: apply ignora letter_md/cv_variant_md guardados.
- Bug #2: letter/cv se machacan mutuamente al upsert.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from atalaya import cli as cli_module
from atalaya.cli import app
from atalaya.models import Offer, ScoreBreakdown
from atalaya.storage import get_application, init_db, upsert_offer

if TYPE_CHECKING:
    from pytest import MonkeyPatch


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: MonkeyPatch) -> Iterator[Path]:
    db_path = tmp_path / "atalaya.db"
    init_db(db_path)

    monkeypatch.setattr("atalaya.storage.get_db_path", lambda: db_path)
    monkeypatch.setattr("atalaya.cli.get_db_path", lambda: db_path)
    # Aísla RateLimiter state JSON al tmp_path para evitar cross-test contamination
    monkeypatch.setattr("atalaya.appliers.rate_limit.get_data_dir", lambda: tmp_path)
    yield db_path


@pytest.fixture()
def seed_offer_with_email(isolated_db: Path) -> int:
    offer = Offer(
        source="test",
        title="Junior MERN Developer",
        company="Zendrop",
        location="Remote Spain",
        remote=True,
        stack=["react", "node"],
        url="https://example.com/zendrop",
        description="MERN remoto. Envía CV a hr@zendrop.example.",
        seniority="junior",
    )
    breakdown = ScoreBreakdown(
        total=85,
        stack_match=90,
        remote_match=100,
        seniority_match=100,
        language_match=70,
    )
    offer_id, _ = upsert_offer(offer, score=breakdown, db_path=isolated_db)
    return offer_id


def _fake_letter(**kwargs: object) -> str:
    return "CARTA_TAILORED_PRUEBA"


def _fake_cv_variant(**kwargs: object) -> str:
    return "CV_VARIANT_PRUEBA"


def _fake_load_base_cv(lang: str, base_dir: Path | None = None) -> str:
    return "CV base markdown."


def test_letter_then_cv_does_not_overwrite_letter(
    isolated_db: Path,
    seed_offer_with_email: int,
    monkeypatch: MonkeyPatch,
) -> None:
    """Bug #2 regression: tras `letter` + `cv`, ambos campos persisten."""
    monkeypatch.setattr(cli_module, "generate_letter", _fake_letter)
    monkeypatch.setattr(cli_module, "generate_cv_variant", _fake_cv_variant)
    monkeypatch.setattr(cli_module, "load_base_cv", _fake_load_base_cv)

    runner = CliRunner()
    r1 = runner.invoke(app, ["letter", str(seed_offer_with_email)])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(app, ["cv", str(seed_offer_with_email)])
    assert r2.exit_code == 0, r2.output

    app_persisted = get_application(seed_offer_with_email, db_path=isolated_db)
    assert app_persisted is not None
    assert app_persisted.letter_md == "CARTA_TAILORED_PRUEBA"
    assert app_persisted.cv_variant_md == "CV_VARIANT_PRUEBA"


def test_cv_then_letter_preserves_cv(
    isolated_db: Path,
    seed_offer_with_email: int,
    monkeypatch: MonkeyPatch,
) -> None:
    """Mismo bug #2 al revés: orden cv → letter también preserva ambos."""
    monkeypatch.setattr(cli_module, "generate_letter", _fake_letter)
    monkeypatch.setattr(cli_module, "generate_cv_variant", _fake_cv_variant)
    monkeypatch.setattr(cli_module, "load_base_cv", _fake_load_base_cv)

    runner = CliRunner()
    r1 = runner.invoke(app, ["cv", str(seed_offer_with_email)])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(app, ["letter", str(seed_offer_with_email)])
    assert r2.exit_code == 0, r2.output

    app_persisted = get_application(seed_offer_with_email, db_path=isolated_db)
    assert app_persisted is not None
    assert app_persisted.letter_md == "CARTA_TAILORED_PRUEBA"
    assert app_persisted.cv_variant_md == "CV_VARIANT_PRUEBA"


def test_apply_preview_uses_persisted_letter_and_cv(
    isolated_db: Path,
    seed_offer_with_email: int,
    monkeypatch: MonkeyPatch,
) -> None:
    """Bug #1 regression: apply --preview ve la letter+cv ya persistidas."""
    monkeypatch.setattr(cli_module, "generate_letter", _fake_letter)
    monkeypatch.setattr(cli_module, "generate_cv_variant", _fake_cv_variant)
    monkeypatch.setattr(cli_module, "load_base_cv", _fake_load_base_cv)

    runner = CliRunner()
    runner.invoke(app, ["letter", str(seed_offer_with_email)])
    runner.invoke(app, ["cv", str(seed_offer_with_email)])

    captured: dict[str, object] = {}

    def _spy_apply(self, offer, application, profile, *, preview=False):  # type: ignore[no-untyped-def]
        captured["letter_md"] = application.letter_md
        captured["cv_variant_md"] = application.cv_variant_md
        from atalaya.appliers.base import ApplyResult, ApplyStatus

        return ApplyResult(
            status=ApplyStatus.SKIPPED_PREVIEW, detail="would send"
        )

    monkeypatch.setattr(
        "atalaya.appliers.email_apply.EmailApplier.apply", _spy_apply
    )

    r = runner.invoke(app, ["apply", str(seed_offer_with_email), "--preview"])
    assert r.exit_code == 0, r.output
    assert captured["letter_md"] == "CARTA_TAILORED_PRUEBA"
    assert captured["cv_variant_md"] == "CV_VARIANT_PRUEBA"


def test_apply_warns_when_no_letter_or_cv(
    isolated_db: Path,
    seed_offer_with_email: int,
    monkeypatch: MonkeyPatch,
) -> None:
    """Apply sobre offer sin letter/cv emite warning visible al user."""
    from atalaya.appliers.base import ApplyResult, ApplyStatus

    def _stub_apply(self, offer, application, profile, *, preview=False):  # type: ignore[no-untyped-def]
        return ApplyResult(status=ApplyStatus.SKIPPED_PREVIEW, detail="preview")

    monkeypatch.setattr(
        "atalaya.appliers.email_apply.EmailApplier.apply", _stub_apply
    )

    runner = CliRunner()
    r = runner.invoke(app, ["apply", str(seed_offer_with_email), "--preview"])
    assert r.exit_code == 0, r.output
    assert "warn" in r.output.lower() or "no hay carta" in r.output.lower()


def test_apply_does_not_lose_letter_cv_when_marking_status(
    isolated_db: Path,
    seed_offer_with_email: int,
    monkeypatch: MonkeyPatch,
) -> None:
    """Tras apply, los campos letter_md/cv_variant_md NO se borran."""
    monkeypatch.setattr(cli_module, "generate_letter", _fake_letter)
    monkeypatch.setattr(cli_module, "generate_cv_variant", _fake_cv_variant)
    monkeypatch.setattr(cli_module, "load_base_cv", _fake_load_base_cv)

    runner = CliRunner()
    runner.invoke(app, ["letter", str(seed_offer_with_email)])
    runner.invoke(app, ["cv", str(seed_offer_with_email)])

    from atalaya.appliers.base import ApplyResult, ApplyStatus

    def _stub_applied(self, offer, application, profile, *, preview=False):  # type: ignore[no-untyped-def]
        return ApplyResult(status=ApplyStatus.APPLIED, detail="email sent fake")

    monkeypatch.setattr(
        "atalaya.appliers.email_apply.EmailApplier.apply", _stub_applied
    )

    r = runner.invoke(app, ["apply", str(seed_offer_with_email), "--force"])
    assert r.exit_code == 0, r.output

    conn = sqlite3.connect(isolated_db)
    try:
        row = conn.execute(
            "SELECT letter_md, cv_variant_md, status, applied_at "
            "FROM applications WHERE offer_id = ?",
            (seed_offer_with_email,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    letter_md, cv_md, status, applied_at = row
    assert letter_md == "CARTA_TAILORED_PRUEBA"
    assert cv_md == "CV_VARIANT_PRUEBA"
    assert status == "applied"
    assert applied_at is not None
