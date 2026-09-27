"""Spec 2026-07-28 stempelt `serverInfo` in die Resultate — mit Version.

In der modernen Aera gibt es keinen `initialize`-Handshake mehr, der Name und
Version einmal pro Verbindung uebertraegt. Das SDK legt die Angabe stattdessen
als `_meta`-Eintrag `io.modelcontextprotocol/serverInfo` auf die Resultate. Der
Server gab `MCPServer` keine `version` mit, und auf der Leitung stand
`"version": ""` — eine Luecke, die sich wie eine Angabe liest.

Geprueft an der Antwort einer echten `ClientSession`, nicht am Konstruktor-
Argument: ein Blick auf `mcp.version` waere auch dann gruen, wenn das SDK den
Wert nicht in den Stempel uebernaehme.
"""

from __future__ import annotations

from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types.version import LATEST_MODERN_VERSION

from parlament_mcp import __version__
from parlament_mcp.server import mcp

SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"


async def test_die_moderne_aera_stempelt_die_paketversion() -> None:
    async with Client(mcp, mode=LATEST_MODERN_VERSION) as client:
        result = await client.list_tools()

    stamp = (result.meta or {}).get(SERVER_INFO_KEY)
    assert stamp is not None, f"kein {SERVER_INFO_KEY} auf tools/list"
    assert stamp["name"] == "parlament_mcp"
    assert stamp["version"] == __version__


async def test_der_handshake_meldet_dieselbe_version() -> None:
    """Beide Aeren muessen dasselbe sagen, sonst haengt die gemeldete Version
    davon ab, welcher Client fragt."""
    async with Client(mcp, mode="legacy") as client:
        assert client.server_info is not None
        assert client.server_info.version == __version__


async def test_ohne_argument_bleibt_die_version_leer() -> None:
    """Negativkontrolle: gleiches SDK, kein `version`. Faellt dieser Test, hat
    das SDK einen eigenen Default bekommen — dann pruefen die Tests oben nicht
    mehr, dass wir ihn setzen."""
    async with Client(MCPServer("kontrolle"), mode=LATEST_MODERN_VERSION) as client:
        result = await client.list_tools()

    assert (result.meta or {})[SERVER_INFO_KEY]["version"] == ""
