"""Generador de variantes de CV tailored por oferta."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from atalaya.generators.claude_client import ClaudeBackend, make_client
from atalaya.models import Offer, Profile

Lang = Literal["es", "en"]

_MAX_DESCRIPTION_CHARS = 1500
_MAX_OUTPUT_TOKENS = 2500

_DEFAULT_CV_BASE_DIR = Path(__file__).resolve().parents[3] / "projects" / "job-search" / "cv"

_SYSTEM_BASE_ES = """Eres un asistente que reescribe un CV markdown para enfatizar la stack \
y experiencia relevante para una oferta concreta, SIN inventar experiencia.

Reglas estrictas (obligatorio):
- Mantener la estructura original del CV (mismos headers, mismo orden de secciones).
- Reordenar bullets dentro de cada seccion para poner primero lo mas relevante a la oferta.
- Quitar bullets que no aporten a esta oferta (maximo 20% de poda).
- Reescribir sutilmente la seccion "Perfil" para enfatizar lo relevante (ej. si oferta es \
Python heavy, reforzar Python y Atalaya; si es MERN, reforzar Strev).
- NUNCA anadir experiencia, proyectos, titulos o habilidades no presentes en el CV base.
- NUNCA cambiar fechas, nombres de empresas, titulos academicos o datos de contacto.
- Salida: markdown valido completo, listo para convertir a PDF. Sin comentarios previos.
"""

_SYSTEM_BASE_EN = """You are an assistant that rewrites a markdown CV to emphasize the stack \
and experience relevant to a specific job posting, WITHOUT fabricating experience.

Strict rules (mandatory):
- Keep the original CV structure (same headers, same section order).
- Reorder bullets within each section so the most role-relevant items come first.
- Drop bullets that do not contribute to this specific role (at most 20% pruning).
- Subtly rewrite the "Profile" section to emphasize what matters (e.g. for a Python-heavy \
role, reinforce Python and Atalaya; for MERN, reinforce Strev).
- NEVER add experience, projects, degrees or skills not present in the base CV.
- NEVER change dates, company names, academic titles or contact details.
- Output: complete valid markdown, ready to convert to PDF. No preamble.
"""


def load_base_cv(lang: Lang, base_dir: Path | None = None) -> str:
    """Carga el CV base markdown para el idioma dado.

    Orden de busqueda:
    1. Argumento `base_dir` si se pasa.
    2. Variable de entorno `ATALAYA_BASE_CV_DIR`.
    3. Path por defecto relativo al repo (`projects/job-search/cv/`).
    """
    if base_dir is not None:
        target_dir = base_dir
    else:
        env_dir = os.environ.get("ATALAYA_BASE_CV_DIR")
        target_dir = Path(env_dir) if env_dir else _DEFAULT_CV_BASE_DIR

    cv_path = target_dir / f"cv-{lang}.md"
    if not cv_path.exists():
        raise FileNotFoundError(
            f"CV base no encontrado en {cv_path}. "
            "Define ATALAYA_BASE_CV_DIR o pasa --cv-base PATH."
        )
    return cv_path.read_text(encoding="utf-8")


def generate_cv_variant(
    offer: Offer,
    profile: Profile,
    base_cv_md: str | None = None,
    lang: Lang = "es",
    client: ClaudeBackend | None = None,
) -> str:
    """Genera una variante del CV reordenada para maximizar el match con la oferta.

    Si `base_cv_md` es None, se carga desde disco segun `lang`.
    """
    del profile  # perfil ya contenido en el CV base; reservado para futuras senas

    if base_cv_md is None:
        base_cv_md = load_base_cv(lang)

    system_prompt = _SYSTEM_BASE_ES if lang == "es" else _SYSTEM_BASE_EN
    user_prompt = _build_user_prompt(offer, base_cv_md, lang)

    active_client = client if client is not None else make_client()
    return active_client.generate(
        system=system_prompt, user=user_prompt, max_tokens=_MAX_OUTPUT_TOKENS
    )


def _build_user_prompt(offer: Offer, base_cv_md: str, lang: Lang) -> str:
    description = offer.description[:_MAX_DESCRIPTION_CHARS]
    if len(offer.description) > _MAX_DESCRIPTION_CHARS:
        description += "..."

    stack_joined = ", ".join(offer.stack) if offer.stack else "(no detectada)"

    if lang == "es":
        return f"""OFERTA OBJETIVO

- Titulo: {offer.title}
- Empresa: {offer.company}
- Stack detectado: {stack_joined}
- Descripcion:
{description}

CV BASE (markdown fuente de verdad; nunca inventar fuera de aqui):

{base_cv_md}

INSTRUCCIONES FINALES

Devuelve el CV completo en markdown, con la misma estructura pero reordenado y \
sutilmente reescrito para maximizar el match con la oferta. Sin comentarios antes \
o despues del markdown.
"""

    return f"""TARGET JOB POSTING

- Title: {offer.title}
- Company: {offer.company}
- Detected stack: {stack_joined}
- Description:
{description}

BASE CV (markdown source of truth; never invent beyond this):

{base_cv_md}

FINAL INSTRUCTIONS

Return the complete CV in markdown, same structure but reordered and subtly rewritten \
to maximize the role match. No commentary before or after the markdown.
"""
