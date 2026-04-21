"""Scraper de JobFluent.com (startup jobs Barcelona + Europa).

Estructura del listado:
- URL base `https://jobfluent.com/jobs` redirige a `/jobs-barcelona`.
- Paginacion via query `?page=N` (1..N). Rel next en `<link rel="next">`.
- Cada oferta es un `<div class="panel panel-offer">` con id `offer-<hex>`.
- Titulo + empresa combinados en `<h3 class="offer-title"> <a>...</a>` ("Title at Company").
- Detalle URL en `data-url` del div interno `.offer-col.offer` o el href del anchor.
- Tags stack: anchors `<a class="label label-skill">Nombre</a>`.
- Ubicacion deducida del slug del href (`-barcelona-`, `-madrid-`, `-remote-`).
- Salario opcional en `span.salary > span.text-dark` con texto "40.000 EUR - 55.000 EUR".
- Fecha relativa en `<span class="published-date">added today|yesterday|3 days ago</span>`.

HTML server-side, no requiere Playwright. Sin JSON-LD en listing. Rate limit 1s entre paginas.
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

_BASE_URL: Final = "https://jobfluent.com"
_LISTING_URL: Final = f"{_BASE_URL}/jobs"

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
    "ruby on rails",
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
    "tensorflow",
    "pytorch",
)

_SENIORITY_MAP: Final[dict[str, tuple[str, ...]]] = {
    "intern": ("intern", "becario", "becaria", "practicas", "prácticas", "trainee"),
    "junior": ("junior", "jr.", "entry"),
    "senior": ("senior", "sr.", "staff", "principal", "lead"),
    "mid": ("mid", "mid-level", "ssr", "mid/senior", "middle"),
}

_REMOTE_HINTS: Final = (
    "remote",
    "remoto",
    "teletrabajo",
    "work from home",
    "wfh",
    "fully remote",
)

_HYBRID_HINTS: Final = ("hibrido", "híbrido", "hybrid")


class JobFluentScraper(BaseScraper):
    """Scraper para jobfluent.com."""

    name = "jobfluent"
    source_url = _LISTING_URL

    async def scrape(self) -> list[Offer]:
        offers: list[Offer] = []
        seen: set[str] = set()
        headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en,es;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            for page in range(1, self.max_pages + 1):
                url = _LISTING_URL if page == 1 else f"{_LISTING_URL}?page={page}"
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
        now = datetime.now(UTC)
        for card in tree.css("div.panel.panel-offer"):
            title_node = card.css_first("h3.offer-title a")
            if title_node is None:
                continue
            href = title_node.attributes.get("href") or ""
            if not href.startswith("/jobs/"):
                continue
            detail_url = _BASE_URL + href.split("?", 1)[0]
            raw_title = html_lib.unescape(title_node.text(strip=True))
            title, company = cls._split_title_company(raw_title)

            logo_anchor = card.css_first("a.offer-logo")
            if company == "" and logo_anchor is not None:
                logo_title = logo_anchor.attributes.get("title") or ""
                # "View <Company> company details and its job offerings"
                match = re.match(
                    r"View\s+(.+?)\s+company details", logo_title, flags=re.IGNORECASE
                )
                if match:
                    company = match.group(1).strip()

            stack = cls._extract_stack(card, title)
            location = cls._extract_location(detail_url)
            remote = cls._detect_remote(detail_url, title.lower() + " " + location.lower())
            seniority = cls._detect_seniority(title)
            salary_min, salary_max = cls._extract_salary(card)
            posted_at = cls._parse_relative_date(card, now)
            raw_hash = hashlib.sha256(
                (detail_url + raw_title).encode("utf-8")
            ).hexdigest()[:16]

            offers.append(
                Offer(
                    source="jobfluent",
                    title=title or raw_title,
                    company=company or "JobFluent",
                    location=location or "Spain",
                    remote=remote,
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
    def _split_title_company(raw: str) -> tuple[str, str]:
        # Pattern: "<Title> at <Company>"
        match = re.match(r"^(.*?)\s+at\s+(.+)$", raw, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return raw, ""

    @staticmethod
    def _extract_stack(card: Node, title: str) -> list[str]:
        found: list[str] = []
        skills_nodes = card.css("a.label.label-skill")
        for node in skills_nodes:
            label = html_lib.unescape(node.text(strip=True)).lower()
            label = label.replace(".js", "js").replace(" ", "")
            # Normalize variants to canonical keys
            if label in ("nodejs", "node.js"):
                label = "node"
            elif label in ("next.js",):
                label = "nextjs"
            if label and label not in found:
                found.append(label)
        lowered = title.lower()
        for kw in _STACK_KEYWORDS:
            pattern = r"(?<![a-z0-9+#.])" + re.escape(kw) + r"(?![a-z0-9+#])"
            if re.search(pattern, lowered):
                canonical = kw.replace("node.js", "node").replace("nodejs", "node")
                canonical = canonical.replace("next.js", "nextjs")
                if canonical not in found:
                    found.append(canonical)
        return found

    @staticmethod
    def _extract_location(detail_url: str) -> str:
        # Slug ends with "-<location>-<hex6>?..." - extract second-to-last token
        path = detail_url.rsplit("/", 1)[-1]
        slug = path.split("?", 1)[0]
        tokens = slug.split("-")
        if len(tokens) >= 2:
            candidate = tokens[-2]
            if candidate and candidate.isalpha():
                return candidate.capitalize()
        return ""

    @classmethod
    def _detect_remote(cls, detail_url: str, text: str) -> bool:
        url_lower = detail_url.lower()
        if "-remote-" in url_lower or "/jobs-remote" in url_lower:
            return True
        if any(hint in text for hint in _REMOTE_HINTS):
            return not any(h in text for h in _HYBRID_HINTS)
        return False

    @staticmethod
    def _detect_seniority(title: str) -> str | None:
        lowered = title.lower()
        for level in ("senior", "mid", "junior", "intern"):
            for keyword in _SENIORITY_MAP[level]:
                if keyword in lowered:
                    return level
        return None

    @staticmethod
    def _extract_salary(card: Node) -> tuple[int | None, int | None]:
        node = card.css_first("span.salary span.text-dark")
        if node is None:
            return None, None
        text = html_lib.unescape(node.text(strip=True))
        # "40.000 EUR - 55.000 EUR" or "40000 - 55000" or "40k-55k"
        nums = re.findall(r"(\d[\d.,]*)\s*k?", text)
        parsed: list[int] = []
        for n in nums:
            cleaned = n.replace(".", "").replace(",", "")
            if cleaned.isdigit():
                value = int(cleaned)
                # normalize "40k" style
                if "k" in text.lower() and value < 1000:
                    value *= 1000
                parsed.append(value)
        if len(parsed) >= 2:
            return parsed[0], parsed[1]
        if len(parsed) == 1:
            return parsed[0], None
        return None, None

    @staticmethod
    def _parse_relative_date(card: Node, now: datetime) -> datetime | None:
        node = card.css_first("span.published-date")
        if node is None:
            return None
        text = node.text(strip=True).lower()
        if "today" in text or "hoy" in text:
            return now
        if "yesterday" in text or "ayer" in text:
            return now - timedelta(days=1)
        match = re.search(r"(\d+)\s+(day|days|week|weeks|month|months)", text)
        if match:
            qty = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("day"):
                return now - timedelta(days=qty)
            if unit.startswith("week"):
                return now - timedelta(weeks=qty)
            if unit.startswith("month"):
                return now - timedelta(days=qty * 30)
        return None
