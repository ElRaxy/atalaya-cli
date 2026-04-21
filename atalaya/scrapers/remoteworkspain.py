"""Scraper de RemoteWorkSpain.es (WP Job Board Pro)."""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
from datetime import datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser

from atalaya.models import Offer
from atalaya.scrapers.base import USER_AGENT, BaseScraper, fetch_html

_STACK_KEYWORDS = (
    "react",
    "node",
    "node.js",
    "nodejs",
    "python",
    "mern",
    "typescript",
    "javascript",
    "vue",
    "angular",
    "aws",
    "django",
    "rails",
    "postgres",
    "mongo",
    "kubernetes",
    "docker",
    "nestjs",
    "express",
    "svelte",
    "nextjs",
    "next.js",
    "java",
    "spring",
    "go",
    "golang",
    "php",
    "laravel",
    "ruby",
    "rust",
    "kotlin",
    "swift",
    "flutter",
    "graphql",
    "redis",
    "kafka",
    "terraform",
    "ansible",
)

_SENIORITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "intern": ("intern", "becario", "becaria", "prácticas", "practicas"),
    "junior": ("junior", "jr.", "entry"),
    "senior": ("senior", "sr.", "lead", "principal"),
    "mid": ("mid", "mid-level", "ssr"),
}

_REMOTE_HINTS = (
    "remote",
    "remoto",
    "teletrabajo",
    "telework",
    "work from home",
    "distributed",
)

_HYBRID_HINTS = ("híbrido", "hibrido", "hybrid")


class RemoteWorkSpainScraper(BaseScraper):
    name = "remoteworkspain"
    source_url = "https://remoteworkspain.es/trabajo-en-remoto/"

    async def scrape(self) -> list[Offer]:
        offers: list[Offer] = []
        headers = {"User-Agent": USER_AGENT, "Accept-Language": "es,en;q=0.8"}
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            listing_html = await fetch_html(self.source_url, client)
            urls = self._parse_listing_urls(listing_html)
            seen: set[str] = set()
            for detail_url in urls:
                if detail_url in seen:
                    continue
                seen.add(detail_url)
                try:
                    detail_html = await fetch_html(detail_url, client)
                except httpx.HTTPError:
                    continue
                offer = self._parse_detail(detail_url, detail_html)
                if offer is not None:
                    offers.append(offer)
                await asyncio.sleep(self.rate_limit_s)
        return offers

    @staticmethod
    def _parse_listing_urls(listing_html: str) -> list[str]:
        tree = HTMLParser(listing_html)
        urls: list[str] = []
        for a in tree.css("article.job_listing h2.job-title a"):
            href = a.attributes.get("href") or ""
            if href.startswith("https://remoteworkspain.es/job/"):
                urls.append(href)
        return urls

    @classmethod
    def _parse_detail(cls, url: str, detail_html: str) -> Offer | None:
        tree = HTMLParser(detail_html)
        title_node = tree.css_first("h1.job-detail-title") or tree.css_first("h1")
        if title_node is None:
            return None
        title = html.unescape(title_node.text(strip=True))

        posted_at: datetime | None = None
        description = ""
        company = "RemoteWorkSpain"
        location = ""
        raw_location_node = tree.css_first(".job-location a")
        if raw_location_node is not None:
            location = raw_location_node.text(strip=True)

        ld_data = cls._extract_jobposting_ld(detail_html)
        if ld_data is not None:
            posted_raw = ld_data.get("datePosted")
            if isinstance(posted_raw, str):
                try:
                    posted_at = datetime.fromisoformat(posted_raw)
                except ValueError:
                    posted_at = None
            desc = ld_data.get("description")
            if isinstance(desc, str):
                description = html.unescape(
                    html.unescape(re.sub(r"<[^>]+>", " ", desc))
                ).strip()
            org = ld_data.get("hiringOrganization")
            if isinstance(org, dict):
                org_name = org.get("name")
                if (
                    isinstance(org_name, str)
                    and org_name
                    and "remote work spain" not in org_name.lower()
                ):
                    company = org_name
            job_loc = ld_data.get("jobLocation")
            if isinstance(job_loc, dict):
                addr = job_loc.get("address")
                if isinstance(addr, str) and addr:
                    location = addr
                elif isinstance(addr, dict):
                    for key in ("addressLocality", "addressRegion", "addressCountry"):
                        value = addr.get(key)
                        if isinstance(value, str) and value:
                            location = value
                            break

        combined_text = f"{title}\n{description}".lower()
        remote = cls._detect_remote(combined_text, location)
        seniority = cls._detect_seniority(combined_text)
        stack = cls._extract_stack(combined_text)
        raw_hash = hashlib.sha256(detail_html.encode("utf-8")).hexdigest()[:16]

        return Offer(
            source="remoteworkspain",
            title=title,
            company=company,
            location=location or "Espana",
            remote=remote,
            stack=stack,
            url=url,
            description=description[:4000],
            posted_at=posted_at,
            seniority=seniority,
            raw_html_hash=raw_hash,
        )

    @staticmethod
    def _extract_jobposting_ld(detail_html: str) -> dict[str, Any] | None:
        pattern = re.compile(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.findall(detail_html):
            if "JobPosting" not in match:
                continue
            try:
                data = json.loads(match)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and entry.get("@type") == "JobPosting":
                        return entry
        return None

    @staticmethod
    def _extract_stack(text: str) -> list[str]:
        found: list[str] = []
        for keyword in _STACK_KEYWORDS:
            pattern = r"(?<![a-z0-9+#.])" + re.escape(keyword) + r"(?![a-z0-9+#])"
            if re.search(pattern, text):
                canonical = keyword.replace("node.js", "node").replace("nodejs", "node")
                canonical = canonical.replace("next.js", "nextjs")
                if canonical not in found:
                    found.append(canonical)
        return found

    @staticmethod
    def _detect_remote(text: str, location: str) -> bool:
        loc = (location or "").lower()
        if any(hint in loc for hint in _REMOTE_HINTS):
            return True
        if any(hint in text for hint in _REMOTE_HINTS):
            return not any(h in text for h in _HYBRID_HINTS)
        return False

    @staticmethod
    def _detect_seniority(text: str) -> str | None:
        for level in ("senior", "mid", "junior", "intern"):
            for keyword in _SENIORITY_KEYWORDS[level]:
                if keyword in text:
                    return level
        return None
