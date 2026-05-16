"""Applier manual asistido.

Para ofertas que requieren formulario propio (LinkedIn / InfoJobs / Tecnoempleo /
formularios custom de empresas), no podemos automatizar el submit sin riesgo de
ban. El applier manual reduce el coste de cada apply a ~30s:

1. Recupera carta + CV variant persistidos en SQLite.
2. Escribe ambos a `<tmp>/atalaya-apply-<offer_id>/` (markdown).
3. Copia la carta al portapapeles del sistema (best-effort por OS).
4. Abre la URL de la oferta en el navegador por defecto.
5. El usuario pega + adjunta + clica Submit en el form.
6. (Opcional) marca como APPLIED tras confirmación del usuario.

No depende de Playwright ni cookies. No toca cuentas del usuario directamente.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import tempfile
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from atalaya.appliers.base import ApplyResult, ApplyStatus, BaseApplier
from atalaya.models import Application, Offer, Profile

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ManualDossier:
    """Paquete de archivos generado para el apply manual asistido."""

    folder: Path
    letter_path: Path | None
    cv_path: Path | None
    clipboard_copied: bool


def copy_to_clipboard(text: str) -> bool:
    """Best-effort: copia `text` al portapapeles del sistema.

    Devuelve True si parece haber funcionado, False si no hay backend disponible.
    Soporta Windows (`clip`), macOS (`pbcopy`), Linux (`xclip`/`xsel`/`wl-copy`).
    """
    if not text:
        return False
    encoded = text.encode("utf-8")
    system = platform.system()

    if system == "Windows":
        try:
            proc = subprocess.run(
                ["clip"], input=encoded, check=False, capture_output=True
            )
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    if system == "Darwin":
        try:
            proc = subprocess.run(
                ["pbcopy"], input=encoded, check=False, capture_output=True
            )
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    # Linux: probar xclip → xsel → wl-copy
    for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "-bi"], ["wl-copy"]):
        try:
            proc = subprocess.run(
                cmd, input=encoded, check=False, capture_output=True
            )
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False


class ManualApplier(BaseApplier):
    """Applier manual asistido. No envía nada por sí mismo.

    Marca el resultado como `APPLIED` solo si el flag `mark_applied=True` se pasa
    explícitamente (la CLI lo pide al usuario tras confirmar el apply manual).
    """

    name = "manual"

    def __init__(self, mark_applied: bool = False, open_browser: bool = True) -> None:
        self._mark_applied = mark_applied
        self._open_browser = open_browser
        self.last_dossier: ManualDossier | None = None

    def apply(
        self,
        offer: Offer,
        application: Application,
        profile: Profile,
        *,
        preview: bool = False,
    ) -> ApplyResult:
        del profile  # firma de la interfaz; aquí no se usa

        if preview:
            return ApplyResult(
                status=ApplyStatus.SKIPPED_PREVIEW,
                detail=f"would prepare dossier for {offer.url}",
            )

        dossier = self.build_dossier(offer, application)
        self.last_dossier = dossier

        if self._open_browser:
            try:
                webbrowser.open(offer.url, new=2)
            except (webbrowser.Error, OSError) as exc:
                log.warning("no se pudo abrir el navegador: %s", exc)

        if self._mark_applied:
            return ApplyResult(
                status=ApplyStatus.APPLIED,
                detail=f"manual apply marked; dossier in {dossier.folder}",
            )
        return ApplyResult(
            status=ApplyStatus.SKIPPED_PREVIEW,
            detail=f"dossier ready in {dossier.folder} (run again with --mark-applied to record)",
        )

    @staticmethod
    def build_dossier(offer: Offer, application: Application) -> ManualDossier:
        """Escribe carta + CV en un dir temporal y copia carta al clipboard."""
        offer_id = offer.id if offer.id is not None else 0
        folder = Path(tempfile.gettempdir()) / f"atalaya-apply-{offer_id}"
        folder.mkdir(parents=True, exist_ok=True)

        letter_path: Path | None = None
        if application.letter_md:
            letter_path = folder / "letter.md"
            letter_path.write_text(application.letter_md, encoding="utf-8")

        cv_path: Path | None = None
        if application.cv_variant_md:
            cv_path = folder / "cv.md"
            cv_path.write_text(application.cv_variant_md, encoding="utf-8")

        # Pista de la oferta junto al dossier para no perder contexto.
        meta = folder / "offer.txt"
        meta.write_text(
            f"{offer.title}\n{offer.company}\n{offer.location}\n{offer.url}\n",
            encoding="utf-8",
        )

        copied = copy_to_clipboard(application.letter_md or "")
        return ManualDossier(
            folder=folder,
            letter_path=letter_path,
            cv_path=cv_path,
            clipboard_copied=copied,
        )
