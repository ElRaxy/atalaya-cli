"""Scraper de Tecnoempleo.com (dev jobs ES).

Listing URL para remoto: `https://www.tecnoempleo.com/ofertas-trabajo/?te=&pr=remoto&pagina=N`

URLs reales de oferta siguen el patrón:
    https://www.tecnoempleo.com/<slug-titulo-empresa>/<tags-tech>/rf-<hash-16-32-chars>

Paths legacy `/ofertas-trabajo/<slug>/rf-<id>/` también se aceptan (fixture compat).

Estructura típica de cards (HTML server-side, sin auth ni CF agresivo):
- Anchor del título con href que matchea el patrón anterior.
- Empresa en `<a class="text-primary" href="/empresas/<slug>">Empresa</a>` o `span.font-italic`.
- Tags/skills en `<span class="badge">React</span>`, `<span class="hidden-xs">Madrid</span>`.
- Salario opcional `<span class="text-muted">35.000 - 45.000 €</span>`.
- Fecha relativa `Hace 2 días` en `<span class="text-muted small">`.
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import re
from datetime import UTC, datetime, timedelta
from typing import Final

import httpx
from selectolax.parser import HTMLParser, Node

from atalaya.models import Offer
from atalaya.scrapers.base import USER_AGENT, BaseScraper, fetch_html

_BASE_URL: Final = "https://www.tecnoempleo.com"
_LISTING_URL: Final = f"{_BASE_URL}/ofertas-trabajo/?te=&pr=remoto"

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
)

_SENIORITY_MAP: Final[dict[str, tuple[str, ...]]] = {
    "intern": ("intern", "trainee", "becario", "prácticas", "practicas"),
    "junior": ("junior", "jr.", "junior developer"),
    "senior": ("senior", "sr.", "staff", "principal", "lead"),
    "mid": ("mid-level", "mid level", "mid", "ssr."),
}


class TecnoempleoScraper(BaseScraper):
    """Scraper de tecnoempleo.com filtrado por remoto."""

    name = "tecnoempleo"
    source_url = _LISTING_URL

    async def scrape(self) -> list[Offer]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.6",
        }
        offers: list[Offer] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            for page in range(1, self.max_pages + 1):
                url = _LISTING_URL if page == 1 else f"{_LISTING_URL}&pagina={page}"
                try:
                    listing_html = await fetch_html(url, client)
                except httpx.HTTPError:
                    break
                parsed = self._parse_listing(listing_html)
                if not parsed:
                    break
                for offer in parsed:
                    if offer.url in seen:
                        continue
                    seen.add(offer.url)
                    offers.append(offer)
                if page < self.max_pages:
                    await asyncio.sleep(self.rate_limit_s)
        return offers

    @classmethod
    def _parse_listing(cls, listing_html: str) -> list[Offer]:
        tree = HTMLParser(listing_html)
        offers: list[Offer] = []
        seen_urls: set[str] = set()
        now = datetime.now(UTC)

        # Each offer card: anchor with href matching /ofertas-trabajo/<slug>/<id>/
        for anchor in tree.css("a"):
            href = anchor.attributes.get("href") or ""
            if not cls._is_offer_url(href):
                continue
            title_text = anchor.text(strip=True)
            if not title_text or len(title_text) < 5:
                continue
            detail_url = cls._normalize_url(href)
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            card = cls._find_card_root(anchor)
            company = cls._extract_company(card) if card else ""
            location = cls._extract_location(card) if card else "Remoto"
            tags = cls._extract_tags(card) if card else []
            posted_at = cls._extract_posted(card, now) if card else None
            salary_min, salary_max = cls._extract_salary(card) if card else (None, None)

            title = html_lib.unescape(title_text)
            stack = cls._extract_stack(title, tags)
            seniority = cls._detect_seniority(title, tags)
            raw_hash = hashlib.sha256(
                (detail_url + title).encode("utf-8")
            ).hexdigest()[:16]

            offers.append(
                Offer(
                    source="tecnoempleo",
                    title=title,
                    company=company or "Tecnoempleo",
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
    def _is_offer_url(href: str) -> bool:
        # Real-world URL: https://www.tecnoempleo.com/<slug>/<tech>/rf-<hex>
        # Legacy/fixture:  /ofertas-trabajo/<slug>/rf-<id>/
        if "/rf-" not in href:
            return False
        if href.startswith("https://www.tecnoempleo.com/") or href.startswith("/"):
            # exclude navigation/static URLs
            if "/ofertas-trabajo/?" in href or href.rstrip("/").endswith("/ofertas-trabajo"):
                return False
            return True
        return False

    @staticmethod
    def _normalize_url(href: str) -> str:
        if href.startswith("http"):
            return href.split("?", 1)[0]
        return (_BASE_URL + href).split("?", 1)[0]

    @staticmethod
    def _find_card_root(node: Node, max_climbs: int = 6) -> Node | None:
        # Walk up to find card container (selectolax doesn't expose parent directly,
        # but we can look at anchor itself + reasonable surrounding text via siblings).
        # Workaround: use node directly as container, accept that some fields may be empty.
        return node

    @staticmethod
    def _extract_company(card: Node) -> str:
        # Look for anchor pointing to /empresas/<slug>
        for anchor in card.css("a"):
            href = anchor.attributes.get("href") or ""
            if "/empresas/" in href:
                txt = html_lib.unescape(anchor.text(strip=True))
                if txt:
                    return txt
        return ""

    @staticmethod
    def _extract_location(card: Node) -> str:
        text = card.text() if card else ""
        text = html_lib.unescape(text)
        if re.search(r"\bremoto\b", text, flags=re.IGNORECASE):
            return "Remoto"
        return "Remoto"

    @staticmethod
    def _extract_tags(card: Node) -> list[str]:
        tags: list[str] = []
        for node in card.css("span"):
            txt = html_lib.unescape(node.text(strip=True))
            if 1 < len(txt) < 30 and txt.lower() not in {t.lower() for t in tags}:
                tags.append(txt)
        return tags

    @staticmethod
    def _extract_posted(card: Node, now: datetime) -> datetime | None:
        text = card.text() if card else ""
        pattern = r"hace\s+(\d+)\s+(d[íi]as?|horas?|semanas?|meses)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            qty = int(match.group(1))
            unit = match.group(2).lower()
            if "hora" in unit:
                return now - timedelta(hours=qty)
            if "día" in unit or "dia" in unit:
                return now - timedelta(days=qty)
            if "semana" in unit:
                return now - timedelta(weeks=qty)
            if "mes" in unit:
                return now - timedelta(days=qty * 30)
        if re.search(r"\bhoy\b", text, flags=re.IGNORECASE):
            return now
        return None

    @staticmethod
    def _extract_salary(card: Node) -> tuple[int | None, int | None]:
        text = card.text() if card else ""
        text = html_lib.unescape(text)
        match = re.search(r"(\d{1,3}(?:[.\s]\d{3})+)\s*-\s*(\d{1,3}(?:[.\s]\d{3})+)\s*€", text)
        if match:
            low = int(re.sub(r"[.\s]", "", match.group(1)))
            high = int(re.sub(r"[.\s]", "", match.group(2)))
            if low >= 10000 and high >= low:
                return low, high
        return None, None

    @staticmethod
    def _extract_stack(title: str, tags: list[str]) -> list[str]:
        found: list[str] = []
        haystack = (title + " " + " ".join(tags)).lower()
        for kw in _STACK_KEYWORDS:
            pattern = r"(?<![a-z0-9+#.])" + re.escape(kw) + r"(?![a-z0-9+#])"
            if re.search(pattern, haystack):
                canonical = kw.replace("node.js", "node").replace("nodejs", "node")
                canonical = canonical.replace("next.js", "nextjs")
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
