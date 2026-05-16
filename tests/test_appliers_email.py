"""Tests del EmailApplier (parse target email + preview mode)."""

from __future__ import annotations

from atalaya.appliers.base import ApplyStatus
from atalaya.appliers.email_apply import EmailApplier
from atalaya.models import Application, Offer, Profile


def _sample_offer(description: str = "") -> Offer:
    return Offer(
        source="test",
        title="Senior Python Developer",
        company="Acme",
        location="Remoto",
        remote=True,
        stack=["python"],
        url="https://example.com/offer/1",
        description=description,
    )


def _sample_profile() -> Profile:
    return Profile(
        name="Alex Mico",
        email="alex@example.com",
        stack_core=["python"],
        location="Las Palmas",
        seniority="junior",
        availability="inmediata",
        modes=["remote"],
        languages=["es", "en"],
    )


def test_extract_target_email_from_plain_text() -> None:
    offer = _sample_offer("Envía tu CV a hiring@acme.com para aplicar.")
    email = EmailApplier._extract_target_email(offer)
    assert email == "hiring@acme.com"


def test_extract_target_email_skips_blocked() -> None:
    offer = _sample_offer(
        "Contacta no-reply@example.com o también careers@acme.com con tu CV."
    )
    email = EmailApplier._extract_target_email(offer)
    assert email == "careers@acme.com"


def test_extract_target_email_none_when_absent() -> None:
    offer = _sample_offer("Aplica vía nuestro portal web.")
    assert EmailApplier._extract_target_email(offer) is None


def test_apply_skips_when_no_target() -> None:
    offer = _sample_offer("Aplica en nuestro portal.")
    result = EmailApplier().apply(
        offer, Application(offer_id=1), _sample_profile(), preview=False
    )
    assert result.status == ApplyStatus.SKIPPED_NO_TARGET


def test_apply_preview_returns_would_send() -> None:
    offer = _sample_offer("Envía CV a hiring@acme.com")
    result = EmailApplier().apply(
        offer, Application(offer_id=1), _sample_profile(), preview=True
    )
    assert result.status == ApplyStatus.SKIPPED_PREVIEW
    assert "hiring@acme.com" in result.detail


def test_apply_returns_error_when_smtp_not_configured(monkeypatch) -> None:
    # Forzamos config vacía
    monkeypatch.setattr("atalaya.appliers.email_apply.load_config", lambda: {})
    offer = _sample_offer("Envía CV a hiring@acme.com")
    result = EmailApplier().apply(
        offer, Application(offer_id=1), _sample_profile(), preview=False
    )
    assert result.status == ApplyStatus.ERROR
    assert "smtp_not_configured" in result.detail
