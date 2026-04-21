"""Tests del comando `bhound letter` con DB temporal y generador mockeado."""

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
from atalaya.storage import init_db, upsert_offer

if TYPE_CHECKING:
    from pytest import MonkeyPatch


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: MonkeyPatch) -> Iterator[Path]:
    db_path = tmp_path / "atalaya.db"
    init_db(db_path)

    monkeypatch.setattr("atalaya.storage.get_db_path", lambda: db_path)
    monkeypatch.setattr("atalaya.cli.get_db_path", lambda: db_path)
    yield db_path


@pytest.fixture()
def seed_offer(isolated_db: Path) -> int:
    offer = Offer(
        source="test",
        title="Junior MERN Developer",
        company="Zendrop",
        location="Remote Spain",
        remote=True,
        stack=["react", "node"],
        url="https://example.com/zendrop",
        description="MERN remoto",
        seniority="junior",
    )
    breakdown = ScoreBreakdown(
        total=85, stack_match=90, remote_match=100, seniority_match=100, language_match=70
    )
    offer_id, _ = upsert_offer(offer, score=breakdown, db_path=isolated_db)
    return offer_id


def _fake_generate_letter(**kwargs: object) -> str:
    return "Carta de prueba tailored para la oferta."


def test_letter_persists_to_application(
    isolated_db: Path,
    seed_offer: int,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module, "generate_letter", _fake_generate_letter)

    runner = CliRunner()
    result = runner.invoke(app, ["letter", str(seed_offer), "--lang", "es"])

    assert result.exit_code == 0, result.output
    assert "carta generada" in result.output.lower()

    conn = sqlite3.connect(isolated_db)
    try:
        row = conn.execute(
            "SELECT letter_md, status FROM applications WHERE offer_id = ?",
            (seed_offer,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    letter_md, status = row
    assert "Carta de prueba tailored" in letter_md
    assert status == "drafted"


def test_letter_writes_out_file_when_requested(
    isolated_db: Path,
    seed_offer: int,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module, "generate_letter", _fake_generate_letter)
    out_path = tmp_path / "letters" / "zendrop.md"

    runner = CliRunner()
    result = runner.invoke(
        app, ["letter", str(seed_offer), "--lang", "es", "--out", str(out_path)]
    )

    assert result.exit_code == 0, result.output
    assert out_path.exists()
    assert "Carta de prueba tailored" in out_path.read_text(encoding="utf-8")


def test_letter_rejects_unknown_offer(
    isolated_db: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module, "generate_letter", _fake_generate_letter)

    runner = CliRunner()
    result = runner.invoke(app, ["letter", "9999"])

    assert result.exit_code == 2
    assert "no existe" in result.output.lower()


def test_letter_rejects_invalid_lang(
    isolated_db: Path,
    seed_offer: int,
) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["letter", str(seed_offer), "--lang", "fr"])
    assert result.exit_code == 2
    assert "lang" in result.output.lower()
