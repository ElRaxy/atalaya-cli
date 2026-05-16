"""Interfaz base + tipos compartidos para appliers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from atalaya.models import Application, Offer, Profile


class ApplyStatus(StrEnum):
    """Resultado de un intento de aplicar."""

    APPLIED = "applied"
    SKIPPED_NO_TARGET = "skipped_no_target"
    SKIPPED_RATE_LIMIT = "skipped_rate_limit"
    SKIPPED_PREVIEW = "skipped_preview"
    SKIPPED_ALREADY_APPLIED = "skipped_already_applied"
    ERROR = "error"


@dataclass(frozen=True)
class ApplyResult:
    """Resultado tipado de `BaseApplier.apply`."""

    status: ApplyStatus
    detail: str = ""
    """Mensaje legible (target email, error, etc.). Persiste en `Application.notes`."""


class BaseApplier(ABC):
    """Interfaz de un applier de candidaturas.

    Implementaciones concretas:
    - `EmailApplier` — busca email en description, envía SMTP.
    - `LinkedInApplier` (futuro) — Playwright Easy Apply.
    - `InfoJobsApplier` (futuro) — Playwright form fill.

    Convención: nunca lanza en path normal. Errores → `ApplyResult(status=ERROR, detail=...)`.
    """

    name: str = ""

    @abstractmethod
    def apply(
        self,
        offer: Offer,
        application: Application,
        profile: Profile,
        *,
        preview: bool = False,
    ) -> ApplyResult:
        """Intenta aplicar a `offer` con `application.letter_md` + `cv_variant_md`.

        Args:
            offer: oferta target.
            application: contiene `letter_md` y `cv_variant_md` ya generados.
            profile: perfil del candidato (name, email, etc.).
            preview: si True, no envía nada — solo simula y devuelve SKIPPED_PREVIEW.

        Returns:
            ApplyResult con status final.
        """
        raise NotImplementedError
