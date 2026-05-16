"""Wrapper IMAP minimalista sobre stdlib imaplib + email."""

from __future__ import annotations

import contextlib
import email
import email.utils
import imaplib
import logging
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import Message

from atalaya.ingest.base import ParsedEmail

log = logging.getLogger(__name__)


@dataclass(slots=True)
class IMAPConfig:
    """Config IMAP. App Password recomendado (Gmail/Outlook)."""

    host: str
    port: int
    user: str
    password: str
    use_ssl: bool = True


def _decode_header(raw: str | None) -> str:
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    out = []
    for value, charset in parts:
        if isinstance(value, bytes):
            try:
                out.append(value.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                out.append(value.decode("utf-8", errors="replace"))
        else:
            out.append(value)
    return "".join(out)


def _extract_bodies(msg: Message) -> tuple[str, str]:
    """Devuelve (text_plain, text_html). Cualquiera puede ser ''."""
    text_body = ""
    html_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes):
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                text = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain" and not text_body:
                text_body = text
            elif ctype == "text/html" and not html_body:
                html_body = text
    else:
        ctype = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                text = payload.decode("utf-8", errors="replace")
            if ctype == "text/html":
                html_body = text
            else:
                text_body = text
    return text_body, html_body


def parse_message(raw: bytes, folder: str) -> ParsedEmail:
    """Parsea un email crudo a ParsedEmail. Útil también para tests con .eml."""
    msg = email.message_from_bytes(raw)
    text_body, html_body = _extract_bodies(msg)
    date_hdr = msg.get("Date")
    sent_at: datetime | None = None
    if date_hdr:
        parsed = email.utils.parsedate_to_datetime(date_hdr)
        sent_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return ParsedEmail(
        message_id=(msg.get("Message-ID") or "").strip("<>"),
        sender=_decode_header(msg.get("From")),
        subject=_decode_header(msg.get("Subject")),
        date=sent_at,
        folder=folder,
        text_body=text_body,
        html_body=html_body,
    )


class IMAPClient:
    """Wrapper IMAP. Idempotente con email_seen (no toca flags en servidor)."""

    def __init__(self, config: IMAPConfig) -> None:
        self.config = config

    def fetch_recent(
        self,
        folder: str = "INBOX",
        since_days: int = 7,
        senders_filter: list[str] | None = None,
        limit: int = 200,
    ) -> list[ParsedEmail]:
        """Trae emails desde hace N días. NO marca como leído (Peek)."""
        client: imaplib.IMAP4
        if self.config.use_ssl:
            ctx = ssl.create_default_context()
            client = imaplib.IMAP4_SSL(
                self.config.host, self.config.port, ssl_context=ctx
            )
        else:
            client = imaplib.IMAP4(self.config.host, self.config.port)

        try:
            client.login(self.config.user, self.config.password)
            client.select(folder, readonly=True)

            since = (datetime.now(UTC) - timedelta(days=since_days)).strftime(
                "%d-%b-%Y"
            )
            criteria = [f'(SINCE "{since}")']
            typ, data = client.search(None, *criteria)
            if typ != "OK" or not data or not data[0]:
                return []

            uids = data[0].split()[-limit:]
            results: list[ParsedEmail] = []
            for uid in uids:
                typ, fetched = client.fetch(uid, "(BODY.PEEK[])")
                if typ != "OK" or not fetched:
                    continue
                first = fetched[0]
                if not isinstance(first, tuple) or len(first) < 2:
                    continue
                raw = first[1]
                if not isinstance(raw, bytes):
                    continue
                parsed = parse_message(raw, folder)
                if senders_filter:
                    sl = parsed.sender.lower()
                    if not any(p.lower() in sl for p in senders_filter):
                        continue
                results.append(parsed)
            return results
        finally:
            with contextlib.suppress(imaplib.IMAP4.error):
                client.close()
            client.logout()
