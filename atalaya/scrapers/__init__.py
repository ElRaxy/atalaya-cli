"""Registro de scrapers disponibles."""

from __future__ import annotations

from atalaya.scrapers.base import BaseScraper
from atalaya.scrapers.himalayas import HimalayasScraper
from atalaya.scrapers.indeed_es import IndeedEsScraper
from atalaya.scrapers.jobfluent import JobFluentScraper
from atalaya.scrapers.remoteworkspain import RemoteWorkSpainScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    RemoteWorkSpainScraper.name: RemoteWorkSpainScraper,
    JobFluentScraper.name: JobFluentScraper,
    HimalayasScraper.name: HimalayasScraper,
    IndeedEsScraper.name: IndeedEsScraper,
}

__all__ = [
    "SCRAPERS",
    "BaseScraper",
    "HimalayasScraper",
    "IndeedEsScraper",
    "JobFluentScraper",
    "RemoteWorkSpainScraper",
]
