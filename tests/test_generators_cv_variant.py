"""Tests del generador de variantes de CV."""

from __future__ import annotations

from pathlib import Path

import pytest

from atalaya.generators.cv_variant import generate_cv_variant, load_base_cv
from atalaya.models import Offer, Profile


class _FakeClient:
    def __init__(self, reply: str = "# CV\n\nContenido.") -> None:
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
        title="Python Backend Engineer",
        company="Invox",
        location="Remote EU",
        remote=True,
        stack=["python", "fastapi"],
        url="https://example.com/invox",
        description="Buscamos backend Python con experiencia en APIs y LLMs.",
    )


def _profile() -> Profile:
    return Profile(
        name="Alex Mico",
        email="alex@example.com",
        stack_core=["python", "node"],
        location="Alicante",
        seniority="junior",
        availability="2026-06",
        modes=["remote"],
        languages=["es", "en"],
    )


def test_base_cv_is_passed_verbatim_in_user_prompt() -> None:
    client = _FakeClient()
    base_cv = "# Alex Mico\n\n## Perfil\n\nFull Stack MERN junior.\n"
    generate_cv_variant(
        offer=_offer(), profile=_profile(), base_cv_md=base_cv, lang="es", client=client
    )
    assert base_cv in client.user
    assert "Invox" in client.user
    assert "python" in client.user.lower()


def test_system_prompt_prohibits_fabricating_experience() -> None:
    client = _FakeClient()
    generate_cv_variant(
        offer=_offer(), profile=_profile(), base_cv_md="# CV base", lang="es", client=client
    )
    assert "nunca" in client.system.lower()
    assert "inventar" in client.system.lower()


def test_load_base_cv_reads_custom_dir(tmp_path: Path) -> None:
    cv_file = tmp_path / "cv-es.md"
    cv_file.write_text("# Test CV\n", encoding="utf-8")
    result = load_base_cv("es", base_dir=tmp_path)
    assert "# Test CV" in result


def test_load_base_cv_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="CV base no encontrado"):
        load_base_cv("es", base_dir=tmp_path)


def test_returns_non_empty_string() -> None:
    client = _FakeClient(reply="# Alex\n\nCV.")
    result = generate_cv_variant(
        offer=_offer(), profile=_profile(), base_cv_md="# CV", lang="es", client=client
    )
    assert isinstance(result, str)
    assert len(result) > 0
