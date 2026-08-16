#!/usr/bin/env python3
"""Die ruff-Version steht je Projekt an genau einer Stelle — und bleibt dort.

Dieses Repo traegt zwei Projekte mit eigenen Gate-Saetzen: den Bundes-Server im
Root und `openparldata-mcp/`. Beide deklarierten `ruff>=0.4.0`, und beide
CI-Jobs legten mit einem eigenen `pip install ruff==0.16.1` nach. Die
CI-Schritte liefen nach dem Install des Extras und gewannen gegen pyproject —
die Werte dort waren wirkungslos, und die CLAUDE.md musste den Unterschied mit
"die Version von Hand setzen" auffangen.

Vier Stellen, jetzt zwei. Dass beide dieselbe Version tragen, ist Teil der
Zusicherung: zwei Gate-Saetze mit verschiedenen ruff-Versionen wuerden
denselben Code unterschiedlich beurteilen.
"""

from __future__ import annotations

import pathlib
import re
import tomllib

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / ".github" / "workflows"
_PYPROJECTS = (_ROOT / "pyproject.toml", _ROOT / "openparldata-mcp" / "pyproject.toml")


def _ruff_specifier(pyproject: pathlib.Path) -> str:
    daten = tomllib.loads(pyproject.read_text())
    specs = daten["project"]["optional-dependencies"]["dev"]
    treffer = [s for s in specs if re.match(r"^ruff\b", s)]
    assert len(treffer) == 1, f"{pyproject}: genau ein ruff-Specifier erwartet, gefunden {treffer}"
    return treffer[0]


def test_beide_projekte_pinnen_ruff_exakt() -> None:
    """Eine Spanne laesst lokalen Lauf und CI verschiedene Versionen fahren."""
    for pyproject in _PYPROJECTS:
        spec = _ruff_specifier(pyproject)
        assert re.fullmatch(r"ruff==\d+\.\d+\.\d+", spec), (
            f"{pyproject.relative_to(_ROOT)}: ruff muss als ruff==X.Y.Z gepinnt sein, "
            f"gefunden {spec!r}. Eine Spanne laesst lokal und in der CI verschiedene "
            "Versionen laufen."
        )


def test_beide_projekte_pinnen_dieselbe_version() -> None:
    """Zwei Gate-Saetze mit verschiedenen ruff-Versionen beurteilen Code ungleich."""
    specs = {p: _ruff_specifier(p) for p in _PYPROJECTS}
    versionen = set(specs.values())
    assert len(versionen) == 1, (
        "Root und openparldata-mcp pinnen verschiedene ruff-Versionen: "
        + ", ".join(f"{p.relative_to(_ROOT)} -> {s}" for p, s in specs.items())
    )


def test_die_pins_sind_die_einzige_versionsquelle() -> None:
    """Kein Workflow darf ruff selbst installieren.

    Ein solcher Schritt laeuft nach dem Install des Extras und ueberstimmt den
    Pin — die Zahl in pyproject waere dann Dekoration.
    """
    for workflow in sorted(_WORKFLOWS.glob("*.yml")):
        # Kommentare ausgenommen: die in ci.yml zitieren den entfernten Schritt,
        # um zu erklaeren, warum er nicht zurueckkommen soll.
        zeilen = [z for z in workflow.read_text().splitlines() if not z.lstrip().startswith("#")]
        treffer = [z.strip() for z in zeilen if re.search(r"pip install\s+ruff", z)]
        assert not treffer, (
            f"{workflow.name} installiert ruff direkt ({treffer}). Dieser Schritt "
            "laeuft nach dem [dev]-Install und ueberstimmt den Pin in pyproject."
        )


def test_der_scan_findet_ueberhaupt_etwas() -> None:
    """Sichert die Pruefungen oben gegen leere Eingaben ab.

    Faende der Workflow-Glob nichts, waere die Schleife leer und die Zusicherung
    trivialerweise wahr — gruen, ohne irgendetwas geprueft zu haben.
    """
    workflows = list(_WORKFLOWS.glob("*.yml"))
    assert len(workflows) >= 2, f"Workflow-Scan findet fast nichts: {workflows}"
    assert any("ruff check" in w.read_text() for w in workflows), (
        "kein Workflow ruft ruff auf — der Scan sucht am falschen Ort"
    )
    for pyproject in _PYPROJECTS:
        assert pyproject.exists(), f"{pyproject} fehlt — die Pin-Pruefung liefe ins Leere"
