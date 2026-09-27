"""SEP-2549: die auflistenden Methoden muessen einen Frischehinweis tragen.

Spec `2026-07-28` gibt jedem cachebaren Resultat `ttlMs` und `cacheScope`. Das
SDK fuellt keines von beiden — `CacheHint()` defaultet auf `ttl_ms=0`,
`scope="private"`, die Drahtform von «schon veraltet, nie teilen». Gemessen
vor der Behebung: `tools/list` in der Aera `2026-07-28` mit `ttlMs=0` — ueber
streamable-http wie in-process —, waehrend der Bundes-Server im selben
Repository `300000`/`public` meldete.

Geprueft ueber eine echte `Client`-Verbindung statt durch Ruecklesen von
`CACHE_HINTS`: ein Blick ins Dict waere auch dann gruen, wenn das Argument am
Konstruktor verlorenginge.
"""

from __future__ import annotations

import pytest
from mcp import Client
from mcp.server.caching import CACHEABLE_METHODS
from mcp.server.mcpserver import MCPServer
from mcp.types.version import LATEST_MODERN_VERSION

from openparldata_mcp.server import CACHE_HINTS, LIST_CACHE_TTL_MS, mcp

pytestmark = pytest.mark.usefixtures("offline_lifespan")


async def test_die_werkzeugliste_traegt_die_ttl() -> None:
    async with Client(mcp, mode=LATEST_MODERN_VERSION) as client:
        result = await client.list_tools()

    assert result.ttl_ms == LIST_CACHE_TTL_MS, (
        f"tools/list antwortete mit ttlMs={result.ttl_ms}; bei 0 listet jeder Client "
        "bei jeder Verbindung neu auf"
    )
    assert result.cache_scope == "public"


async def test_ein_server_ohne_hinweise_sagt_nichts() -> None:
    """Negativkontrolle: gleiches SDK, gleicher Client, kein `cache_hints`.
    Faengt den Tag ab, an dem das SDK selbst einen Default bekommt — dann
    pruefen die Tests oben nicht mehr, dass wir ihn setzen."""
    async with Client(MCPServer("kontrolle"), mode=LATEST_MODERN_VERSION) as client:
        result = await client.list_tools()

    assert result.ttl_ms == 0
    assert result.cache_scope == "private"


def test_die_ttl_ist_lang_genug_um_etwas_zu_sagen() -> None:
    """Sichert die Richtung einer kuenftigen Aenderung, nicht die Zahl."""
    assert LIST_CACHE_TTL_MS >= 60_000


def test_jede_gehinweiste_methode_ist_nach_spec_cachebar() -> None:
    unknown = sorted(set(CACHE_HINTS) - set(CACHEABLE_METHODS))
    assert not unknown, f"nach Spec 2026-07-28 nicht cachebar: {unknown}"
