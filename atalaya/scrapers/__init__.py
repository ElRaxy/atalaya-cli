"""Registro de scrapers disponibles."""

from __future__ import annotations

from atalaya.scrapers.base import BaseScraper
from atalaya.scrapers.himalayas import HimalayasScraper
from atalaya.scrapers.indeed_es import IndeedEsScraper
from atalaya.scrapers.infojobs import InfoJobsScraper
from atalaya.scrapers.jobfluent import JobFluentScraper
from atalaya.scrapers.linkedin_public import LinkedInPublicScraper
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
    InfoJobsScraper.name: InfoJobsScraper,
    LinkedInPublicScraper.name: LinkedInPublicScraper,
}

__all__ = [
    "SCRAPERS",
    "BaseScraper",
    "HimalayasScraper",
    "IndeedEsScraper",
    "InfoJobsScraper",
    "JobFluentScraper",
    "LinkedInPublicScraper",
    "RemoteOkScraper",
    "RemoteWorkSpainScraper",
    "TecnoempleoScraper",
    "WeWorkRemotelyScraper",
]
