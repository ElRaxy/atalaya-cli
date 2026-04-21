"""Tests del generador de cartas: validamos prompts sin llamadas reales."""

from __future__ import annotations

from datetime import UTC, datetime

from atalaya.generators.letter import generate_letter
from atalaya.models import Offer, Profile


class _FakeClient:
    def __init__(self, reply: str = "# Carta\n\nEsto es una carta.") -> None:
        self.reply = reply
        self.system: str = ""
        self.user: str = ""
        self.max_tokens: int = 0

    def generate(
        self,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = 2000,
    ) -> str:
        del model
        self.system = system
        self.user = user
        self.max_tokens = max_tokens
        return self.reply


def _offer() -> Offer:
    return Offer(
        source="test",
        title="Junior Full Stack Developer",
        company="Zendrop",
        location="Remote Spain",
        remote=True,
        stack=["react", "node", "mongodb"],
        url="https://example.com/zendrop",
        description="Buscamos developer junior MERN remoto en Espana con experiencia React y Node.",
        posted_at=datetime(2026, 4, 20, tzinfo=UTC),
        seniority="junior",
    )


def _profile() -> Profile:
    return Profile(
        name="Alex Mico",
        email="alex@example.com",
        stack_core=["react", "node", "express", "mongodb", "javascript"],
        stack_extra=["anthropic", "claude"],
        location="Alicante, Espana",
        seniority="junior",
        availability="2026-06",
        modes=["remote"],
        languages=["es", "en"],
        portfolio_url="https://portfolioalex-mico.vercel.app",  # type: ignore[arg-type]
        github_url="https://github.com/ElRaxy",  # type: ignore[arg-type]
    )


def test_system_prompt_includes_anti_cliche_rules() -> None:
    client = _FakeClient()
    generate_letter(offer=_offer(), profile=_profile(), lang="es", client=client)
    assert "siempre he sido apasionado" in client.system.lower()
    assert "equipo dinamico" in client.system.lower() or "equipo dinámico" in client.system.lower()
    assert "no vender" in client.system.lower() or "junior" in client.system.lower()


def test_user_prompt_includes_offer_stack_and_company() -> None:
    client = _FakeClient()
    generate_letter(offer=_offer(), profile=_profile(), lang="es", client=client)
    assert "Zendrop" in client.user
    assert "react" in client.user.lower()
    assert "node" in client.user.lower()
    assert "mongodb" in client.user.lower()


def test_returns_non_empty_string() -> None:
    client = _FakeClient(reply="Estimado equipo,\n\nMi carta.")
    result = generate_letter(offer=_offer(), profile=_profile(), lang="es", client=client)
    assert isinstance(result, str)
    assert len(result) > 0


def test_english_prompt_when_lang_en() -> None:
    client = _FakeClient()
    generate_letter(offer=_offer(), profile=_profile(), lang="en", client=client)
    assert "banned cliches" in client.system.lower() or "always been passionate" in client.system
    assert "Zendrop" in client.user


def test_infer_lang_defaults_to_english_when_no_spanish_markers() -> None:
    client = _FakeClient()
    offer = Offer(
        source="test",
        title="Senior Engineer",
        company="Acme",
        location="Remote EU",
        remote=True,
        stack=["python"],
        url="https://example.com/acme",
        description="We are hiring a backend engineer with Python and AWS experience.",
    )
    generate_letter(offer=offer, profile=_profile(), client=client)
    assert "Banned cliches" in client.system or "banned cliches" in client.system.lower()
