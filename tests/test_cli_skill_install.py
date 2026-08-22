"""Tests de `bhound skill install` con un HOME temporal.

Nunca tocan el HOME real: el comando escribe en ~/.claude y ~/.codex, y un test
que ensucia el entorno de quien lo corre es un test que nadie quiere ejecutar.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from atalaya import cli as cli_module
from atalaya.cli import app

runner = CliRunner()


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fake = tmp_path / "home"
    fake.mkdir()
    monkeypatch.setattr(
        cli_module,
        "_AGENT_SKILL_DIRS",
        {
            "claude": fake / ".claude" / "skills",
            "codex": fake / ".codex" / "skills",
        },
    )
    return fake


def test_instala_donde_el_agente_ya_existe(home: Path) -> None:
    (home / ".claude").mkdir()

    result = runner.invoke(app, ["skill", "install"])

    assert result.exit_code == 0
    assert (home / ".claude" / "skills" / "atalaya" / "SKILL.md").is_file()
    assert (home / ".claude" / "skills" / "atalaya" / "modes" / "barrido.md").is_file()


def test_no_crea_el_directorio_de_un_agente_que_no_esta(home: Path) -> None:
    """Crear ~/.codex a alguien que no usa Codex es ensuciarle el home."""
    (home / ".claude").mkdir()

    runner.invoke(app, ["skill", "install"])

    assert not (home / ".codex").exists()


def test_sin_ningun_agente_avisa_y_sale_con_error(home: Path) -> None:
    result = runner.invoke(app, ["skill", "install"])

    assert result.exit_code == 1
    assert "no AI CLI detected" in result.stdout


def test_no_pisa_una_instalacion_previa_sin_force(home: Path) -> None:
    (home / ".claude").mkdir()
    runner.invoke(app, ["skill", "install"])
    marca = home / ".claude" / "skills" / "atalaya" / "SKILL.md"
    marca.write_text("editado a mano", encoding="utf-8")

    result = runner.invoke(app, ["skill", "install"])

    assert result.exit_code == 0
    assert marca.read_text(encoding="utf-8") == "editado a mano"

    result = runner.invoke(app, ["skill", "install", "--force"])

    assert result.exit_code == 0
    assert marca.read_text(encoding="utf-8") != "editado a mano"


def test_agente_desconocido_es_error_de_uso(home: Path) -> None:
    result = runner.invoke(app, ["skill", "install", "--agent", "vim"])

    assert result.exit_code == 2
    assert "unknown agent" in result.stdout


def test_la_skill_empaquetada_existe_y_tiene_frontmatter() -> None:
    source = cli_module._bundled_skill_dir()

    assert source.is_dir(), "la skill no viaja dentro del paquete"
    contenido = (source / "SKILL.md").read_text(encoding="utf-8")
    assert contenido.startswith("---"), "SKILL.md sin frontmatter: no se descubre"
    assert "name: atalaya" in contenido
