"""Scraper de RemoteOK (https://remoteok.com).

RemoteOK expone una API pública JSON sin auth en `/api`. Devuelve un array donde el primer
elemento es metadata legal (skip) y el resto son ofertas con campos estables:

    {
        "id": "1234567",
        "url": "https://remoteok.com/remote-jobs/...",
        "company": "Acme",
        "position": "Senior Python Developer",
        "tags": ["python", "django", "remote"],
        "location": "Worldwide" | "Europe" | "EMEA" | "Spain",
        "salary_min": 60000,
        "salary_max": 90000,
        "date": "2026-05-15T12:00:00+02:00",
        "description": "<p>HTML...</p>"
    }

Filtramos por tag dev-related y location compatible (worldwide, europe, EMEA, EU, Spain).
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
from datetime import UTC, datetime
from typing import Any, Final

import httpx

from atalaya.models import Offer
from atalaya.scrapers.base import DEFAULT_TIMEOUT, USER_AGENT, BaseScraper

_API_URL: Final = "https://remoteok.com/api"

_DEV_TAG_KEYWORDS: Final = (
    "developer",
    "engineer",
    "engineering",
    "programming",
    "programmer",
    "software",
    "backend",
    "frontend",
    "fullstack",
    "full-stack",
    "full stack",
    "python",
    "javascript",
    "typescript",
    "nodejs",
    "node.js",
    "react",
    "vue",
    "angular",
    "nextjs",
    "next.js",
    "nestjs",
    "ruby",
    "rails",
    "golang",
    "java",
    "spring",
    "laravel",
    "rust",
    "kotlin",
    "flutter",
    "machine learning",
    "data engineer",
    "data scientist",
    "devops",
    "sre",
    "cloud engineer",
    "platform engineer",
    "infrastructure engineer",
    "site reliability",
)

_DEV_TAG_EXACT: Final = frozenset(
    {
        "dev",
        "ai",
        "ml",
        "llm",
        "go",
        "php",
        "swift",
        "node",
        "data",
        "cloud",
    }
)

_COMPATIBLE_LOCATIONS: Final = (
    "worldwide",
    "anywhere",
    "remote",
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


class RemoteOkScraper(BaseScraper):
    """Scraper para remoteok.com vía API JSON pública."""

    name = "remoteok"
    source_url = _API_URL

    async def scrape(self) -> list[Offer]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en,es;q=0.8",
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            try:
                response = await client.get(_API_URL, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, json.JSONDecodeError):
                return []
        return self._parse_payload(payload)

    @classmethod
    def _parse_payload(cls, payload: Any) -> list[Offer]:
        if not isinstance(payload, list):
            return []
        offers: list[Offer] = []
        seen: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            # First element is legal metadata, skip if no 'position' field.
            position = item.get("position") or item.get("title")
            company = item.get("company")
            url = item.get("url")
            if not (position and company and url):
                continue
            if url in seen:
                continue
            seen.add(url)

            tags_raw = item.get("tags") or []
            tags = [str(t).lower() for t in tags_raw if isinstance(t, str | int)]

            if not cls._is_dev_role(str(position), tags):
                continue

            location = str(item.get("location") or "Worldwide")
            if not cls._is_compatible_location(location):
                continue

            posted_at = cls._parse_date(item.get("date"))
            salary_min = cls._safe_int(item.get("salary_min"))
            salary_max = cls._safe_int(item.get("salary_max"))
            title_clean = html_lib.unescape(str(position).strip())
            company_clean = html_lib.unescape(str(company).strip())
            stack = cls._extract_stack(title_clean, tags)
            seniority = cls._detect_seniority(title_clean, tags)
            raw_hash = hashlib.sha256(
                (str(url) + title_clean).encode("utf-8")
            ).hexdigest()[:16]

            offers.append(
                Offer(
                    source="remoteok",
                    title=title_clean,
                    company=company_clean,
                    location=location,
                    remote=True,
                    stack=stack,
                    url=str(url),
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
    def _is_dev_role(position: str, tags: list[str]) -> bool:
        position_low = position.lower()
        tags_low = {t.lower() for t in tags}

        # Substring match on position only — keywords are specific enough.
        for kw in _DEV_TAG_KEYWORDS:
            if kw in position_low:
                return True

        # Exact-token match on tags (short ambiguous tokens like "go", "ai").
        for token in _DEV_TAG_EXACT:
            if token in tags_low:
                return True

        # Also accept any _DEV_TAG_KEYWORDS as an exact tag.
        for kw in _DEV_TAG_KEYWORDS:
            if kw in tags_low:
                return True

        return False

    @staticmethod
    def _is_compatible_location(location: str) -> bool:
        low = location.lower()
        return any(loc in low for loc in _COMPATIBLE_LOCATIONS)

    @staticmethod
    def _parse_date(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, int | float):
            try:
                return datetime.fromtimestamp(float(value), tz=UTC)
            except (ValueError, OSError):
                return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            n = int(value)
            return n if n > 0 else None
        except (TypeError, ValueError):
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
