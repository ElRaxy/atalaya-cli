"""Scraper de InfoJobs.net (job board ES generalista, sección remoto).

Estructura HTML (renderizada server-side las primeras 5 cards; resto requiere JS scroll):

    <li class="ij-List-item ij-OfferList-offerCardItem ...">
      <a class="ij-OfferCardContent-media-link"
         href="https://<empresa>.ofertas-trabajo.infojobs.net"
         aria-label="Empresa">
      <a class="ij-OfferCardContent-description-link"
         href="//www.infojobs.net/<provincia>/<slug>/of-i<hash>?..."
         aria-label="Título de la oferta">

URL de oferta canónica: `https://www.infojobs.net/<provincia>/<slug>/of-i<hash>`.

Limitación: HTTP scraping solo devuelve las primeras 5 cards. Las restantes se cargan vía
JavaScript (scroll/click "siguiente"). Para volumen completo migrar a Playwright (issue M9.2-bis).

Filtro: parámetro `teletrabajo=2` en URL = "Trabajo a distancia". Asumimos remote=True.
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
from atalaya.scrapers.base import USER_AGENT, BaseScraper, fetch_html

_BASE_URL: Final = "https://www.infojobs.net"
_LISTING_TEMPLATE: Final = (
    _BASE_URL
    + "/jobsearch/search-results/list.xhtml?keyword={keyword}&teletrabajo=2&page={page}"
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
    "qlik",
    "power bi",
    "powerbi",
)

_SENIORITY_MAP: Final[dict[str, tuple[str, ...]]] = {
    "intern": ("intern", "trainee", "becario", "prácticas", "practicas"),
    "junior": ("junior", "jr.", "junior developer"),
    "senior": ("senior", "sr.", "staff", "principal", "lead"),
    "mid": ("mid-level", "mid level", "mid", "ssr."),
}

_DEFAULT_KEYWORDS: Final = ("developer", "engineer", "fullstack")


class InfoJobsScraper(BaseScraper):
    """Scraper InfoJobs con filtro teletrabajo. Solo cards initial server-side (5/listing)."""

    name = "infojobs"
    source_url = _LISTING_TEMPLATE.format(keyword="developer", page=1)

    async def scrape(self) -> list[Offer]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120 Safari/537.36 "
                + USER_AGENT
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.6",
        }
        offers: list[Offer] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            for keyword in _DEFAULT_KEYWORDS:
                for page in range(1, self.max_pages + 1):
                    url = _LISTING_TEMPLATE.format(keyword=quote(keyword), page=page)
                    try:
                        listing_html = await fetch_html(url, client)
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
                    if page < self.max_pages:
                        await asyncio.sleep(self.rate_limit_s)
        return offers

    @classmethod
    def _parse_listing(cls, listing_html: str) -> list[Offer]:
        tree = HTMLParser(listing_html)
        offers: list[Offer] = []
        seen_urls: set[str] = set()
        now = datetime.now(UTC)

        for card in tree.css("li.ij-OfferList-offerCardItem"):
            title_anchor = card.css_first("a.ij-OfferCardContent-description-link")
            if title_anchor is None:
                continue
            href = title_anchor.attributes.get("href") or ""
            title = (
                title_anchor.attributes.get("aria-label")
                or title_anchor.text(strip=True)
                or ""
            )
            if not href or not title:
                continue
            detail_url = cls._normalize_url(href)
            if "/of-i" not in detail_url:
                continue
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            company = cls._extract_company(card)
            location = cls._extract_location(card, detail_url)
            tags = cls._extract_tags(card)
            salary_min, salary_max = cls._extract_salary(card)
            posted_at = cls._extract_posted(card, now)
            title_clean = html_lib.unescape(title)
            stack = cls._extract_stack(title_clean, tags)
            seniority = cls._detect_seniority(title_clean, tags)
            raw_hash = hashlib.sha256(
                (detail_url + title_clean).encode("utf-8")
            ).hexdigest()[:16]

            offers.append(
                Offer(
                    source="infojobs",
                    title=title_clean,
                    company=company or "InfoJobs",
                    location=location or "Remoto",
                    remote=True,
                    stack=stack,
                    url=detail_url,
                    description="",
                    posted_at=posted_at,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    seniority=seniority,
                    raw_html_hash=raw_hash,
                )
            )
        return offers

    @staticmethod
    def _normalize_url(href: str) -> str:
        if href.startswith("//"):
            url = "https:" + href
        elif href.startswith("/"):
            url = _BASE_URL + href
        else:
            url = href
        return url.split("?", 1)[0]

    @staticmethod
    def _extract_company(card: Node) -> str:
        anchor = card.css_first("a.ij-OfferCardContent-media-link")
        if anchor is not None:
            label = anchor.attributes.get("aria-label") or ""
            if label:
                return html_lib.unescape(label).strip()
        for anchor_alt in card.css("a"):
            href = anchor_alt.attributes.get("href") or ""
            if "ofertas-trabajo.infojobs.net" in href:
                label = anchor_alt.attributes.get("aria-label") or anchor_alt.text(strip=True)
                if label:
                    return html_lib.unescape(label).strip()
        return ""

    @staticmethod
    def _extract_location(card: Node, detail_url: str) -> str:
        text = card.text() if card else ""
        if re.search(r"\bteletrabajo\b|\bremoto\b", text, flags=re.IGNORECASE):
            return "Remoto"
        # Province from URL: //www.infojobs.net/<provincia>/<slug>/of-iXXX
        match = re.search(r"infojobs\.net/([a-z\-]+)/", detail_url)
        if match:
            province = match.group(1).replace("-", " ").title()
            if province.lower() not in {"jobsearch", "ofertas-trabajo"}:
                return f"{province} (remoto)"
        return "Remoto"

    @staticmethod
    def _extract_tags(card: Node) -> list[str]:
        tags: list[str] = []
        for li in card.css("li.ij-OfferCardContent-description-list-item"):
            text = html_lib.unescape(li.text(strip=True))
            if text and len(text) < 60 and text.lower() not in {t.lower() for t in tags}:
                tags.append(text)
        return tags

    @staticmethod
    def _extract_salary(card: Node) -> tuple[int | None, int | None]:
        text = html_lib.unescape(card.text() if card else "")
        match = re.search(
            r"(\d{1,3}(?:[.\s]\d{3})+)\s*-\s*(\d{1,3}(?:[.\s]\d{3})+)\s*€",
            text,
        )
        if match:
            low = int(re.sub(r"[.\s]", "", match.group(1)))
            high = int(re.sub(r"[.\s]", "", match.group(2)))
            if low >= 10000 and high >= low:
                return low, high
        return None, None

    @staticmethod
    def _extract_posted(card: Node, now: datetime) -> datetime | None:
        text = card.text() if card else ""
        match = re.search(
            r"hace\s+(\d+)\s+(d[íi]as?|horas?|semanas?|meses)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            qty = int(match.group(1))
            unit = match.group(2).lower()
            if "hora" in unit:
                return now - timedelta(hours=qty)
            if unit.startswith(("día", "dia")):
                return now - timedelta(days=qty)
            if "semana" in unit:
                return now - timedelta(weeks=qty)
            if "mes" in unit:
                return now - timedelta(days=qty * 30)
        if re.search(r"\bhoy\b", text, flags=re.IGNORECASE):
            return now
        return None

    @staticmethod
    def _extract_stack(title: str, tags: list[str]) -> list[str]:
        found: list[str] = []
        haystack = (title + " " + " ".join(tags)).lower()
        for kw in _STACK_KEYWORDS:
            pattern = r"(?<![a-z0-9+#.])" + re.escape(kw) + r"(?![a-z0-9+#])"
            if re.search(pattern, haystack):
                canonical = kw.replace("node.js", "node").replace("nodejs", "node")
                canonical = canonical.replace("next.js", "nextjs")
                canonical = canonical.replace("power bi", "powerbi")
                if canonical not in found:
                    found.append(canonical)
        return found

    @staticmethod
    def _detect_seniority(title: str, tags: list[str]) -> str | None:
        haystack = (title + " " + " ".join(tags)).lower()
        for level in ("senior", "mid", "junior", "intern"):
            for kw in _SENIORITY_MAP[level]:
                if kw in haystack:
                    return level
        return None
