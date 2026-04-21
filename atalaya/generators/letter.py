"""Generador de cartas de presentacion tailored con Claude."""

from __future__ import annotations

from typing import Literal

from atalaya.generators.claude_client import ClaudeClient
from atalaya.models import Offer, Profile

Lang = Literal["es", "en"]
Tone = Literal["direct", "warm"]

_MAX_DESCRIPTION_CHARS = 1500

_SYSTEM_BASE_ES = """Eres un asistente que escribe cartas de presentacion concisas y honestas \
para un desarrollador junior que busca su primer empleo dev remoto.

Reglas estrictas (obligatorio):
- Longitud: 2-3 parrafos, 200-280 palabras aproximadamente.
- Primer parrafo: quien soy y que encaja con la oferta.
- Segundo parrafo: un proyecto real que demuestra ese match (Strev o Atalaya segun stack).
- Tercer parrafo: por que esa empresa concreta y cierre honesto.
- Firma final en una linea separada:
  "Alex Mico Robles - alexmico2006@gmail.com - portfolioalex-mico.vercel.app"

Anti-cliches prohibidos:
- "siempre he sido apasionado", "desde pequeno", "equipo dinamico", "gran oportunidad".
- Emojis, superlativos exagerados, saludos genericos tipo "Estimados Sres.".
- No vender al candidato como senior. Es junior post-DAW (graduacion junio 2026).

Reglas de contenido:
- Ser especifico con la stack: si la oferta pide X, mencionar el X real del candidato.
- No inventar experiencia. Solo usar proyectos y stack reales del perfil.
- Empezar directo, sin asunto ni encabezado formal.
- Salida en Markdown plano (sin headers ni bullets, solo parrafos).

Proyectos base del candidato (usar segun encaje con la oferta):
- Strev: SaaS fitness MERN en beta privada. Auth con cookies HttpOnly, tracking de \
entrenamientos, personalizacion de rutinas via Claude API. Stack: React + Node/Express + MongoDB.
- Atalaya: CLI Python con Typer + anthropic SDK. Agrega ofertas dev remoto, scoring contra \
perfil y genera cartas tailored con Claude. Open source MIT.
"""

_SYSTEM_BASE_EN = """You are an assistant that writes concise, honest cover letters \
for a junior developer applying to their first remote dev role.

Strict rules (mandatory):
- Length: 2-3 paragraphs, ~200-280 words.
- First paragraph: who I am and how I fit the role.
- Second paragraph: a real project that proves the match (Strev or Atalaya per stack).
- Third paragraph: why this specific company and an honest closing.
- Final signature on its own line:
  "Alex Mico Robles - alexmico2006@gmail.com - portfolioalex-mico.vercel.app"

Banned cliches:
- "always been passionate", "since I was a kid", "dynamic team", "great opportunity".
- Emojis, inflated superlatives, generic greetings like "Dear Sirs".
- Do not pitch the candidate as senior. They are junior post-DAW (graduating June 2026).

Content rules:
- Be specific with the stack: if the role asks for X, mention the candidate's real X.
- Never invent experience. Only use real projects and stack from the profile.
- Start directly, no subject line or formal header.
- Output: plain Markdown paragraphs (no headers, no bullets).

Candidate base projects (pick the one that fits the role):
- Strev: MERN fitness SaaS in private beta. HttpOnly cookie auth, workout tracking, \
Claude-powered routine personalization. Stack: React + Node/Express + MongoDB.
- Atalaya: Python CLI with Typer + anthropic SDK. Aggregates remote dev offers, scores \
matches against a profile and generates tailored cover letters with Claude. Open source, MIT.
"""


def generate_letter(
    offer: Offer,
    profile: Profile,
    lang: Lang | None = None,
    tone: Tone = "direct",
    client: ClaudeClient | None = None,
) -> str:
    """Genera una carta de presentacion tailored para la oferta.

    Si `lang` no se especifica, se infiere del idioma de la descripcion.
    `client` se inyecta para tests; por defecto se crea uno nuevo.
    """
    resolved_lang: Lang = lang if lang is not None else _infer_lang(offer.description)
    system_prompt = _SYSTEM_BASE_ES if resolved_lang == "es" else _SYSTEM_BASE_EN
    user_prompt = _build_user_prompt(offer, profile, resolved_lang, tone)

    active_client = client if client is not None else ClaudeClient()
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
- Stack core: {profile_core}
- Stack extra: {profile_extra}
- Seniority: {profile.seniority} (disponible {profile.availability})
- Portfolio: {portfolio}
- GitHub: {github}

INSTRUCCIONES FINALES

- Idioma: castellano.
- Tono: {tone} ("direct" = sobrio y sin lloriqueo; "warm" = cercano pero profesional).
- Longitud: 200-280 palabras, 2-3 parrafos.
- Mencionar proyecto relevante (Strev si es MERN/Node/fitness/SaaS; Atalaya si es Python/IA/CLI).
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
- Core stack: {profile_core}
- Extra stack: {profile_extra}
- Seniority: {profile.seniority} (available {profile.availability})
- Portfolio: {portfolio}
- GitHub: {github}

FINAL INSTRUCTIONS

- Language: English.
- Tone: {tone} ("direct" = sober, no whining; "warm" = friendly but professional).
- Length: 200-280 words, 2-3 paragraphs.
- Mention the relevant project (Strev for MERN/Node/fitness/SaaS; Atalaya for Python/AI/CLI).
- Do not invent experience. End with the signature on its own line.
"""
