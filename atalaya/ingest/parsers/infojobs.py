"""Parser de alertas InfoJobs.

InfoJobs envía emails desde `noreply@infojobs.net` con cards HTML que enlazan a
`https://www.infojobs.net/<slug>/of-<id>` (anchor en la oferta detalle).
"""

from __future__ import annotations

import html as html_lib
import re
from typing import ClassVar, Final
from urllib.parse import urlparse, urlunparse

from selectolax.parser import HTMLParser

from atalaya.ingest._heuristics import detect_seniority, detect_stack, is_remote
from atalaya.ingest.base import BaseAlertParser, IngestedOffer, ParsedEmail

_OFFER_HREF: Final = re.compile(
    r"https?://(?:www\.)?infojobs\.net/(?:[^/\s\"]+/){1,4}of-[a-z0-9]+",
    re.IGNORECASE,
)


def _strip_tracking(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


class InfoJobsAlertParser(BaseAlertParser):
    name: ClassVar[str] = "email_infojobs"
    sender_patterns: ClassVar[list[str]] = [
        "noreply@infojobs.net",
        "no-reply@infojobs.net",
        "@infojobs.net",
    ]

    def parse(self, email: ParsedEmail) -> list[IngestedOffer]:
        if not (email.html_body or email.text_body):
            return []
        if email.html_body:
            return self._parse_html(email.html_body)
        return self._parse_text(email.text_body)

    @staticmethod
    def _parse_html(html: str) -> list[IngestedOffer]:
        tree = HTMLParser(html)
        offers: list[IngestedOffer] = []
        seen: set[str] = set()
        for anchor in tree.css("a"):
            href = anchor.attributes.get("href", "") or ""
            match = _OFFER_HREF.match(href)
            if not match:
                continue
            url = _strip_tracking(match.group(0))
            if url in seen:
                continue

            title = html_lib.unescape(anchor.text(strip=True))
            title = re.sub(r"\s+", " ", title).strip()
            if not title or len(title) < 3:
                continue
            if title.lower() in {"ver oferta", "ver detalle", "ver más"}:
                continue
            seen.add(url)

            parent = getattr(anchor, "parent", None)
            block_text = ""
            if parent is not None:
                block_text = html_lib.unescape(parent.text(separator=" ", strip=True))
                block_text = re.sub(r"\s+", " ", block_text)

            company = InfoJobsAlertParser._extract_company(block_text)
            location = InfoJobsAlertParser._extract_location(block_text)
            stack = detect_stack(f"{title} {block_text}")
            seniority = detect_seniority(title)
            remote = is_remote(f"{title} {block_text}")

            offers.append(
                IngestedOffer(
                    title=title[:200],
                    company=company or "InfoJobs (sin empresa)",
                    url=url,
                    location=location or "España",
                    remote=remote,
                    stack=stack,
                    seniority=seniority,
                    description="",
                )
            )
        return offers

    @staticmethod
    def _extract_company(text: str) -> str:
        match = re.search(r"\bEmpresa[:\s]+([^|·\n]{2,60})", text)
        if match:
            return match.group(1).strip(" .,")
        return ""

    @staticmethod
    def _extract_location(text: str) -> str:
        match = re.search(
            r"\b(?:Provincia|Localidad|Ubicación)[:\s]+([^|·\n]{2,60})", text
        )
        if match:
            return match.group(1).strip(" .,")
        return ""

    @staticmethod
    def _parse_text(text: str) -> list[IngestedOffer]:
        offers: list[IngestedOffer] = []
        seen: set[str] = set()
        for match in _OFFER_HREF.finditer(text):
            url = _strip_tracking(match.group(0))
            if url in seen:
                continue
            seen.add(url)
            offers.append(
                IngestedOffer(
                    title="InfoJobs offer",
                    company="InfoJobs (sin empresa)",
                    url=url,
                    location="España",
                    remote=False,
                )
            )
        return offers
