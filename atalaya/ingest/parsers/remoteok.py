"""Parser del boletín de RemoteOK (jobs digest)."""

from __future__ import annotations

import html as html_lib
import re
from typing import ClassVar, Final
from urllib.parse import urlparse, urlunparse

from selectolax.parser import HTMLParser

from atalaya.ingest._heuristics import detect_seniority, detect_stack
from atalaya.ingest.base import BaseAlertParser, IngestedOffer, ParsedEmail

_OFFER_HREF: Final = re.compile(
    r"https?://(?:www\.)?remoteok\.com/(?:remote-jobs/)?(\d+)(?:-[a-z0-9-]+)?",
    re.IGNORECASE,
)


def _canonical(job_id: str) -> str:
    return f"https://remoteok.com/remote-jobs/{job_id}"


def _strip_tracking(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


class RemoteOkAlertParser(BaseAlertParser):
    name: ClassVar[str] = "email_remoteok"
    sender_patterns: ClassVar[list[str]] = [
        "jobs@remoteok.com",
        "alerts@remoteok.com",
        "noreply@remoteok.com",
        "@remoteok.com",
        "@remoteok.io",
    ]

    def parse(self, email: ParsedEmail) -> list[IngestedOffer]:
        if email.html_body:
            return self._parse_html(email.html_body)
        if email.text_body:
            return self._parse_text(email.text_body)
        return []

    @staticmethod
    def _parse_html(html: str) -> list[IngestedOffer]:
        tree = HTMLParser(html)
        offers: list[IngestedOffer] = []
        seen: set[str] = set()
        for anchor in tree.css("a"):
            href = anchor.attributes.get("href", "") or ""
            match = _OFFER_HREF.search(href)
            if not match:
                continue
            job_id = match.group(1)
            url = _canonical(job_id)
            if url in seen:
                continue

            title = html_lib.unescape(anchor.text(strip=True))
            title = re.sub(r"\s+", " ", title).strip()
            if not title or len(title) < 3:
                continue
            if title.lower() in {"apply", "view", "view job", "see more"}:
                continue
            seen.add(url)

            parent = getattr(anchor, "parent", None)
            block_text = ""
            if parent is not None:
                block_text = html_lib.unescape(parent.text(separator=" ", strip=True))
                block_text = re.sub(r"\s+", " ", block_text)

            company = RemoteOkAlertParser._extract_company(title, block_text)
            stack = detect_stack(f"{title} {block_text}")
            seniority = detect_seniority(title)

            offers.append(
                IngestedOffer(
                    title=title[:200],
                    company=company or "RemoteOK (sin empresa)",
                    url=url,
                    location="Remote",
                    remote=True,
                    stack=stack,
                    seniority=seniority,
                )
            )
        return offers

    @staticmethod
    def _extract_company(title: str, block: str) -> str:
        # Patrón típico RemoteOK: "<Company> is hiring a <Role>"
        match = re.match(r"([A-Z][A-Za-z0-9& .,'-]{1,50})\s+is\s+hiring", title)
        if match:
            return match.group(1).strip(" .,")
        match = re.search(r"\bat\s+([A-Z][A-Za-z0-9& .,'-]{1,50})", block)
        if match:
            return match.group(1).strip(" .,")
        return ""

    @staticmethod
    def _parse_text(text: str) -> list[IngestedOffer]:
        offers: list[IngestedOffer] = []
        seen: set[str] = set()
        for match in _OFFER_HREF.finditer(text):
            job_id = match.group(1)
            url = _canonical(job_id)
            if url in seen:
                continue
            seen.add(url)
            offers.append(
                IngestedOffer(
                    title=f"RemoteOK job {job_id}",
                    company="RemoteOK (sin empresa)",
                    url=url,
                    location="Remote",
                    remote=True,
                )
            )
        return offers
