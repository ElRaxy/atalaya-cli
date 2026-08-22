"""Email-based applier.

Extrae email de contacto de `offer.description` (regex) y envía SMTP con:
- Subject: re ofertas con título de la oferta.
- Body: cuerpo letter_md en texto plano + markdown.
- Adjuntos: CV variant markdown (si presente).

Config esperada en `<config_dir>/config.toml`:

    [smtp]
    host = "smtp.gmail.com"
    port = 587
    user = "tu@email.com"
    password = "app-password-aqui"  # NUNCA password real — Gmail App Password
    from_name = "Tu Nombre"
    from_email = "tu@email.com"
    starttls = true

Si falta sección [smtp] o password → `ApplyResult(ERROR, "smtp_not_configured")`.

Para Gmail: requiere App Password (no password normal). Setup:
https://myaccount.google.com/apppasswords
"""

from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from atalaya.appliers.base import ApplyResult, ApplyStatus, BaseApplier
from atalaya.config import load_config
from atalaya.models import Application, Offer, Profile

_EMAIL_REGEX = re.compile(
    r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b",
    flags=re.IGNORECASE,
)

# Emails que NO son targets reales (no-reply, generic boards, etc).
_EMAIL_BLOCKLIST_SUBSTRINGS = (
    "no-reply",
    "noreply",
    "donotreply",
    "do-not-reply",
    "info@infojobs",
    "support@",
    "contact@anthropic",
)


class EmailApplier(BaseApplier):
    """Envía la candidatura por email si la oferta expone un email de contacto."""

    name = "email"

    def apply(
        self,
        offer: Offer,
        application: Application,
        profile: Profile,
        *,
        preview: bool = False,
    ) -> ApplyResult:
        target_email = self._extract_target_email(offer)
        if not target_email:
            return ApplyResult(
                status=ApplyStatus.SKIPPED_NO_TARGET,
                detail="no email found in description",
            )

        if preview:
            return ApplyResult(
                status=ApplyStatus.SKIPPED_PREVIEW,
                detail=f"would send to {target_email}",
            )

        smtp_cfg = self._load_smtp_config()
        if smtp_cfg is None:
            return ApplyResult(
                status=ApplyStatus.ERROR,
                detail="smtp_not_configured — añade [smtp] a config.toml",
            )

        try:
            self._send(
                smtp_cfg=smtp_cfg,
                target=target_email,
                offer=offer,
                application=application,
                profile=profile,
            )
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            return ApplyResult(
                status=ApplyStatus.ERROR,
                detail=f"smtp_error: {exc.__class__.__name__}: {exc}",
            )

        return ApplyResult(
            status=ApplyStatus.APPLIED,
            detail=f"email sent to {target_email}",
        )

    @classmethod
    def _extract_target_email(cls, offer: Offer) -> str | None:
        haystack = offer.description or ""
        for match in _EMAIL_REGEX.finditer(haystack):
            candidate = match.group(0).lower()
            if any(blocked in candidate for blocked in _EMAIL_BLOCKLIST_SUBSTRINGS):
                continue
            return candidate
        return None

    @staticmethod
    def _load_smtp_config() -> dict[str, Any] | None:
        cfg = load_config()
        smtp = cfg.get("smtp")
        if not isinstance(smtp, dict):
            return None
        required = ("host", "port", "user", "password", "from_email")
        if not all(smtp.get(k) for k in required):
            return None
        return smtp

    @staticmethod
    def _send(
        smtp_cfg: dict[str, Any],
        target: str,
        offer: Offer,
        application: Application,
        profile: Profile,
    ) -> None:
        msg = EmailMessage()
        from_name = smtp_cfg.get("from_name") or profile.name
        from_email = smtp_cfg["from_email"]
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = target
        msg["Subject"] = f"Candidatura: {offer.title} ({offer.company})"

        body_lines = [
            "Hola,",
            "",
            (
                application.letter_md.strip()
                if application.letter_md
                else f"Me interesa la oferta {offer.title} en {offer.company}. "
                f"Adjunto mi CV para vuestra consideración."
            ),
            "",
            "—",
            from_name,
            from_email,
            offer.url,
        ]
        msg.set_content("\n".join(body_lines))

        if application.cv_variant_md:
            msg.add_attachment(
                application.cv_variant_md.encode("utf-8"),
                maintype="text",
                subtype="markdown",
                filename=f"CV-{profile.name.replace(' ', '_')}.md",
            )

        host = str(smtp_cfg["host"])
        port = int(smtp_cfg["port"])
        user = str(smtp_cfg["user"])
        password = str(smtp_cfg["password"])
        starttls = bool(smtp_cfg.get("starttls", True))

        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            if starttls:
                server.starttls(context=context)
                server.ehlo()
            server.login(user, password)
            server.send_message(msg)
