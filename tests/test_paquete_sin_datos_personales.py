"""Guardarrail: el paquete publicado no lleva la identidad de nadie dentro.

Antes de la v0.1.0, `atalaya/generators/letter.py` cableaba en su prompt el
nombre, el email y los proyectos de su autor, y `default_profile()` devolvia su
perfil real. Cualquiera que instalase el paquete generaba cartas firmadas con la
identidad de otra persona y las mandaba a empresas de verdad.

Este test no busca "secretos": busca que no vuelva a colarse una identidad
concreta en el codigo que se distribuye.
"""

from __future__ import annotations

import re
from pathlib import Path

from atalaya.profile import default_profile, is_placeholder

PAQUETE = Path(__file__).resolve().parent.parent / "atalaya"

# Nombres y correos que estuvieron cableados y no deben volver.
_IDENTIDADES_PROHIBIDAS = (
    "alexmico2006",
    "raxytonto",
    "Alex Mico",
    "portfolioalex-mico",
)


def _fuentes() -> list[Path]:
    return [p for p in PAQUETE.rglob("*.py")]


def test_ningun_fichero_del_paquete_cablea_una_identidad() -> None:
    culpables: list[str] = []
    for fichero in _fuentes():
        contenido = fichero.read_text(encoding="utf-8")
        for marca in _IDENTIDADES_PROHIBIDAS:
            if marca in contenido:
                culpables.append(f"{fichero.name}: {marca}")
    assert not culpables, f"identidad cableada en el paquete: {culpables}"


def test_ningun_email_real_en_el_codigo_del_paquete() -> None:
    """Se permiten los de ejemplo; cualquier otro dominio real es sospechoso."""
    patron = re.compile(r"[\w.%-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)
    permitidos = {"tu@email.com", "user@example.com"}
    # Los parsers de alertas necesitan reconocer al remitente del portal: esos
    # buzones son publicos y del board, no de una persona.
    dominios_de_portales = (
        "@infojobs.net",
        "@linkedin.com",
        "@remoteok.com",
        "@tecnoempleo.com",
    )
    encontrados: set[str] = set()
    for fichero in _fuentes():
        for correo in patron.findall(fichero.read_text(encoding="utf-8")):
            bajo = correo.lower()
            if (
                bajo not in permitidos
                and not bajo.endswith((".example", "example.com"))
                and not bajo.endswith(dominios_de_portales)
            ):
                encontrados.add(f"{fichero.name}: {correo}")
    assert not encontrados, f"email real en el paquete: {sorted(encontrados)}"


def test_el_perfil_por_defecto_nace_sin_rellenar() -> None:
    perfil = default_profile()

    assert is_placeholder(perfil), "el perfil por defecto trae datos de una persona real"
    assert perfil.projects == [], "no se distribuyen proyectos de nadie"
    assert perfil.portfolio_url is None
    assert perfil.github_url is None
