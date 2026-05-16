"""Contratos base para parsers de alertas email."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


@dataclass(slots=True)
class ParsedEmail:
    """Email parseado desde IMAP, listo para que un AlertParser lo procese."""

    message_id: str
    sender: str
    subject: str
    date: datetime | None
    folder: str
    text_body: str
    html_body: str


@dataclass(slots=True)
class IngestedOffer:
    """Oferta extraída de un email de alerta. Forma compatible con Offer."""

    title: str
    company: str
    url: str
    location: str = ""
    remote: bool = False
    stack: list[str] = field(default_factory=list)
    description: str = ""
    seniority: str | None = None
    posted_at: datetime | None = None
    salary_min: int | None = None
    salary_max: int | None = None


class BaseAlertParser(ABC):
    """Parser de un proveedor de alertas (LinkedIn, InfoJobs, ...).

    Cada parser declara:
    - `name`: identificador usado como `Offer.source` (debe ser único, prefijo `email_`).
    - `sender_patterns`: lista de subcadenas (lowercase) a buscar en el header `From`
      para decidir si este parser maneja un email. La primera coincidencia gana.
    """

    name: ClassVar[str]
    sender_patterns: ClassVar[list[str]]

    @abstractmethod
    def parse(self, email: ParsedEmail) -> list[IngestedOffer]:
        """Extrae ofertas del cuerpo del email. Devuelve lista (puede estar vacía)."""

    def matches(self, sender: str) -> bool:
        s = sender.lower()
        return any(pat in s for pat in self.sender_patterns)
