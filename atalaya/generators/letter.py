"""Generador de cartas de presentacion tailored con Claude."""

from __future__ import annotations

from typing import Literal

from atalaya.generators.claude_client import ClaudeBackend, make_client
from atalaya.models import Offer, Profile

Lang = Literal["es", "en"]
Tone = Literal["direct", "warm"]

_MAX_DESCRIPTION_CHARS = 1500

_SYSTEM_BASE_ES = """Eres un asistente que escribe cartas de presentacion concisas y honestas \
para un desarrollador junior que busca su primer empleo dev remoto.

Reglas estrictas (obligatorio):
- Longitud: 2-3 parrafos, 200-280 palabras aproximadamente.
- Primer parrafo: quien soy y que encaja con la oferta.
- Segundo parrafo: un proyecto real del perfil que demuestre ese match.
- Tercer parrafo: por que esa empresa concreta y cierre honesto.
- Firma final en una linea separada, con los datos del perfil que se dan abajo:
  "<nombre> - <email> - <portfolio si lo hay>". No inventes ninguno de los tres.

Anti-cliches prohibidos:
- "siempre he sido apasionado", "desde pequeno", "equipo dinamico", "gran oportunidad".
- Emojis, superlativos exagerados, saludos genericos tipo "Estimados Sres.".
- No vender al candidato por encima de la seniority que declara su perfil.

Reglas de contenido:
- Ser especifico con la stack: si la oferta pide X, mencionar el X real del candidato.
- No inventar experiencia. Solo usar proyectos y stack reales del perfil.
- Empezar directo, sin asunto ni encabezado formal.
- Salida en Markdown plano (sin headers ni bullets, solo parrafos).

Los proyectos del candidato llegan en el perfil. Si no trae ninguno, apoyate solo en su
stack y no te inventes proyectos: una carta que cita un proyecto inexistente se cae en la
primera pregunta de la entrevista.
"""

_SYSTEM_BASE_EN = """You are an assistant that writes concise, honest cover letters \
for a junior developer applying to their first remote dev role.

Strict rules (mandatory):
- Length: 2-3 paragraphs, ~200-280 words.
- First paragraph: who I am and how I fit the role.
- Second paragraph: a real project from the profile that proves the match.
- Third paragraph: why this specific company and an honest closing.
- Final signature on its own line, using the profile data given below:
  "<name> - <email> - <portfolio if any>". Never invent any of the three.

Banned cliches:
- "always been passionate", "since I was a kid", "dynamic team", "great opportunity".
- Emojis, inflated superlatives, generic greetings like "Dear Sirs".
- Do not pitch the candidate above the seniority stated in their profile.

Content rules:
- Be specific with the stack: if the role asks for X, mention the candidate's real X.
- Never invent experience. Only use real projects and stack from the profile.
- Start directly, no subject line or formal header.
- Output: plain Markdown paragraphs (no headers, no bullets).

The candidate's projects come with the profile. If it lists none, lean on their stack
alone and invent nothing: a letter citing a project that does not exist collapses at the
first interview question.
"""


def generate_letter(
    offer: Offer,
    profile: Profile,
    lang: Lang | None = None,
    tone: Tone = "direct",
    client: ClaudeBackend | None = None,
) -> str:
    """Genera una carta de presentacion tailored para la oferta.

    Si `lang` no se especifica, se infiere del idioma de la descripcion.
    `client` se inyecta para tests; por defecto se crea el backend de
    `config.toml` (default `cli` = Claude Code subscription).
    """
    resolved_lang: Lang = lang if lang is not None else _infer_lang(offer.description)
    system_prompt = _SYSTEM_BASE_ES if resolved_lang == "es" else _SYSTEM_BASE_EN
    user_prompt = _build_user_prompt(offer, profile, resolved_lang, tone)

    active_client = client if client is not None else make_client()
    return active_client.generate(system=system_prompt, user=user_prompt, max_tokens=1500)


def _infer_lang(description: str) -> Lang:
    """Heuristica simple: si hay marcadores hispanos claros, 'es'; si no, 'en'."""
    text = description.lower()
    spanish_markers = (
        " espana",
        " españa",
        " espanol",
        " castellano",
        " remoto",
        " desarrollador",
        " nosotros ",
        " buscamos ",
    )
    if any(marker in text for marker in spanish_markers):
        return "es"
    return "en"


def _build_user_prompt(offer: Offer, profile: Profile, lang: Lang, tone: Tone) -> str:
    description = offer.description[:_MAX_DESCRIPTION_CHARS]
    if len(offer.description) > _MAX_DESCRIPTION_CHARS:
        description += "..."

    stack_joined = ", ".join(offer.stack) if offer.stack else "(no detectada)"
    profile_core = ", ".join(profile.stack_core)
    profile_extra = ", ".join(profile.stack_extra) if profile.stack_extra else "-"
    portfolio = str(profile.portfolio_url) if profile.portfolio_url else "(sin portfolio)"
    github = str(profile.github_url) if profile.github_url else "(sin github)"
    if profile.projects:
        projects_block = "\n".join(f"- {item}" for item in profile.projects)
    else:
        projects_block = "(el perfil no declara proyectos: no inventes ninguno)"

    if lang == "es":
        return f"""OFERTA

- Titulo: {offer.title}
- Empresa: {offer.company}
- Ubicacion: {offer.location} (remote={offer.remote})
- Stack detectado: {stack_joined}
- Descripcion (recortada):
{description}

PERFIL DEL CANDIDATO

- Nombre: {profile.name}
- Email: {profile.email}
- Stack core: {profile_core}
- Stack extra: {profile_extra}
- Seniority: {profile.seniority} (disponible {profile.availability})
- Portfolio: {portfolio}
- GitHub: {github}
- Proyectos propios:
{projects_block}

INSTRUCCIONES FINALES

- Idioma: castellano.
- Tono: {tone} ("direct" = sobrio y sin lloriqueo; "warm" = cercano pero profesional).
- Longitud: 200-280 palabras, 2-3 parrafos.
- Mencionar el proyecto del perfil que mejor encaje con la oferta, si hay alguno.
- No inventes experiencia. Termina con la firma en linea separada.
"""

    return f"""JOB POSTING

- Title: {offer.title}
- Company: {offer.company}
- Location: {offer.location} (remote={offer.remote})
- Detected stack: {stack_joined}
- Description (trimmed):
{description}

CANDIDATE PROFILE

- Name: {profile.name}
- Email: {profile.email}
- Core stack: {profile_core}
- Extra stack: {profile_extra}
- Seniority: {profile.seniority} (available {profile.availability})
- Portfolio: {portfolio}
- GitHub: {github}
- Own projects:
{projects_block}

FINAL INSTRUCTIONS

- Language: English.
- Tone: {tone} ("direct" = sober, no whining; "warm" = friendly but professional).
- Length: 200-280 words, 2-3 paragraphs.
- Mention whichever profile project best fits the role, if there is one.
- Do not invent experience. End with the signature on its own line.
"""
