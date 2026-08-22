"""Tests del parser de InfoJobs usando fixture HTML."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from atalaya.scrapers.infojobs import InfoJobsScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load_html() -> str:
    return (FIXTURES / "infojobs_sample.html").read_text(encoding="utf-8")


def test_parse_listing_extracts_offers() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "infojobs"
        assert offer.url.startswith("https://www.infojobs.net/")
        assert "/of-i" in offer.url
        assert offer.remote is True


def test_parse_listing_dedupes_urls() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    urls = [o.url for o in offers]
    assert len(urls) == len(set(urls))


def test_parse_listing_extracts_company_from_aria_label() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    companies = {o.company for o in offers}
    assert "Luca TIC" in companies
    assert "Globex Soft" in companies
    assert "Hooli Spain" in companies


def test_parse_listing_detects_seniority() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    senior = next((o for o in offers if "senior" in o.title.lower()), None)
    junior = next((o for o in offers if "junior" in o.title.lower()), None)
    assert senior is not None
    assert senior.seniority == "senior"
    assert junior is not None
    assert junior.seniority == "junior"


def test_parse_listing_extracts_salary() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    senior = next((o for o in offers if "qlik" in o.title.lower()), None)
    assert senior is not None
    assert senior.salary_min == 35000
    assert senior.salary_max == 45000


def test_parse_listing_detects_stack_from_tags() -> None:
    offers = InfoJobsScraper._parse_listing(_load_html())
    fullstack = next((o for o in offers if "fullstack" in o.title.lower()), None)
    assert fullstack is not None
    assert "react" in fullstack.stack
    assert "node" in fullstack.stack
    assert "typescript" in fullstack.stack


def test_parse_listing_handles_empty_html() -> None:
    assert InfoJobsScraper._parse_listing("") == []
    assert InfoJobsScraper._parse_listing("<html></html>") == []


def test_maquetado_2026_08_rellena_fecha_y_descripcion() -> None:
    """Regresion 2026-08-22: las 43 ofertas entraban sin fecha y sin descripcion.

    La fecha se buscaba como "hace 2 dias" y en la tarjeta pone "Hace 2d"; la
    descripcion ni se intentaba (`description=""` a pelo) aunque el `<p>` esta ahi.
    """
    html = (FIXTURES / "infojobs_listing_2026-08.html").read_text(encoding="utf-8")
    offers = InfoJobsScraper._parse_listing(html)

    assert offers, "la fixture del maquetado actual no produjo ninguna oferta"
    assert all(o.posted_at is not None for o in offers), "fecha sin parsear"
    assert all(len(o.description or "") > 50 for o in offers), "descripcion vacia"


def test_los_dos_formatos_de_fecha_del_mismo_span() -> None:
    """InfoJobs cambia de formato segun la antiguedad: "Hace 2d" y "13 jul"."""
    html = (FIXTURES / "infojobs_listing_2026-08.html").read_text(encoding="utf-8")
    offers = InfoJobsScraper._parse_listing(html)
    fechas = [o.posted_at for o in offers if o.posted_at]

    ahora = datetime.now(UTC)
    assert all(f <= ahora for f in fechas), "una fecha en el futuro: el anio se infirio mal"

    # La fixture trae un "13 jul" junto a los "Hace Nd".
    assert any(f.month == 7 and f.day == 13 for f in fechas), "el formato 'dd mes' no se parseo"
    assert any((ahora - f).days <= 3 for f in fechas), "el formato 'Hace Nd' no se parseo"


def test_no_confunde_un_hace_falta_del_cuerpo_con_una_fecha() -> None:
    """El regex generico sobre el texto de la tarjeta cazaba "hace falta"."""
    html = (
        '<li class="ij-OfferList-offerCardItem">'
        '<a class="ij-OfferCardContent-description-link" '
        'href="//www.infojobs.net/madrid/dev/of-iABC" aria-label="Python Developer"></a>'
        '<p class="ij-OfferCardContent-description-description">'
        "Para este puesto hace falta experiencia en Django y en Postgres, "
        "y valoramos mucho el trabajo en equipo dentro de un entorno remoto."
        "</p></li>"
    )
    offers = InfoJobsScraper._parse_listing(html)

    assert len(offers) == 1
    assert offers[0].posted_at is None, "invento una fecha a partir de 'hace falta'"
