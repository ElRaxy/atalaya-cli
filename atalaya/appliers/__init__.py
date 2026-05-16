"""Sistema de appliers (envío automático de candidaturas).

Cada applier implementa `BaseApplier.apply(offer, application, profile)` y devuelve
`ApplyResult` con status final. El registry mapea fuente de oferta → applier preferido.

Estrategia: rate-limit compartido (1 apply / 5 min default) + jitter para evitar
detección como bot. Cuando no hay applier específico, fallback a `email_apply` si la
descripción de la oferta contiene un email.

Riesgos: bans en LinkedIn/InfoJobs por apply-spam. Mitigación: cookies sesión real
(no headless puro), rate-limit conservador, dry-run modo `--preview`.
"""

from __future__ import annotations

from atalaya.appliers.base import ApplyResult, ApplyStatus, BaseApplier
from atalaya.appliers.email_apply import EmailApplier
from atalaya.appliers.manual import ManualApplier, ManualDossier, copy_to_clipboard
from atalaya.appliers.rate_limit import RateLimiter

# Registry: source name (= scraper.name) → applier class. None = sin applier específico,
# fallback a EmailApplier si description tiene email.
APPLIERS: dict[str, type[BaseApplier]] = {
    "email": EmailApplier,
    "manual": ManualApplier,
}


def select_applier(source: str) -> type[BaseApplier] | None:
    """Devuelve applier preferido para una fuente. None = usar fallback email."""
    # Sources con applier específico (futuro: linkedin, infojobs, tecnoempleo).
    return APPLIERS.get(source)


__all__ = [
    "APPLIERS",
    "ApplyResult",
    "ApplyStatus",
    "BaseApplier",
    "EmailApplier",
    "ManualApplier",
    "ManualDossier",
    "RateLimiter",
    "copy_to_clipboard",
    "select_applier",
]
