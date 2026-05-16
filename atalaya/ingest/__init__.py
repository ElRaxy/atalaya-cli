"""Ingesta de ofertas desde alertas email (M7)."""

from __future__ import annotations

from atalaya.ingest.base import BaseAlertParser, IngestedOffer, ParsedEmail
from atalaya.ingest.parsers.infojobs import InfoJobsAlertParser
from atalaya.ingest.parsers.linkedin import LinkedInAlertParser
from atalaya.ingest.parsers.remoteok import RemoteOkAlertParser
from atalaya.ingest.parsers.tecnoempleo import TecnoempleoAlertParser

PARSERS: list[BaseAlertParser] = [
    LinkedInAlertParser(),
    InfoJobsAlertParser(),
    TecnoempleoAlertParser(),
    RemoteOkAlertParser(),
]


def find_parser(sender: str) -> BaseAlertParser | None:
    """Devuelve el primer parser cuyo `sender_patterns` coincida con el `From`."""
    for parser in PARSERS:
        if parser.matches(sender):
            return parser
    return None


__all__ = [
    "PARSERS",
    "BaseAlertParser",
    "InfoJobsAlertParser",
    "IngestedOffer",
    "LinkedInAlertParser",
    "ParsedEmail",
    "RemoteOkAlertParser",
    "TecnoempleoAlertParser",
    "find_parser",
]
