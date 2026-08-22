"""Perfil plantilla con el que arranca Atalaya.

Antes esto devolvia el perfil real de su autor: nombre completo, email personal,
ciudad y fecha de graduacion. Cualquiera que instalase el paquete y ejecutase
`bhound init` empezaba con la identidad de otra persona en su `profile.toml`, y
las cartas generadas salian firmadas con ella. Ahora nace vacio y hay que
rellenarlo, que es lo unico honesto en un paquete publico.
"""

from __future__ import annotations

from atalaya.models import Profile

PLACEHOLDER_NAME = "Tu Nombre"
PLACEHOLDER_EMAIL = "tu@email.com"


def default_profile() -> Profile:
    """Plantilla neutra. Se rellena editando `profile.toml` tras `bhound init`."""
    return Profile(
        name=PLACEHOLDER_NAME,
        email=PLACEHOLDER_EMAIL,
        stack_core=["python"],
        stack_extra=[],
        location="Espana",
        seniority="junior",
        availability="inmediata",
        modes=["remote"],
        languages=["es", "en"],
        portfolio_url=None,
        github_url=None,
        projects=[],
    )


def is_placeholder(profile: Profile) -> bool:
    """True si el perfil sigue sin rellenar.

    Sirve para avisar antes de generar una carta: firmarla como "Tu Nombre" y
    mandarla a una empresa es peor que no generarla.
    """
    return profile.name == PLACEHOLDER_NAME or profile.email == PLACEHOLDER_EMAIL
