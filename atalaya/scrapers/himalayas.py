"""Scraper de Himalayas.app (remote-first job board).

Himalayas es un Next.js SSR. El HTML inicial ya contiene los cards renderizados,
no necesitamos Playwright. Cada card es un `<article>` con clases tailwind; dentro:
- Anchor overlay con `href="/companies/<company>/jobs/<slug>?ref=...&pos=N&src=search"`.
- Titulo en `<a class="relative text-xl font-medium text-gray-900" href="...">Title</a>`.
- Empresa en `<a ... href="/companies/<slug>">Company Name</a>` (dentro del mismo card).
- Fecha relativa en `<time>1 day ago</time>`.
- Tags tipo job-type / category via anchors `/jobs/<tag>` con estilo pill.
- Salario opcional tipo "7k-8k USD" como texto plano dentro del card.

Filtro country=Spain: `https://himalayas.app/jobs?country=Spain`.
Paginacion via `?page=N`. Rate limit 1s. remote=True siempre (Himalayas es remote-first).
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

_BASE_URL: Final = "https://himalayas.app"
_LISTING_URL: Final = f"{_BASE_URL}/jobs?country=Spain"

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
    "intern": ("intern", "trainee", "becario"),
    "junior": ("junior", "entry-level", "entry level", "jr."),
    "senior": ("senior", "sr.", "staff", "principal", "lead"),
    "mid": ("mid-level", "mid level", "mid"),
}


class HimalayasScraper(BaseScraper):
    """Scraper para himalayas.app filtrando por Spain."""

    name = "himalayas"
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
                url = _LISTING_URL if page == 1 else f"{_LISTING_URL}&page={page}"
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
        seen_urls: set[str] = set()
        for article in tree.css("article"):
            title_node = article.css_first("a.text-xl")
            if title_node is None:
                # fallback: first anchor linking to /companies/.../jobs/...
                for anchor in article.css("a"):
                    href = anchor.attributes.get("href") or ""
                    if "/companies/" in href and "/jobs/" in href and anchor.text(strip=True):
                        title_node = anchor
                        break
            if title_node is None:
                continue
            href = title_node.attributes.get("href") or ""
            if "/companies/" not in href or "/jobs/" not in href:
                continue
            clean_href = href.split("?", 1)[0].split("&", 1)[0]
            detail_url = _BASE_URL + clean_href
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            title = html_lib.unescape(title_node.text(strip=True))
            company = cls._extract_company(article, clean_href)
            tags = cls._extract_tags(article)
            posted_at = cls._extract_time(article, now)
            salary_min, salary_max = cls._extract_salary(article)
            stack = cls._extract_stack(title, tags)
            seniority = cls._detect_seniority(title, tags)
            raw_hash = hashlib.sha256(
                (detail_url + title).encode("utf-8")
            ).hexdigest()[:16]

            offers.append(
                Offer(
                    source="himalayas",
                    title=title,
                    company=company or "Himalayas",
                    location="Spain",
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
    def _extract_company(article: Node, job_href: str) -> str:
        # company slug: /companies/<slug>/jobs/<job>
        match = re.match(r"^/companies/([^/]+)/jobs/", job_href)
        company_slug = match.group(1) if match else ""
        for anchor in article.css("a"):
            href = anchor.attributes.get("href") or ""
            if company_slug and href == f"/companies/{company_slug}":
                text: str = html_lib.unescape(anchor.text(strip=True))
                if text:
                    return text
        if company_slug:
            return company_slug.replace("-", " ").title()
        return ""

    @staticmethod
    def _extract_tags(article: Node) -> list[str]:
        tags: list[str] = []
        for anchor in article.css("a"):
            href = anchor.attributes.get("href") or ""
            if href.startswith("/jobs/") and href.count("/") == 2:
                text = html_lib.unescape(anchor.text(strip=True))
                if text and text.lower() not in {t.lower() for t in tags}:
                    tags.append(text)
        return tags

    @staticmethod
    def _extract_time(article: Node, now: datetime) -> datetime | None:
        node = article.css_first("time")
        if node is None:
            return None
        text = node.text(strip=True).lower()
        if "today" in text or "just now" in text or "hour" in text:
            return now
        match = re.search(r"(\d+)\s+(day|days|week|weeks|month|months)\s+ago", text)
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

    @staticmethod
    def _extract_salary(article: Node) -> tuple[int | None, int | None]:
        text: str = article.text()
        # patterns like "7k-8k USD" or "40k-60k USD" or "$60,000-$80,000"
        match = re.search(r"(\d+)\s*k\s*-\s*(\d+)\s*k\b", text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1)) * 1000, int(match.group(2)) * 1000
        match = re.search(
            r"\$\s*(\d[\d,]{3,})\s*-\s*\$?\s*(\d[\d,]{3,})", text
        )
        if match:
            low = int(match.group(1).replace(",", ""))
            high = int(match.group(2).replace(",", ""))
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
