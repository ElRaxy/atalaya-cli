"""Scraper de Indeed Espana (es.indeed.com).

ESTADO ACTUAL: bloqueado por Cloudflare con HTTP 403 en GET directo HTTP.
El scraper detecta el bloqueo y devuelve lista vacia con un warning log, sin crash.

# TODO(M5): migrar a Playwright/Firecrawl si el HTTP directo sigue bloqueado.

Parser implementado para cuando el HTTP directo funcione (o cuando se use
Playwright en un futuro M5). Selectores tipicos de Indeed:
- Cada oferta: `div.job_seen_beacon` o elemento con `data-testid="slider_item"`.
- Titulo: `h2.jobTitle span` o `a.jcs-JobTitle span[title]`.
- Empresa: `span[data-testid="company-name"]` o `.companyName`.
- Ubicacion: `div[data-testid="text-location"]` o `.companyLocation`.
- URL detalle: anchor `a.jcs-JobTitle` con href relativo o `jk=` query param.
- Snippet: `div.job-snippet` o `ul` con bullet points.
- Paginacion: `?start=10,20,30` hasta 30 (3 paginas).

Detectores de bloqueo:
- HTTP 403.
- Titulo "Attention Required! | Cloudflare" o texto "captcha"/"unusual traffic".
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import logging
import re
from typing import Final
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from atalaya.models import Offer
from atalaya.scrapers.base import USER_AGENT, BaseScraper

_BASE_URL: Final = "https://es.indeed.com"
_LISTING_URL: Final = (
    "https://es.indeed.com/jobs?q=full+stack+developer&l=remoto"
)

_BLOCK_MARKERS: Final = (
    "attention required! | cloudflare",
    "cf-browser-verification",
    "captcha-container",
    "unusual traffic",
    "px-captcha",
    "we have detected an unusual",
)

_STACK_KEYWORDS: Final = (
    "react",
    "node",
    "nodejs",
    "node.js",
    "python",
    "typescript",
    "javascript",
    "vue",
    "angular",
    "aws",
    "docker",
    "kubernetes",
    "django",
    "laravel",
    "php",
    "java",
    "spring",
    "go",
    "golang",
    "rust",
    "flutter",
    "nextjs",
    "next.js",
    "postgres",
    "mongo",
    "graphql",
)

_SENIORITY_MAP: Final[dict[str, tuple[str, ...]]] = {
    "intern": ("intern", "becario", "becaria", "practicas", "prácticas"),
    "junior": ("junior", "jr.", "entry"),
    "senior": ("senior", "sr.", "lead", "staff", "principal"),
    "mid": ("mid", "mid-level", "ssr"),
}

logger = logging.getLogger("atalaya.scrapers.indeed_es")


class IndeedEsScraper(BaseScraper):
    """Scraper para es.indeed.com con deteccion de bloqueo anti-bot."""

    name = "indeed_es"
    source_url = _LISTING_URL

    async def scrape(self) -> list[Offer]:
        offers: list[Offer] = []
        seen: set[str] = set()
        headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "es,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        }
        async with httpx.AsyncClient(
            headers=headers, follow_redirects=True, timeout=15.0
        ) as client:
            for page in range(self.max_pages):
                start = page * 10
                url = _LISTING_URL if start == 0 else f"{_LISTING_URL}&start={start}"
                try:
                    response = await client.get(url)
                except httpx.HTTPError as exc:
                    logger.warning("indeed_es request error en page=%d: %s", page, exc)
                    break
                if response.status_code == 403 or self._is_blocked(response.text):
                    logger.warning(
                        "indeed_es bloqueado por anti-bot (status=%d) - "
                        "requiere Playwright en futuro milestone",
                        response.status_code,
                    )
                    break
                if response.status_code >= 400:
                    logger.warning(
                        "indeed_es status=%d en page=%d, abortando",
                        response.status_code,
                        page,
                    )
                    break
                parsed = self._parse_listing(response.text)
                if not parsed:
                    break
                for offer in parsed:
                    if offer.url in seen:
                        continue
                    seen.add(offer.url)
                    offers.append(offer)
                if page < self.max_pages - 1:
                    await asyncio.sleep(self.rate_limit_s)
        return offers

    @staticmethod
    def _is_blocked(html: str) -> bool:
        lowered = html.lower()
        return any(marker in lowered for marker in _BLOCK_MARKERS)

    @classmethod
    def _parse_listing(cls, listing_html: str) -> list[Offer]:
        tree = HTMLParser(listing_html)
        offers: list[Offer] = []
        cards = tree.css("div.job_seen_beacon")
        if not cards:
            cards = tree.css("[data-testid='slider_item']")
        for card in cards:
            title_anchor = (
                card.css_first("a.jcs-JobTitle")
                or card.css_first("h2.jobTitle a")
            )
            if title_anchor is None:
                continue
            href = title_anchor.attributes.get("href") or ""
            if not href:
                continue
            detail_url = urljoin(_BASE_URL, href.split("&", 1)[0])

            title_span = title_anchor.css_first("span")
            title = html_lib.unescape(
                title_span.text(strip=True) if title_span else title_anchor.text(strip=True)
            )

            company_node = (
                card.css_first("[data-testid='company-name']")
                or card.css_first("span.companyName")
            )
            company = (
                html_lib.unescape(company_node.text(strip=True))
                if company_node is not None
                else ""
            )

            location_node = (
                card.css_first("[data-testid='text-location']")
                or card.css_first(".companyLocation")
            )
            location = (
                html_lib.unescape(location_node.text(strip=True))
                if location_node is not None
                else ""
            )

            snippet_node = card.css_first("div.job-snippet") or card.css_first("ul")
            snippet = (
                html_lib.unescape(snippet_node.text(strip=True))[:2000]
                if snippet_node is not None
                else ""
            )

            lowered = f"{title} {snippet} {location}".lower()
            stack = cls._extract_stack(lowered)
            remote = cls._detect_remote(lowered)
            seniority = cls._detect_seniority(title)
            raw_hash = hashlib.sha256(
                (detail_url + title).encode("utf-8")
            ).hexdigest()[:16]

            offers.append(
                Offer(
                    source="indeed_es",
                    title=title,
                    company=company or "Indeed ES",
                    location=location or "Espana",
                    remote=remote,
                    stack=stack,
                    url=detail_url,
                    description=snippet,
                    posted_at=None,
                    seniority=seniority,
                    raw_html_hash=raw_hash,
                )
            )
        return offers

    @staticmethod
    def _extract_stack(text: str) -> list[str]:
        found: list[str] = []
        for kw in _STACK_KEYWORDS:
            pattern = r"(?<![a-z0-9+#.])" + re.escape(kw) + r"(?![a-z0-9+#])"
            if re.search(pattern, text):
                canonical = kw.replace("node.js", "node").replace("nodejs", "node")
                canonical = canonical.replace("next.js", "nextjs")
                if canonical not in found:
                    found.append(canonical)
        return found

    @staticmethod
    def _detect_remote(text: str) -> bool:
        return any(
            hint in text
            for hint in ("remoto", "remote", "teletrabajo", "work from home")
        )

    @staticmethod
    def _detect_seniority(title: str) -> str | None:
        lowered = title.lower()
        for level in ("senior", "mid", "junior", "intern"):
            for kw in _SENIORITY_MAP[level]:
                if kw in lowered:
                    return level
        return None
