"""Registro de scrapers disponibles."""

from __future__ import annotations

from atalaya.scrapers.base import BaseScraper
from atalaya.scrapers.himalayas import HimalayasScraper
from atalaya.scrapers.indeed_es import IndeedEsScraper
from atalaya.scrapers.jobfluent import JobFluentScraper
from atalaya.scrapers.remoteok import RemoteOkScraper
from atalaya.scrapers.remoteworkspain import RemoteWorkSpainScraper
from atalaya.scrapers.tecnoempleo import TecnoempleoScraper
from atalaya.scrapers.weworkremotely import WeWorkRemotelyScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    RemoteWorkSpainScraper.name: RemoteWorkSpainScraper,
    JobFluentScraper.name: JobFluentScraper,
    HimalayasScraper.name: HimalayasScraper,
    IndeedEsScraper.name: IndeedEsScraper,
    RemoteOkScraper.name: RemoteOkScraper,
    WeWorkRemotelyScraper.name: WeWorkRemotelyScraper,
    TecnoempleoScraper.name: TecnoempleoScraper,
}

__all__ = [
    "SCRAPERS",
    "BaseScraper",
    "HimalayasScraper",
    "IndeedEsScraper",
    "JobFluentScraper",
    "RemoteOkScraper",
    "RemoteWorkSpainScraper",
    "TecnoempleoScraper",
    "WeWorkRemotelyScraper",
]
