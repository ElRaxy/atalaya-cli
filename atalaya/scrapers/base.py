"""Interfaz base para scrapers de job boards."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from atalaya.models import Offer

USER_AGENT = "Atalaya/0.1 (+https://github.com/ElRaxy/atalaya-cli)"
DEFAULT_TIMEOUT = 15.0


async def fetch_html(url: str, client: httpx.AsyncClient) -> str:
    response = await client.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.text


class BaseScraper(ABC):
    name: str = ""
    source_url: str = ""

    def __init__(self, max_pages: int = 3, rate_limit_s: float = 1.0) -> None:
        self.max_pages = max_pages
        self.rate_limit_s = rate_limit_s

    @abstractmethod
    async def scrape(self) -> list[Offer]:
        raise NotImplementedError
