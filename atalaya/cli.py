from __future__ import annotations

import typer
from rich.console import Console

from atalaya import __version__

app = typer.Typer(
    name="bhound",
    help="Atalaya — tu vigía de ofertas dev remoto.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Print Atalaya version."""
    console.print(f"Atalaya [bold]v{__version__}[/bold] · binary [cyan]bhound[/cyan]")


@app.command()
def init() -> None:
    """Initialize Atalaya config and profile."""
    console.print("[yellow]TODO:[/yellow] crear ~/.atalaya/config.toml + profile.toml")


@app.command()
def search(
    remote: bool = typer.Option(True, help="Solo ofertas remotas."),
    stack: str = typer.Option("", help="Filtro stack, ej: mern,react,python."),
    board: str = typer.Option("all", help="Job board: all|remoteworkspain|jobfluent|himalayas."),
) -> None:
    """Scrape job boards and store new offers."""
    console.print(f"[yellow]TODO:[/yellow] search remote={remote} stack={stack} board={board}")


@app.command(name="list")
def list_offers(
    min_score: int = typer.Option(0, "--min-score", help="Score mínimo (0-100)."),
    limit: int = typer.Option(20, help="Máximo resultados."),
) -> None:
    """List stored offers, optionally filtered by score."""
    console.print(f"[yellow]TODO:[/yellow] list min_score={min_score} limit={limit}")


@app.command()
def letter(offer_id: str) -> None:
    """Generate tailored cover letter for an offer."""
    console.print(f"[yellow]TODO:[/yellow] letter offer_id={offer_id}")


@app.command()
def cv(offer_id: str) -> None:
    """Generate tailored CV variant for an offer."""
    console.print(f"[yellow]TODO:[/yellow] cv offer_id={offer_id}")


@app.command()
def export(
    fmt: str = typer.Option("csv", help="Formato: csv|json."),
    out: str = typer.Option("atalaya-export", help="Ruta salida (sin extensión)."),
) -> None:
    """Export offers to CSV or JSON."""
    console.print(f"[yellow]TODO:[/yellow] export fmt={fmt} out={out}")


if __name__ == "__main__":
    app()
