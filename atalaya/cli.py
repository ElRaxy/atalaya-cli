"""CLI principal de Atalaya (binary `bhound`)."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from atalaya import __version__
from atalaya.appliers import ApplyStatus, EmailApplier, RateLimiter
from atalaya.config import (
    get_config_path,
    get_db_path,
    get_profile_path,
    load_profile,
    save_profile,
)
from atalaya.generators import (
    ConfigError,
    generate_cv_variant,
    generate_letter,
    load_base_cv,
)
from atalaya.models import Application, ApplicationStatus, Offer, ScoreBreakdown
from atalaya.profile import default_profile
from atalaya.scoring import score_offer
from atalaya.scrapers import SCRAPERS
from atalaya.storage import (
    get_offer,
    init_db,
    list_offers,
    record_run,
    save_application,
    upsert_offer,
)

app = typer.Typer(
    name="bhound",
    help="Atalaya - tu vigia de ofertas dev remoto.",
    no_args_is_help=True,
)
console = Console()


def _configure_logging() -> None:
    """Configura logging basico a stderr si el usuario no lo hizo ya."""
    root = logging.getLogger("atalaya")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)


_configure_logging()


@app.command()
def version() -> None:
    """Print Atalaya version."""
    console.print(f"Atalaya [bold]v{__version__}[/bold] - binary [cyan]bhound[/cyan]")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Sobrescribir profile.toml existente."),
) -> None:
    """Inicializa directorios, profile.toml y base de datos SQLite."""
    cfg_path = get_config_path()
    profile_path = get_profile_path()
    db_path = get_db_path()

    if not profile_path.exists() or force:
        save_profile(default_profile())
        console.print(f"[green]OK[/green] profile.toml -> {profile_path}")
    else:
        console.print(f"[yellow]skip[/yellow] profile.toml ya existe ({profile_path})")

    init_db()
    console.print(f"[green]OK[/green] db SQLite -> {db_path}")
    console.print(f"[dim]config dir: {cfg_path.parent}[/dim]")


async def _run_scraper(
    board: str,
) -> tuple[str, list[Offer] | None, Exception | None]:
    scraper_cls = SCRAPERS[board]
    scraper = scraper_cls()
    try:
        offers = await scraper.scrape()
        return board, offers, None
    except Exception as exc:
        return board, None, exc


async def _run_scrapers_parallel(
    boards: list[str],
) -> dict[str, tuple[list[Offer] | None, Exception | None]]:
    results = await asyncio.gather(*[_run_scraper(b) for b in boards])
    return {board: (offers, err) for board, offers, err in results}


@app.command()
def search(
    board: str = typer.Option(
        "remoteworkspain",
        "--board",
        help="Job board a scrapear. Usa 'all' para correrlos todos en paralelo.",
    ),
    limit: int = typer.Option(20, "--limit", help="Maximo ofertas a procesar tras scrape."),
    remote_only: bool = typer.Option(False, "--remote-only", help="Solo ofertas remotas."),
) -> None:
    """Scrapea un job board (o todos con --board all), puntua y persiste."""
    if board == "all":
        boards = sorted(SCRAPERS.keys())
    elif board in SCRAPERS:
        boards = [board]
    else:
        available = ", ".join([*sorted(SCRAPERS.keys()), "all"])
        console.print(f"[red]ERROR[/red] board desconocido '{board}'. Disponibles: {available}")
        raise typer.Exit(code=2)

    profile = load_profile()

    for b in boards:
        cls = SCRAPERS[b]
        console.print(f"[cyan]scraping[/cyan] {cls.name} -> {cls.source_url}")

    results = asyncio.run(_run_scrapers_parallel(boards))

    summary_table = Table(title="Resumen por scraper")
    summary_table.add_column("scraper")
    summary_table.add_column("nuevas", justify="right")
    summary_table.add_column("actualizadas", justify="right")
    summary_table.add_column("scraped", justify="right")
    summary_table.add_column("errores", justify="right")

    scored_all: list[tuple[Offer, ScoreBreakdown, bool]] = []
    for b in boards:
        offers_res, err = results[b]
        if err is not None or offers_res is None:
            console.print(f"[red]ERROR[/red] {b}: {err}")
            record_run(source=b, new_count=0, updated_count=0, errors=1)
            summary_table.add_row(b, "0", "0", "0", "1")
            continue

        offers: list[Offer] = offers_res
        if remote_only:
            offers = [o for o in offers if o.remote]
        offers = offers[:limit]

        new_count = 0
        updated_count = 0
        for offer in offers:
            breakdown = score_offer(offer, profile)
            _, created = upsert_offer(offer, score=breakdown)
            if created:
                new_count += 1
            else:
                updated_count += 1
            scored_all.append((offer, breakdown, created))

        record_run(source=b, new_count=new_count, updated_count=updated_count, errors=0)
        summary_table.add_row(
            b, str(new_count), str(updated_count), str(len(offers)), "0"
        )

    console.print(summary_table)

    scored_all.sort(key=lambda x: x[1].total, reverse=True)
    top = scored_all[:5]
    if top:
        table = Table(title="Top 5 ofertas por score (global)")
        table.add_column("score", justify="right")
        table.add_column("source")
        table.add_column("titulo", overflow="fold")
        table.add_column("empresa")
        table.add_column("remote", justify="center")
        for offer, breakdown, _ in top:
            table.add_row(
                str(breakdown.total),
                offer.source,
                offer.title[:80],
                offer.company[:30],
                "si" if offer.remote else "no",
            )
        console.print(table)


@app.command(name="list")
def list_cmd(
    min_score: int = typer.Option(0, "--min-score", help="Score minimo (0-100)."),
    limit: int = typer.Option(20, "--limit", help="Maximo resultados."),
    status: str | None = typer.Option(None, "--status", help="Filtra por estado de candidatura."),
) -> None:
    """Lista ofertas almacenadas ordenadas por score."""
    rows = list_offers(min_score=min_score, limit=limit, status_filter=status)
    if not rows:
        console.print("[yellow]sin resultados[/yellow] (prueba 'bhound search')")
        return
    table = Table(title=f"Ofertas (min_score={min_score}, limit={limit})")
    table.add_column("id", justify="right")
    table.add_column("titulo", overflow="fold")
    table.add_column("empresa")
    table.add_column("score", justify="right")
    table.add_column("remote", justify="center")
    table.add_column("url", overflow="fold")
    for offer, score, _ in rows:
        table.add_row(
            str(offer.id),
            offer.title[:70],
            offer.company[:24],
            str(score) if score is not None else "-",
            "si" if offer.remote else "no",
            offer.url,
        )
    console.print(table)


def _ensure_offer(offer_id: int) -> Offer:
    offer = get_offer(offer_id)
    if offer is None:
        console.print(f"[red]ERROR[/red] offer_id={offer_id} no existe")
        raise typer.Exit(code=2)
    return offer


def _write_optional_out(out: str | None, content: str) -> None:
    if out is None:
        return
    path = Path(out).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    console.print(f"[green]OK[/green] escrito -> {path}")


@app.command()
def letter(
    offer_id: int = typer.Argument(..., help="ID de la oferta en la base de datos."),
    lang: str = typer.Option("es", "--lang", help="Idioma: es | en."),
    tone: str = typer.Option("direct", "--tone", help="Tono: direct | warm."),
    out: str | None = typer.Option(None, "--out", help="Path opcional para guardar la carta."),
) -> None:
    """Genera carta de presentacion tailored para una oferta."""
    if lang not in ("es", "en"):
        console.print(f"[red]ERROR[/red] --lang debe ser 'es' o 'en' (dado: {lang})")
        raise typer.Exit(code=2)
    if tone not in ("direct", "warm"):
        console.print(f"[red]ERROR[/red] --tone debe ser 'direct' o 'warm' (dado: {tone})")
        raise typer.Exit(code=2)

    offer = _ensure_offer(offer_id)
    profile = load_profile()

    try:
        content = generate_letter(offer=offer, profile=profile, lang=lang, tone=tone)  # type: ignore[arg-type]
    except ConfigError as exc:
        console.print(f"[red]ERROR[/red] {exc}")
        raise typer.Exit(code=2) from exc

    application = Application(
        offer_id=offer_id,
        status=ApplicationStatus.DRAFTED,
        letter_md=content,
    )
    save_application(application)

    console.print(f"[green]OK[/green] carta generada para offer #{offer_id} ({offer.title})")
    console.print(Markdown(content))
    _write_optional_out(out, content)


@app.command()
def cv(
    offer_id: int = typer.Argument(..., help="ID de la oferta en la base de datos."),
    lang: str = typer.Option("es", "--lang", help="Idioma: es | en."),
    out: str | None = typer.Option(None, "--out", help="Path opcional para guardar el CV."),
    cv_base: str | None = typer.Option(None, "--cv-base", help="Directorio con cv-{lang}.md."),
) -> None:
    """Genera variante de CV tailored para una oferta."""
    if lang not in ("es", "en"):
        console.print(f"[red]ERROR[/red] --lang debe ser 'es' o 'en' (dado: {lang})")
        raise typer.Exit(code=2)

    offer = _ensure_offer(offer_id)
    profile = load_profile()

    try:
        base_dir = Path(cv_base).expanduser() if cv_base else None
        base_md = load_base_cv(lang, base_dir=base_dir)  # type: ignore[arg-type]
    except FileNotFoundError as exc:
        console.print(f"[red]ERROR[/red] {exc}")
        raise typer.Exit(code=2) from exc

    try:
        content = generate_cv_variant(
            offer=offer,
            profile=profile,
            base_cv_md=base_md,
            lang=lang,  # type: ignore[arg-type]
        )
    except ConfigError as exc:
        console.print(f"[red]ERROR[/red] {exc}")
        raise typer.Exit(code=2) from exc

    application = Application(
        offer_id=offer_id,
        status=ApplicationStatus.DRAFTED,
        cv_variant_md=content,
    )
    save_application(application)

    console.print(f"[green]OK[/green] CV variant generado para offer #{offer_id} ({offer.title})")
    console.print(Markdown(content))
    _write_optional_out(out, content)


def _resolve_apply_status(result_status: ApplyStatus) -> ApplicationStatus:
    """Mapea ApplyStatus → ApplicationStatus persistido."""
    if result_status == ApplyStatus.APPLIED:
        return ApplicationStatus.APPLIED
    return ApplicationStatus.DRAFTED


@app.command()
def apply(
    offer_id: int = typer.Argument(..., help="ID de la oferta en la base de datos."),
    preview: bool = typer.Option(
        False, "--preview", help="Simula sin enviar — útil para verificar target."
    ),
    force: bool = typer.Option(
        False, "--force", help="Ignora rate-limit. Cuidado: riesgo de ban si abusas."
    ),
) -> None:
    """Aplica a una oferta concreta usando el applier disponible (email por defecto)."""
    offer = _ensure_offer(offer_id)
    profile = load_profile()

    # Application: usa letter/cv ya generados si existen, sino vacía.
    application = Application(offer_id=offer_id)
    # Si existe Application previa, recuperar letter_md/cv_variant_md no es trivial
    # (no hay get_application). Pero save_application hace upsert, así que basta
    # con regenerar o aceptar la versión vacía. Para esta versión: no recuperamos —
    # el usuario debe correr `bhound letter <id>` y `bhound cv <id>` antes.

    limiter = RateLimiter()
    if not force and not limiter.acquire():
        wait_s = int(limiter.seconds_until_next())
        console.print(
            f"[yellow]rate-limit[/yellow] espera {wait_s}s antes del próximo apply "
            f"(o usa --force para saltarlo)."
        )
        raise typer.Exit(code=3)

    applier = EmailApplier()
    result = applier.apply(offer, application, profile, preview=preview)

    application = Application(
        offer_id=offer_id,
        status=_resolve_apply_status(result.status),
        letter_md=application.letter_md,
        cv_variant_md=application.cv_variant_md,
        applied_at=(
            datetime.now(UTC) if result.status == ApplyStatus.APPLIED else None
        ),
        notes=f"applier={applier.name} status={result.status.value} | {result.detail}",
    )
    save_application(application)

    color = {
        ApplyStatus.APPLIED: "green",
        ApplyStatus.SKIPPED_PREVIEW: "cyan",
        ApplyStatus.SKIPPED_NO_TARGET: "yellow",
        ApplyStatus.ERROR: "red",
    }.get(result.status, "yellow")
    console.print(
        f"[{color}]{result.status.value}[/{color}] offer #{offer_id} ({offer.title}) "
        f"-> {result.detail}"
    )


@app.command(name="apply-batch")
def apply_batch(
    min_score: int = typer.Option(70, "--min-score", help="Score mínimo (0-100)."),
    limit: int = typer.Option(5, "--limit", help="Máximo de candidaturas en este batch."),
    preview: bool = typer.Option(
        False, "--preview", help="Simula sin enviar — solo lista lo que aplicaría."
    ),
) -> None:
    """Aplica en batch a top N ofertas que cumplan score mínimo. Respeta rate-limit."""
    rows = list_offers(min_score=min_score, limit=limit * 5)
    # Filtra ofertas que aún no aplicamos (status DRAFTED/NEW).
    candidates: list[tuple[Offer, int | None]] = []
    for offer, score, status in rows:
        if status == ApplicationStatus.APPLIED.value:
            continue
        candidates.append((offer, score))
        if len(candidates) >= limit:
            break

    if not candidates:
        console.print("[yellow]sin candidatos[/yellow] (score insuficiente o todas aplicadas)")
        return

    profile = load_profile()
    applier = EmailApplier()
    limiter = RateLimiter()

    table = Table(title=f"Batch apply (preview={preview})")
    table.add_column("id", justify="right")
    table.add_column("title")
    table.add_column("score", justify="right")
    table.add_column("status")
    table.add_column("detail")

    for offer, score in candidates:
        if not preview and not limiter.acquire():
            wait_s = int(limiter.seconds_until_next())
            table.add_row(
                str(offer.id),
                offer.title[:50],
                str(score or "-"),
                "rate-limited",
                f"espera {wait_s}s",
            )
            break

        application = Application(offer_id=offer.id or 0)
        result = applier.apply(offer, application, profile, preview=preview)
        app_status = _resolve_apply_status(result.status)

        save_application(
            Application(
                offer_id=offer.id or 0,
                status=app_status,
                applied_at=(
                    datetime.now(UTC) if result.status == ApplyStatus.APPLIED else None
                ),
                notes=f"applier={applier.name} status={result.status.value} | {result.detail}",
            )
        )

        table.add_row(
            str(offer.id),
            offer.title[:50],
            str(score or "-"),
            result.status.value,
            result.detail[:60],
        )

    console.print(table)


@app.command()
def export(
    fmt: str = typer.Option("csv", "--fmt", help="Formato: csv | json."),
    out: str = typer.Option("atalaya-export", "--out", help="Ruta salida (sin extension)."),
    min_score: int = typer.Option(0, "--min-score", help="Score minimo (0-100)."),
    limit: int = typer.Option(1000, "--limit", help="Maximo ofertas a exportar."),
) -> None:
    """Exporta ofertas con score y estado de candidatura a CSV o JSON."""
    if fmt not in ("csv", "json"):
        console.print(f"[red]ERROR[/red] --fmt debe ser 'csv' o 'json' (dado: {fmt})")
        raise typer.Exit(code=2)

    rows = list_offers(min_score=min_score, limit=limit)
    if not rows:
        console.print("[yellow]sin ofertas para exportar[/yellow]")
        return

    records: list[dict[str, object]] = []
    for offer, score, status in rows:
        records.append(
            {
                "id": offer.id,
                "source": offer.source,
                "title": offer.title,
                "company": offer.company,
                "location": offer.location,
                "remote": offer.remote,
                "stack": ",".join(offer.stack),
                "url": offer.url,
                "seniority": offer.seniority,
                "score": score if score is not None else "",
                "application_status": status if status is not None else "",
            }
        )

    target = Path(out).expanduser()
    if not target.suffix:
        target = target.with_suffix(f".{fmt}")
    target.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        with target.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
    else:
        target.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    console.print(f"[green]OK[/green] exportadas {len(records)} ofertas -> {target}")


if __name__ == "__main__":
    app()
