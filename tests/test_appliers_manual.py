"""Tests del ManualApplier + dossier + clipboard (mock)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from atalaya.appliers import ApplyStatus, ManualApplier, copy_to_clipboard
from atalaya.appliers.manual import ManualDossier
from atalaya.models import Application, Offer
from atalaya.profile import default_profile

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def _offer(offer_id: int = 1, url: str = "https://example.com/job/1") -> Offer:
    return Offer(
        id=offer_id,
        source="test",
        title="Senior Backend",
        company="Acme",
        location="Remote",
        remote=True,
        stack=["python"],
        url=url,
        description="",
        seniority="senior",
    )


def _app(letter: str = "CARTA", cv: str = "CV") -> Application:
    return Application(offer_id=1, letter_md=letter, cv_variant_md=cv)


def test_build_dossier_writes_letter_cv_meta(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

    dossier = ManualApplier.build_dossier(_offer(), _app())

    assert dossier.folder.exists()
    assert dossier.letter_path is not None
    assert dossier.letter_path.read_text(encoding="utf-8") == "CARTA"
    assert dossier.cv_path is not None
    assert dossier.cv_path.read_text(encoding="utf-8") == "CV"

    meta = dossier.folder / "offer.txt"
    assert meta.exists()
    assert "Senior Backend" in meta.read_text(encoding="utf-8")


def test_build_dossier_skips_empty_letter_or_cv(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

    dossier = ManualApplier.build_dossier(_offer(), _app(letter="", cv=""))

    assert dossier.letter_path is None
    assert dossier.cv_path is None
    # meta sigue ahí
    assert (dossier.folder / "offer.txt").exists()


def test_copy_to_clipboard_returns_false_on_missing_backend(
    monkeypatch: MonkeyPatch,
) -> None:
    def _raise_not_found(cmd, **kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(subprocess, "run", _raise_not_found)
    assert copy_to_clipboard("hola") is False


def test_copy_to_clipboard_empty_text_returns_false() -> None:
    assert copy_to_clipboard("") is False


def test_copy_to_clipboard_returns_true_on_success(monkeypatch: MonkeyPatch) -> None:
    class _OK:
        returncode = 0

    def _ok(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return _OK()

    monkeypatch.setattr(subprocess, "run", _ok)
    assert copy_to_clipboard("hola") is True


def test_manual_apply_preview_does_not_build_dossier(
    monkeypatch: MonkeyPatch,
) -> None:
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, **kw: opened.append(url))

    applier = ManualApplier(mark_applied=False, open_browser=True)
    result = applier.apply(_offer(), _app(), default_profile(), preview=True)

    assert result.status == ApplyStatus.SKIPPED_PREVIEW
    assert "would prepare" in result.detail.lower()
    assert applier.last_dossier is None
    assert opened == []


def test_manual_apply_opens_browser_and_builds_dossier(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr("atalaya.appliers.manual.copy_to_clipboard", lambda t: True)
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, **kw: opened.append(url))

    applier = ManualApplier(mark_applied=False, open_browser=True)
    result = applier.apply(_offer(), _app(), default_profile())

    assert result.status == ApplyStatus.SKIPPED_PREVIEW
    assert applier.last_dossier is not None
    assert applier.last_dossier.clipboard_copied is True
    assert opened == ["https://example.com/job/1"]


def test_manual_apply_mark_applied_status(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr("atalaya.appliers.manual.copy_to_clipboard", lambda t: False)
    monkeypatch.setattr("webbrowser.open", lambda url, **kw: None)

    applier = ManualApplier(mark_applied=True, open_browser=False)
    result = applier.apply(_offer(), _app(), default_profile())

    assert result.status == ApplyStatus.APPLIED
    assert applier.last_dossier is not None


def test_manual_apply_no_browser_flag(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr("atalaya.appliers.manual.copy_to_clipboard", lambda t: False)
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, **kw: opened.append(url))

    applier = ManualApplier(mark_applied=False, open_browser=False)
    applier.apply(_offer(), _app(), default_profile())
    assert opened == []


def test_manual_dossier_dataclass_fields() -> None:
    d = ManualDossier(
        folder=Path("/tmp/x"),
        letter_path=None,
        cv_path=None,
        clipboard_copied=False,
    )
    assert d.folder == Path("/tmp/x")
    assert d.clipboard_copied is False
