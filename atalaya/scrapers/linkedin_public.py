"""Scraper público de LinkedIn Jobs (sin auth, sin Easy Apply).

LinkedIn expone `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search`
sin auth: devuelve HTML fragment con ~8-10 cards por request, paginable con `start`.

Filtros soportados vía query:
- `keywords=<query>` — palabras clave en título / descripción.
- `location=Spain` — país/región.
- `f_WT=2` — filtro "remote" (`2` = Remoto; `1` = Híbrido; `3` = Presencial).
- `start=0,25,50,...` — paginación.

URL canónica de oferta: `https://www.linkedin.com/jobs/view/<id>`. No requiere auth para verla.

Limitaciones:
- LinkedIn cambia el HTML con frecuencia → parser pueder romperse.
- Solo devuelve título + empresa + location + fecha. Stack/skills no aparecen en card,
  hay que detectarlos del título (no description).
- LinkedIn puede rate-limit por IP tras muchas requests seguidas. Rate-limit conservador.
- No requiere auth pero LinkedIn detecta scraping pesado → User-Agent realista + delay 2s
  entre páginas.


Sobre la descripcion: NO se pide la pagina de detalle, a diferencia de JobFluent.
Medido el 2026-08-22: el detalle responde 200 en ~1 s pero pesa 315 KB, asi que
las ~89 ofertas de un barrido serian unos 28 MB y 89 peticiones seguidas contra
LinkedIn. Es justo el patron que su anti-bot corta, y perder el listado publico
-que hoy funciona- por ganar el resumen no compensa. Las ofertas de LinkedIn
llegan con titulo, empresa y fecha, y el enlace lleva al detalle.
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import re
from datetime import UTC, datetime, timedelta
from typing import Final
from urllib.parse import quote

import httpx
from selectolax.parser import HTMLParser, Node

from atalaya.models import Offer
from atalaya.scrapers.base import DEFAULT_TIMEOUT, USER_AGENT, BaseScraper

_GUEST_API: Final = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)

_DEFAULT_KEYWORDS: Final = ("developer", "engineer", "fullstack")
_PAGE_SIZE: Final = 25  # LinkedIn devuelve ~10 cards realmente, pero usa start múltiplos de 25

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
    "ruby",
    "rails",
    "go",
    "golang",
    "java",
    "spring",
    "php",
    "laravel",
    "rust",
    "kotlin",
    "swift",
    "flutter",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "postgres",
    "postgresql",
    "mongo",
    "mongodb",
    "redis",
    "graphql",
    "nextjs",
    "next.js",
    "nestjs",
    "express",
    "django",
    "fastapi",
    "ai",
    "ml",
    "llm",
    ".net",
    "c#",
)

_SENIORITY_MAP: Final[dict[str, tuple[str, ...]]] = {
    "intern": ("intern", "trainee", "becario", "prácticas", "practicas"),
    "junior": ("junior", "jr.", "entry-level", "entry level"),
    "senior": ("senior", "sr.", "staff", "principal", "lead"),
    "mid": ("mid-level", "mid level", "mid-senior", "ssr.", " mid "),
}


class LinkedInPublicScraper(BaseScraper):
    """LinkedIn jobs-guest API. Sin auth. Filtro Spain + remote (f_WT=2)."""

    name = "linkedin_public"
    source_url = _GUEST_API + "?keywords=developer&location=Spain&f_WT=2&start=0"

    async def scrape(self) -> list[Offer]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120 Safari/537.36 "
                + USER_AGENT
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.6",
            "Referer": "https://www.linkedin.com/jobs/search",
        }
        offers: list[Offer] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            for keyword in _DEFAULT_KEYWORDS:
                for page in range(self.max_pages):
                    start = page * _PAGE_SIZE
                    url = (
                        f"{_GUEST_API}?keywords={quote(keyword)}"
                        f"&location=Spain&f_WT=2&start={start}"
                    )
                    try:
                        response = await client.get(url, timeout=DEFAULT_TIMEOUT)
                        response.raise_for_status()
                        listing_html = response.text
                    except httpx.HTTPError:
                        break
                    parsed = self._parse_listing(listing_html)
                    if not parsed:
                        break
                    new_in_page = 0
                    for offer in parsed:
                        if offer.url in seen:
                            continue
                        seen.add(offer.url)
                        offers.append(offer)
                        new_in_page += 1
                    if new_in_page == 0:
                        break
                    # LinkedIn conservative rate-limit: 2s between page requests.
                    await asyncio.sleep(max(self.rate_limit_s, 2.0))
        return offers

    @classmethod
    def _parse_listing(cls, listing_html: str) -> list[Offer]:
        tree = HTMLParser(listing_html)
        offers: list[Offer] = []
        seen_urls: set[str] = set()
        now = datetime.now(UTC)

        # Each card: div[data-entity-urn^="urn:li:jobPosting:"] or li directly
        cards = tree.css("[data-entity-urn^='urn:li:jobPosting:']")
        if not cards:
            # Fallback: root-level cards under div.base-card
            cards = tree.css("div.base-card")
        for card in cards:
            urn = card.attributes.get("data-entity-urn", "") or ""
            match = re.search(r"urn:li:jobPosting:(\d+)", urn)
            job_id = match.group(1) if match else cls._extract_id_from_link(card)
            if not job_id:
                continue
            detail_url = f"https://www.linkedin.com/jobs/view/{job_id}"
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            title = cls._extract_title(card)
            if not title:
                continue
            company = cls._extract_company(card)
            location = cls._extract_location(card)
            posted_at = cls._extract_posted(card, now)
            stack = cls._extract_stack(title)
            seniority = cls._detect_seniority(title)
            raw_hash = hashlib.sha256(
                (detail_url + title).encode("utf-8")
            ).hexdigest()[:16]

            offers.append(
                Offer(
                    source="linkedin_public",
                    title=title,
                    company=company or "LinkedIn",
                    location=location or "Spain",
                    remote=True,
                    stack=stack,
                    url=detail_url,
                    description="",
                    posted_at=posted_at,
                    salary_min=None,
                    salary_max=None,
                    seniority=seniority,
                    raw_html_hash=raw_hash,
                )
            )
        return offers

    @staticmethod
    def _extract_id_from_link(card: Node) -> str:
        anchor = card.css_first("a.base-card__full-link")
        if anchor is None:
            anchor = card.css_first("a")
        if anchor is None:
            return ""
        href = anchor.attributes.get("href", "") or ""
        match = re.search(r"/jobs/view/[\w\-]*?-(\d+)\b|/jobs/view/(\d+)\b", href)
        if match:
            return match.group(1) or match.group(2) or ""
        return ""

    @staticmethod
    def _extract_title(card: Node) -> str:
        node = card.css_first("h3.base-search-card__title")
        if node is None:
            node = card.css_first("h3")
        if node is None:
            sr_only = card.css_first("span.sr-only")
            if sr_only is not None:
                return html_lib.unescape(sr_only.text(strip=True))
            return ""
        return html_lib.unescape(node.text(strip=True))

    @staticmethod
    def _extract_company(card: Node) -> str:
        node = card.css_first("h4.base-search-card__subtitle")
        if node is None:
            node = card.css_first("h4")
        if node is None:
            return ""
        anchor = node.css_first("a")
        text = anchor.text(strip=True) if anchor else node.text(strip=True)
        return html_lib.unescape(text)

    @staticmethod
    def _extract_location(card: Node) -> str:
        node = card.css_first("span.job-search-card__location")
        if node is None:
            return ""
        return html_lib.unescape(node.text(strip=True))

    @staticmethod
    def _extract_posted(card: Node, now: datetime) -> datetime | None:
        node = card.css_first("time")
        if node is None:
            return None
        # LinkedIn time element typically has `datetime="2026-05-14"` attribute.
        dt_attr = node.attributes.get("datetime", "") or ""
        if dt_attr:
            try:
                return datetime.fromisoformat(dt_attr).replace(tzinfo=UTC)
            except ValueError:
                pass
        text = node.text(strip=True).lower()
        match = re.search(r"(\d+)\s+(hour|day|week|month)s?\s+ago", text)
        if match:
            qty = int(match.group(1))
            unit = match.group(2)
            if unit == "hour":
                return now - timedelta(hours=qty)
            if unit == "day":
                return now - timedelta(days=qty)
            if unit == "week":
                return now - timedelta(weeks=qty)
            if unit == "month":
                return now - timedelta(days=qty * 30)
        return None

    @staticmethod
    def _extract_stack(title: str) -> list[str]:
        found: list[str] = []
        haystack = title.lower()
        for kw in _STACK_KEYWORDS:
            pattern = r"(?<![a-z0-9+#.])" + re.escape(kw) + r"(?![a-z0-9+#])"
            if re.search(pattern, haystack):
                canonical = kw.replace("node.js", "node").replace("nodejs", "node")
                canonical = canonical.replace("next.js", "nextjs")
                if canonical not in found:
                    found.append(canonical)
        return found

    @staticmethod
    def _detect_seniority(title: str) -> str | None:
        haystack = title.lower()
        for level in ("senior", "mid", "junior", "intern"):
            for kw in _SENIORITY_MAP[level]:
                if kw in haystack:
                    return level
        return None
