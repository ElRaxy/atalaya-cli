"""Tests del parser HTML de Tecnoempleo usando fixture estática."""

from __future__ import annotations

from pathlib import Path

from atalaya.scrapers.tecnoempleo import TecnoempleoScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load_html() -> str:
    return (FIXTURES / "tecnoempleo_sample.html").read_text(encoding="utf-8")


def test_parse_listing_extracts_offers() -> None:
    offers = TecnoempleoScraper._parse_listing(_load_html())
    assert len(offers) >= 2
    for offer in offers:
        assert offer.source == "tecnoempleo"
        assert offer.url.startswith("https://www.tecnoempleo.com/")
        assert "/rf-" in offer.url
        assert offer.remote is True


def test_parse_listing_dedupes_urls() -> None:
    offers = TecnoempleoScraper._parse_listing(_load_html())
    urls = [o.url for o in offers]
    assert len(urls) == len(set(urls))


def test_parse_listing_detects_stack() -> None:
    offers = TecnoempleoScraper._parse_listing(_load_html())
    python_offer = next(
        (o for o in offers if "python" in o.title.lower()), None
    )
    assert python_offer is not None
    assert "python" in python_offer.stack


def test_parse_listing_detects_seniority() -> None:
    offers = TecnoempleoScraper._parse_listing(_load_html())
    senior_python = next(
        (o for o in offers if "senior" in o.title.lower()), None
    )
    junior_vue = next(
        (o for o in offers if "junior" in o.title.lower()), None
    )
    assert senior_python is not None
    assert senior_python.seniority == "senior"
    assert junior_vue is not None
    assert junior_vue.seniority == "junior"


def test_parse_listing_handles_empty_html() -> None:
    assert TecnoempleoScraper._parse_listing("<html></html>") == []
    assert TecnoempleoScraper._parse_listing("") == []


def test_maquetado_2026_08_rellena_empresa_fecha_y_descripcion() -> None:
    """Regresion 2026-08-22: las 90 ofertas entraban sin un solo campo util.

    `_find_card_root` devolvia el propio anchor del titulo ("selectolax doesn't
    expose parent directly", que es falso), asi que empresa, fecha, salario y
    descripcion se buscaban dentro del `<a>` y salian vacios sin fallar. Ademas
    la empresa enlaza a `/<slug>-trabajo` y no a `/empresas/<slug>`, y la fecha
    viene en dd/mm/aaaa y no como "hace 3 dias".
    """
    html = (FIXTURES / "tecnoempleo_listing_2026-08.html").read_text(encoding="utf-8")
    offers = TecnoempleoScraper._parse_listing(html)

    assert offers, "la fixture del maquetado actual no produjo ninguna oferta"
    assert all(o.company != "Tecnoempleo" for o in offers), "empresa sin extraer"
    assert all(o.posted_at is not None for o in offers), "fecha dd/mm/aaaa sin parsear"
    assert all(len(o.description or "") > 50 for o in offers), "descripcion vacia"


def test_salario_con_el_simbolo_pegado_a_cada_cifra() -> None:
    """El rango viene como "30.000€ - 33.000€ b/a", no como "30.000 - 33.000 €"."""
    html = (FIXTURES / "tecnoempleo_listing_2026-08.html").read_text(encoding="utf-8")
    offers = TecnoempleoScraper._parse_listing(html)
    con_salario = [o for o in offers if o.salary_min is not None]
    assert con_salario, "ninguna oferta con rango salarial reconocido"
    for offer in con_salario:
        assert offer.salary_min is not None and offer.salary_min >= 10000
        assert offer.salary_max is not None and offer.salary_max >= offer.salary_min
