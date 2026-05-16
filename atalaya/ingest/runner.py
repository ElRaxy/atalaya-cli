"""Coordina fetch IMAP → parse → upsert ofertas → marca email_seen."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from atalaya.ingest.base import IngestedOffer, ParsedEmail
from atalaya.ingest.imap_client import IMAPClient, IMAPConfig
from atalaya.ingest.parsers.infojobs import InfoJobsAlertParser
from atalaya.ingest.parsers.linkedin import LinkedInAlertParser
from atalaya.ingest.parsers.remoteok import RemoteOkAlertParser
from atalaya.ingest.parsers.tecnoempleo import TecnoempleoAlertParser
from atalaya.models import Offer, Profile
from atalaya.scoring import score_offer
from atalaya.storage import is_email_seen, mark_email_seen, upsert_offer

log = logging.getLogger(__name__)


_PARSERS = [
    LinkedInAlertParser(),
    InfoJobsAlertParser(),
    TecnoempleoAlertParser(),
    RemoteOkAlertParser(),
]


@dataclass(slots=True)
class IngestResult:
    emails_scanned: int
    emails_skipped: int
    emails_with_parser: int
    offers_inserted: int
    offers_updated: int
    by_parser: dict[str, int]


def _offer_from_ingested(ingested: IngestedOffer, source_name: str) -> Offer:
    raw_hash = hashlib.sha256(
        (ingested.url + ingested.title).encode("utf-8")
    ).hexdigest()[:16]
    return Offer(
        source=source_name,
        title=ingested.title,
        company=ingested.company,
        location=ingested.location or "Remote",
        remote=ingested.remote,
        stack=ingested.stack,
        url=ingested.url,
        description=ingested.description,
        posted_at=ingested.posted_at,
        salary_min=ingested.salary_min,
        salary_max=ingested.salary_max,
        seniority=ingested.seniority,
        raw_html_hash=raw_hash,
    )


def process_email(
    email: ParsedEmail,
    profile: Profile,
    db_path: Path | None = None,
) -> tuple[int, int, str | None]:
    """Procesa UN email. Devuelve (inserted, updated, parser_name|None)."""
    parser = next((p for p in _PARSERS if p.matches(email.sender)), None)
    if parser is None:
        return 0, 0, None
    ingested = parser.parse(email)
    inserted = 0
    updated = 0
    for off in ingested:
        try:
            offer = _offer_from_ingested(off, parser.name)
        except Exception as exc:  # pragma: no cover — validación Pydantic
            log.warning("ingested-offer inválida: %s", exc)
            continue
        breakdown = score_offer(offer, profile)
        _, created = upsert_offer(offer, score=breakdown, db_path=db_path)
        if created:
            inserted += 1
        else:
            updated += 1
    return inserted, updated, parser.name


def ingest(
    config: IMAPConfig,
    profile: Profile,
    folder: str = "INBOX",
    since_days: int = 7,
    limit: int = 200,
    db_path: Path | None = None,
) -> IngestResult:
    """Fetch IMAP + procesa emails nuevos. Idempotente vía email_seen."""
    client = IMAPClient(config)
    senders = [pat for parser in _PARSERS for pat in parser.sender_patterns]
    emails = client.fetch_recent(
        folder=folder,
        since_days=since_days,
        senders_filter=senders,
        limit=limit,
    )

    scanned = 0
    skipped = 0
    matched = 0
    total_inserted = 0
    total_updated = 0
    by_parser: dict[str, int] = {}

    for parsed_email in emails:
        scanned += 1
        if parsed_email.message_id and is_email_seen(
            parsed_email.message_id, db_path=db_path
        ):
            skipped += 1
            continue
        inserted, updated, parser_name = process_email(
            parsed_email, profile, db_path=db_path
        )
        if parser_name is None:
            skipped += 1
            continue
        matched += 1
        total_inserted += inserted
        total_updated += updated
        by_parser[parser_name] = (
            by_parser.get(parser_name, 0) + inserted + updated
        )
        mark_email_seen(
            message_id=parsed_email.message_id,
            folder=parsed_email.folder,
            sender=parsed_email.sender,
            offers_count=inserted + updated,
            db_path=db_path,
        )

    return IngestResult(
        emails_scanned=scanned,
        emails_skipped=skipped,
        emails_with_parser=matched,
        offers_inserted=total_inserted,
        offers_updated=total_updated,
        by_parser=by_parser,
    )


def load_imap_config(config: dict[str, object]) -> IMAPConfig | None:
    """Construye IMAPConfig desde el dict de config.toml. None si falta sección."""
    imap = config.get("imap")
    if not isinstance(imap, dict):
        return None
    required = ("host", "port", "user", "password")
    if not all(k in imap and imap[k] for k in required):
        return None
    return IMAPConfig(
        host=str(imap["host"]),
        port=int(str(imap["port"])),
        user=str(imap["user"]),
        password=str(imap["password"]),
        use_ssl=bool(imap.get("use_ssl", True)),
    )
