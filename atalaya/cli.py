"""CLI principal de Atalaya (binary `bhound`)."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from atalaya import __version__
from atalaya.config import (
    get_config_path,
    get_db_path,
    get_profile_path,
    load_profile,
    save_profile,
)
from atalaya.models import Offer, ScoreBreakdown
from atalaya.profile import default_profile
from atalaya.scoring import score_offer
from atalaya.scrapers import SCRAPERS
from atalaya.storage import get_offer, init_db, list_offers, record_run, upsert_offer

app = typer.Typer(
    name="bhound",
    help="Atalaya - tu vigia de ofertas dev remoto.",
    no_args_is_help=True,
)
console = Console()


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


@app.command()
def search(
    board: str = typer.Option("remoteworkspain", "--board", help="Job board a scrapear."),
    limit: int = typer.Option(20, "--limit", help="Maximo ofertas a procesar tras scrape."),
    remote_only: bool = typer.Option(False, "--remote-only", help="Solo ofertas remotas."),
) -> None:
    """Scrapea un job board, puntua las ofertas y las persiste."""
    if board not in SCRAPERS:
        available = ", ".join(sorted(SCRAPERS.keys()))
        console.print(f"[red]ERROR[/red] board desconocido '{board}'. Disponibles: {available}")
        raise typer.Exit(code=2)

    profile = load_profile()
    scraper_cls = SCRAPERS[board]
    scraper = scraper_cls()
    console.print(f"[cyan]scraping[/cyan] {scraper.source_url}")

    try:
        offers: list[Offer] = asyncio.run(scraper.scrape())
    except Exception as exc:
        console.print(f"[red]ERROR[/red] scrape fallo: {exc}")
        record_run(source=board, new_count=0, updated_count=0, errors=1)
        raise typer.Exit(code=1) from exc

    if remote_only:
        offers = [o for o in offers if o.remote]

    offers = offers[:limit]
    new_count = 0
    updated_count = 0
    scored: list[tuple[Offer, ScoreBreakdown, bool]] = []
    for offer in offers:
        breakdown = score_offer(offer, profile)
        _, created = upsert_offer(offer, score=breakdown)
        if created:
            new_count += 1
        else:
            updated_count += 1
        scored.append((offer, breakdown, created))

    record_run(source=board, new_count=new_count, updated_count=updated_count, errors=0)

    console.print(
        f"[green]done[/green] nuevas={new_count} actualizadas={updated_count} "
        f"total_scraped={len(offers)}"
    )

    scored.sort(key=lambda x: x[1].total, reverse=True)
    top = scored[:5]
    if top:
        table = Table(title="Top 5 ofertas por score")
        table.add_column("score", justify="right")
        table.add_column("titulo", overflow="fold")
        table.add_column("empresa")
        table.add_column("remote", justify="center")
        for offer, breakdown, _ in top:
            table.add_row(
                str(breakdown.total),
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


@app.command()
def letter(offer_id: int) -> None:
    """Genera carta de presentacion tailored (TODO: integracion Claude)."""
    offer = _ensure_offer(offer_id)
    console.print(f"[yellow]TODO[/yellow] letter para offer #{offer.id} - {offer.title}")


@app.command()
def cv(offer_id: int) -> None:
    """Genera variante de CV para una oferta (TODO: integracion Claude)."""
    offer = _ensure_offer(offer_id)
    console.print(f"[yellow]TODO[/yellow] cv para offer #{offer.id} - {offer.title}")


@app.command()
def export(
    fmt: str = typer.Option("csv", "--fmt", help="Formato: csv|json."),
    out: str = typer.Option("atalaya-export", "--out", help="Ruta salida (sin extension)."),
) -> None:
    """Exporta ofertas a CSV o JSON (TODO)."""
    console.print(f"[yellow]TODO[/yellow] export fmt={fmt} out={out}")


if __name__ == "__main__":
    app()
