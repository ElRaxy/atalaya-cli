"""Registro de scrapers disponibles."""

from __future__ import annotations

from atalaya.scrapers.base import BaseScraper
from atalaya.scrapers.remoteworkspain import RemoteWorkSpainScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    RemoteWorkSpainScraper.name: RemoteWorkSpainScraper,
}

__all__ = ["SCRAPERS", "BaseScraper", "RemoteWorkSpainScraper"]
