"""Parser de alertas LinkedIn Jobs.

LinkedIn envía emails desde `jobs-noreply@linkedin.com` / `jobalerts-noreply@linkedin.com`.
Los emails HTML contienen cards con enlaces a `https://www.linkedin.com/comm/jobs/view/<id>?...`.
El título del puesto suele estar como texto del propio `<a>` o en `<strong>` cercano.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import ClassVar, Final
from urllib.parse import urlparse, urlunparse

from selectolax.parser import HTMLParser

from atalaya.ingest._heuristics import detect_seniority, detect_stack, is_remote
from atalaya.ingest.base import BaseAlertParser, IngestedOffer, ParsedEmail

_JOB_HREF: Final = re.compile(
    r"https?://[a-z0-9.]*linkedin\.com/(?:comm/)?jobs/view/(\d+)",
    re.IGNORECASE,
)


def _canonical_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{job_id}"


def _clean_title(raw: str) -> str:
    text = html_lib.unescape(raw or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:300]


def _strip_tracking_params(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


class LinkedInAlertParser(BaseAlertParser):
    name: ClassVar[str] = "email_linkedin"
    sender_patterns: ClassVar[list[str]] = [
        "jobs-noreply@linkedin.com",
        "jobalerts-noreply@linkedin.com",
        "@linkedin.com",
    ]

    def parse(self, email: ParsedEmail) -> list[IngestedOffer]:
        body = email.html_body or email.text_body
        if not body:
            return []
        if email.html_body:
            offers = self._parse_html(email.html_body)
        else:
            offers = self._parse_text(email.text_body)
        return self._dedupe(offers)

    @staticmethod
    def _parse_html(html: str) -> list[IngestedOffer]:
        tree = HTMLParser(html)
        offers: list[IngestedOffer] = []
        seen: set[str] = set()
        for anchor in tree.css("a"):
            href = anchor.attributes.get("href", "") or ""
            match = _JOB_HREF.search(href)
            if not match:
                continue
            job_id = match.group(1)
            url = _canonical_url(job_id)
            if url in seen:
                continue

            title = _clean_title(anchor.text(strip=True))
            if not title or len(title) < 3:
                # Sin título usable: probablemente botón "Ver oferta". Saltar.
                continue
            if title.lower() in {"view job", "ver oferta", "see job"}:
                continue
            seen.add(url)

            # Empresa: buscar siguientes nodos hermanos con clase company-name
            # o el siguiente <a> que no sea una oferta.
            company = LinkedInAlertParser._extract_company_near(anchor)
            location = LinkedInAlertParser._extract_location_near(anchor)
            stack = detect_stack(title)
            seniority = detect_seniority(title)
            remote = is_remote(f"{title} {location}")

            offers.append(
                IngestedOffer(
                    title=title,
                    company=company or "LinkedIn (sin empresa)",
                    url=url,
                    location=location or "Spain",
                    remote=remote,
                    stack=stack,
                    seniority=seniority,
                    description="",
                )
            )
        return offers

    @staticmethod
    def _extract_company_near(anchor: object) -> str:
        """Busca empresa en el padre directo del anchor (mismo card)."""
        node = anchor
        # selectolax Node API: anchor.parent.
        parent = getattr(node, "parent", None)
        if parent is None:
            return ""
        text = html_lib.unescape(parent.text(separator=" ", strip=True))
        text = re.sub(r"\s+", " ", text)
        match = re.search(
            r"\bat\s+([A-Z][^·\n|]{1,60})", text
        )  # "Senior Engineer at Acme · Spain"
        if match:
            return match.group(1).strip(" .,")
        match = re.search(
            r"\ben\s+([A-Z][^·\n|]{1,60})", text
        )  # "Desarrollador en Acme · Madrid"
        if match:
            return match.group(1).strip(" .,")
        return ""

    @staticmethod
    def _extract_location_near(anchor: object) -> str:
        parent = getattr(anchor, "parent", None)
        if parent is None:
            return ""
        text = html_lib.unescape(parent.text(separator=" ", strip=True))
        text = re.sub(r"\s+", " ", text)
        match = re.search(
            r"·\s+([A-ZÁÉÍÓÚÑa-záéíóúñ ,.()-]{2,80}?)(?:\s+\d|\s*$|·)",
            text,
        )
        if match:
            return match.group(1).strip(" .,")
        return ""

    @staticmethod
    def _parse_text(text: str) -> list[IngestedOffer]:
        offers: list[IngestedOffer] = []
        seen: set[str] = set()
        for match in _JOB_HREF.finditer(text):
            job_id = match.group(1)
            url = _canonical_url(job_id)
            if url in seen:
                continue
            seen.add(url)
            # En modo texto plano no tenemos title fiable; usar URL como fallback.
            offers.append(
                IngestedOffer(
                    title=f"LinkedIn job {job_id}",
                    company="LinkedIn (sin empresa)",
                    url=url,
                    location="Spain",
                    remote=False,
                    stack=[],
                )
            )
        return offers

    @staticmethod
    def _dedupe(offers: list[IngestedOffer]) -> list[IngestedOffer]:
        seen: set[str] = set()
        out: list[IngestedOffer] = []
        for o in offers:
            canonical = _strip_tracking_params(o.url)
            if canonical in seen:
                continue
            seen.add(canonical)
            out.append(o)
        return out
