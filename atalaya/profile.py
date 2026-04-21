"""Perfil por defecto de Alex Mico para inicializar Atalaya."""

from __future__ import annotations

from atalaya.models import Profile


def default_profile() -> Profile:
    return Profile(
        name="Alex Mico Robles",
        email="raxytonto@gmail.com",
        stack_core=[
            "react",
            "node",
            "express",
            "mongodb",
            "javascript",
            "typescript",
            "python",
        ],
        stack_extra=[
            "anthropic",
            "claude",
            "mern",
            "linux",
            "nginx",
        ],
        location="Alicante, Villena, Espana",
        seniority="junior",
        availability="2026-06",
        modes=["remote", "hybrid_es", "hybrid_eu"],
        languages=["es", "va", "en"],
        portfolio_url="https://portfolioalex-mico.vercel.app",  # type: ignore[arg-type]
        github_url="https://github.com/ElRaxy",  # type: ignore[arg-type]
    )
