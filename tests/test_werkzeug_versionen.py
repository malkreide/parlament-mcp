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

# Formen, in denen ein Schritt ein Paket eigenstaendig installiert. Die erste
# Fassung dieses Tests kannte nur `pip install ruff` und liess damit
# `pip install --upgrade ruff==…`, `pip install "ruff==…"`, `pip3 install`,
# `uv tool install` und `uv run --with ruff==…` durch — allesamt Formen, die
# den Pin genauso ueberstimmen. Aufgefallen ist das in einem Codex-Review.
_INSTALL_FORM = re.compile(
    r"(?:pip3?\s+install|python\s+-m\s+pip\s+install|uv\s+pip\s+install"
    r"|uv\s+tool\s+install|uv\s+add|pipx\s+install|--with)\b"
)
# ruff als eigenes Paket-Argument. Anfuehrungszeichen sind erlaubt, ein
# vorangehendes Wort-, Pfad- oder Bindestrich-Zeichen nicht: sonst zaehlten
# `ruff-lsp` und `scripts/ruff_helper.py` mit.
_RUFF_PAKET = re.compile(r"""(?<![\w./-])["']?ruff(?![\w-])""")


def _installiert_ruff(zeile: str) -> bool:
    """Installiert diese Zeile ruff als benanntes Paket?

    `pip install -e ".[dev]"` zieht ruff ebenfalls herein — das ist aber der
    richtige Weg und darf nicht anschlagen. Entscheidend ist deshalb, ob nach
    dem Install-Befehl ein eigenes Argument `ruff` steht.
    """
    treffer = _INSTALL_FORM.search(zeile)
    return bool(treffer) and bool(_RUFF_PAKET.search(zeile[treffer.end() :]))


def _workflow_dateien() -> list[pathlib.Path]:
    """Beide Endungen: GitHub laedt `*.yml` UND `*.yaml`."""
    return sorted([*_WORKFLOWS.glob("*.yml"), *_WORKFLOWS.glob("*.yaml")])


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
    for workflow in _workflow_dateien():
        # Kommentare ausgenommen: die in ci.yml zitieren den entfernten Schritt,
        # um zu erklaeren, warum er nicht zurueckkommen soll.
        zeilen = [z for z in workflow.read_text().splitlines() if not z.lstrip().startswith("#")]
        treffer = [z.strip() for z in zeilen if _installiert_ruff(z)]
        assert not treffer, (
            f"{workflow.name} installiert ruff direkt ({treffer}). Dieser Schritt "
            "laeuft nach dem [dev]-Install und ueberstimmt den Pin in pyproject."
        )


def test_der_scan_findet_ueberhaupt_etwas() -> None:
    """Sichert die Pruefungen oben gegen leere Eingaben ab.

    Faende der Workflow-Glob nichts, waere die Schleife leer und die Zusicherung
    trivialerweise wahr — gruen, ohne irgendetwas geprueft zu haben.
    """
    workflows = _workflow_dateien()
    assert len(workflows) >= 2, f"Workflow-Scan findet fast nichts: {workflows}"
    assert any("ruff check" in w.read_text() for w in workflows), (
        "kein Workflow ruft ruff auf — der Scan sucht am falschen Ort"
    )
    for pyproject in _PYPROJECTS:
        assert pyproject.exists(), f"{pyproject} fehlt — die Pin-Pruefung liefe ins Leere"


def test_der_erkenner_kennt_die_gaengigen_installationsformen() -> None:
    """Der Scan ist nur so gut wie das, was er als Install erkennt.

    Ohne diese Tabelle ist die Zusicherung oben gruen, weil sie die Form nicht
    kennt — nicht, weil sie fehlt. Genau so war es: Die erste Fassung suchte
    woertlich nach `pip install ruff` und uebersah fuenf von sieben geprueften
    Schreibweisen.
    """
    muss_treffen = [
        "run: pip install ruff==0.16.1",
        "run: pip install --upgrade ruff==0.16.1",
        'run: pip install "ruff==0.16.1"',
        "run: pip install 'ruff==0.16.1'",
        "run: pip3 install ruff==0.16.1",
        "run: python -m pip install ruff==0.16.1",
        "run: uv pip install ruff==0.16.1 --system",
        "run: uv tool install ruff==0.16.1",
        "run: uv add ruff==0.16.1",
        "run: pipx install ruff==0.16.1",
        "run: uv run --with ruff==0.16.1 ruff check src/",
        "run: pip install ruff",
        "run: pip install pytest ruff==0.16.1",
        "run: pip install ruff[extra]==0.16.1",
    ]
    darf_nicht_treffen = [
        'run: pip install -e ".[dev]"',
        'run: uv pip install -e ".[dev]" --system',
        "run: ruff check src/ tests/ scripts/",
        "run: ruff format --check src/ tests/",
        "run: pip install ruff-lsp",
        "run: pip install uv",
        "run: python -m pip install --upgrade pip",
        "run: pip install build hatchling",
        "run: uv run --with pip-audit pip-audit",
        "run: python scripts/ruff_helper.py",
        "run: pip install -r requirements.txt",
        "name: Lint mit ruff",
    ]
    uebersehen = [z for z in muss_treffen if not _installiert_ruff(z)]
    assert not uebersehen, f"Erkenner uebersieht: {uebersehen}"
    fehlalarm = [z for z in darf_nicht_treffen if _installiert_ruff(z)]
    assert not fehlalarm, f"Erkenner schlaegt faelschlich an: {fehlalarm}"
