"""Scraper de We Work Remotely vía RSS feed.

WWR expone RSS por categoría sin auth ni rate-limit estricto:

- Programming: https://weworkremotely.com/categories/remote-programming-jobs.rss
- Full-stack:  https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss
- Frontend:    https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss
- Backend:     https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss

Cada `<item>` tiene:
- `<title>Company Name: Position Title</title>` (formato típico, a veces con region: "(EU only)")
- `<link>https://weworkremotely.com/remote-jobs/<slug></link>`
- `<guid>https://weworkremotely.com/remote-jobs/<slug></guid>`
- `<pubDate>RFC 822 date</pubDate>`
- `<description>HTML description con tags y location info</description>`
- `<region>` opcional (Europe, Worldwide, USA, etc.)

remote=True siempre (WWR es remote-only).
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Final
from xml.etree import ElementTree as ET

import httpx

from atalaya.models import Offer
from atalaya.scrapers.base import DEFAULT_TIMEOUT, USER_AGENT, BaseScraper

_FEED_URLS: Final = (
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
)

_COMPATIBLE_REGIONS: Final = (
    "worldwide",
    "anywhere",
    "europe",
    "eu",
    "emea",
    "spain",
    "españa",
    "global",
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
)

_SENIORITY_MAP: Final[dict[str, tuple[str, ...]]] = {
    "intern": ("intern", "trainee", "becario"),
    "junior": ("junior", "entry-level", "entry level", "jr."),
    "senior": ("senior", "sr.", "staff", "principal", "lead"),
    "mid": ("mid-level", "mid level", "mid"),
}


class WeWorkRemotelyScraper(BaseScraper):
    """Scraper para weworkremotely.com vía RSS feed de programming categories."""

    name = "weworkremotely"
    source_url = _FEED_URLS[0]

    async def scrape(self) -> list[Offer]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml",
            "Accept-Language": "en,es;q=0.8",
        }
        offers: list[Offer] = []
        seen_urls: set[str] = set()
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            for index, feed_url in enumerate(_FEED_URLS):
                try:
                    response = await client.get(feed_url, timeout=DEFAULT_TIMEOUT)
                    response.raise_for_status()
                    feed_xml = response.text
                except httpx.HTTPError:
                    continue
                for offer in self._parse_feed(feed_xml):
                    if offer.url in seen_urls:
                        continue
                    seen_urls.add(offer.url)
                    offers.append(offer)
                if index < len(_FEED_URLS) - 1:
                    await asyncio.sleep(self.rate_limit_s)
        return offers

    @classmethod
    def _parse_feed(cls, feed_xml: str) -> list[Offer]:
        try:
            root = ET.fromstring(feed_xml)
        except ET.ParseError:
            return []

        items = root.findall(".//item")
        offers: list[Offer] = []
        for item in items:
            title_raw = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title_raw or not link:
                continue
            pub_date = item.findtext("pubDate") or ""
            description = item.findtext("description") or ""
            region_elem = item.findtext("region") or ""

            company, position = cls._split_title(title_raw)
            if not position:
                continue

            location = cls._extract_location(title_raw, region_elem, description)
            if not cls._is_compatible_region(location, description):
                continue

            tags = cls._extract_tags(description)
            stack = cls._extract_stack(position, tags)
            seniority = cls._detect_seniority(position, tags)
            posted_at = cls._parse_date(pub_date)
            description_clean = cls._clean_description(description)
            raw_hash = hashlib.sha256(
                (link + position).encode("utf-8")
            ).hexdigest()[:16]

            offers.append(
                Offer(
                    source="weworkremotely",
                    title=html_lib.unescape(position),
                    company=html_lib.unescape(company or "WWR"),
                    location=location or "Worldwide",
                    remote=True,
                    stack=stack,
                    url=link,
                    description=description_clean,
                    posted_at=posted_at,
                    salary_min=None,
                    salary_max=None,
                    seniority=seniority,
                    raw_html_hash=raw_hash,
                )
            )
        return offers

    @staticmethod
    def _clean_description(raw: str) -> str:
        """Strip HTML, decode entities, collapse whitespace. Cap a 5000 chars."""
        if not raw:
            return ""
        text = re.sub(r"<[^>]+>", " ", raw)
        text = html_lib.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]

    @staticmethod
    def _split_title(title: str) -> tuple[str, str]:
        """Split "Company: Position (region)" into (company, position)."""
        if ":" in title:
            company, _, rest = title.partition(":")
            return company.strip(), rest.strip()
        return "", title.strip()

    @staticmethod
    def _extract_location(title: str, region: str, description: str) -> str:
        for source in (region, title, description):
            low = source.lower()
            for region_name in (
                "spain",
                "españa",
                "emea",
                "europe",
                "eu only",
                "europe only",
                "worldwide",
                "anywhere",
                "global",
            ):
                if region_name in low:
                    return region_name.title()
        return ""

    @staticmethod
    def _is_compatible_region(location: str, description: str) -> bool:
        haystack = (location + " " + description).lower()
        if "usa only" in haystack or "us only" in haystack:
            return False
        if "canada only" in haystack:
            return False
        if not location:
            return True
        return any(region in location.lower() for region in _COMPATIBLE_REGIONS)

    @staticmethod
    def _extract_tags(description: str) -> list[str]:
        text = re.sub(r"<[^>]+>", " ", description).lower()
        text = html_lib.unescape(text)
        tags: list[str] = []
        for kw in _STACK_KEYWORDS:
            pattern = r"(?<![a-z0-9+#.])" + re.escape(kw) + r"(?![a-z0-9+#])"
            if re.search(pattern, text) and kw not in tags:
                tags.append(kw)
        return tags

    @staticmethod
    def _extract_stack(position: str, tags: list[str]) -> list[str]:
        found: list[str] = []
        haystack = (position + " " + " ".join(tags)).lower()
        for kw in _STACK_KEYWORDS:
            pattern = r"(?<![a-z0-9+#.])" + re.escape(kw) + r"(?![a-z0-9+#])"
            if re.search(pattern, haystack):
                canonical = kw.replace("node.js", "node").replace("nodejs", "node")
                canonical = canonical.replace("next.js", "nextjs")
                if canonical not in found:
                    found.append(canonical)
        return found

    @staticmethod
    def _detect_seniority(position: str, tags: list[str]) -> str | None:
        haystack = (position + " " + " ".join(tags)).lower()
        for level in ("senior", "mid", "junior", "intern"):
            for kw in _SENIORITY_MAP[level]:
                if kw in haystack:
                    return level
        return None

    @staticmethod
    def _parse_date(pub_date: str) -> datetime | None:
        if not pub_date:
            return None
        try:
            return parsedate_to_datetime(pub_date)
        except (TypeError, ValueError):
            return None
