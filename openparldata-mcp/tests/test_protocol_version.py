"""Die beiden Spec-Revisionen, gegen die dieser Server geprueft ist.

`mcp` 2.x bedient ZWEI Protokoll-Aeren ueber denselben Server; die erste
Anfrage einer Verbindung entscheidet, welche gilt:

* die **Legacy-Aera** mit `initialize`-Handshake, gedeckelt bei
  `LATEST_HANDSHAKE_VERSION` — was heutige Clients sprechen.
* die **Modern-Aera** mit Pro-Request-Envelope, `LATEST_MODERN_VERSION`.

`LATEST_PROTOCOL_VERSION` ist ein Alias auf die MODERNE Version; wer nur
dagegen pinnt, laesst die Aera frei wandern, in der heutige Clients sprechen.
Beide stehen deshalb getrennt hier — dieselbe Aufteilung wie im Bundes-Server
(`tests/test_protocol_version.py` in der Wurzel).

Zu den Konstanten kommt die Messung: je Aera eine echte `Client`-Verbindung
gegen den registrierten Server, die Revision von der Verbindung abgelesen.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from mcp import Client
from mcp.types.version import (
    LATEST_HANDSHAKE_VERSION,
    LATEST_MODERN_VERSION,
    LATEST_PROTOCOL_VERSION,
)

from openparldata_mcp.server import mcp

PROJECT = pathlib.Path(__file__).resolve().parents[1]

DOCUMENTED_HANDSHAKE_VERSION = "2025-11-25"
DOCUMENTED_MODERN_VERSION = "2026-07-28"

README_SECTIONS = (
    ("README.md", "## MCP protocol version"),
    ("README.de.md", "## MCP-Protokoll-Version"),
)


def test_die_handshake_aera_steht_wo_die_readme_sie_nennt() -> None:
    assert LATEST_HANDSHAKE_VERSION == DOCUMENTED_HANDSHAKE_VERSION, (
        f"das SDK deckelt den Handshake jetzt bei {LATEST_HANDSHAKE_VERSION}, "
        f"die READMEs sagen {DOCUMENTED_HANDSHAKE_VERSION}. Nicht blind "
        "nachziehen: erst das Spec-Changelog lesen, dann READMEs, CHANGELOG und "
        "diese Konstante zusammen bewegen."
    )


def test_die_moderne_aera_steht_wo_die_readme_sie_nennt() -> None:
    assert LATEST_MODERN_VERSION == DOCUMENTED_MODERN_VERSION


def test_latest_protocol_version_ist_der_alias_auf_die_moderne_aera() -> None:
    assert LATEST_PROTOCOL_VERSION == LATEST_MODERN_VERSION
    assert LATEST_PROTOCOL_VERSION != LATEST_HANDSHAKE_VERSION


def test_der_pin_ist_eine_datierte_revision_kein_bewegliches_ziel() -> None:
    for value in (DOCUMENTED_HANDSHAKE_VERSION, DOCUMENTED_MODERN_VERSION):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), value


def test_beide_readmes_nennen_dieselben_beiden_revisionen() -> None:
    """Jede Sprache einzeln: EN und DE laufen sonst auseinander."""
    for name, anchor in README_SECTIONS:
        text = (PROJECT / name).read_text(encoding="utf-8")
        parts = text.split(anchor, 1)
        assert len(parts) > 1, f"{name} hat keinen Abschnitt «{anchor}»"
        body = parts[1][:2500]
        for value in (DOCUMENTED_HANDSHAKE_VERSION, DOCUMENTED_MODERN_VERSION):
            assert value in body, f"{name} nennt {value} nicht im Abschnitt «{anchor}»"


def test_die_geloggte_revision_ist_die_des_sdk_und_kein_literal() -> None:
    """`server_start` loggte `2025-06-18`, waehrend der Server `2025-11-25`
    aushandelte. Verglichen wird mit dem SDK, nicht mit sich selbst."""
    from openparldata_mcp.config import PROTOCOL_VERSION

    assert PROTOCOL_VERSION == LATEST_HANDSHAKE_VERSION


@pytest.mark.usefixtures("offline_lifespan")
async def test_ein_heutiger_client_handelt_die_handshake_revision_aus() -> None:
    async with Client(mcp, mode="legacy") as client:
        assert client.protocol_version == DOCUMENTED_HANDSHAKE_VERSION


@pytest.mark.usefixtures("offline_lifespan")
async def test_ein_moderner_client_erreicht_die_moderne_revision() -> None:
    """`auto` probt `server/discover` und faellt nur bei einem Legacy-Server auf
    den Handshake zurueck — landet dieser Server dort, soll es auffallen."""
    async with Client(mcp, mode="auto") as client:
        assert client.protocol_version == DOCUMENTED_MODERN_VERSION
        tools = await client.list_tools()

    assert len(tools.tools) == 13
