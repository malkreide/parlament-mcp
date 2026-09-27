"""Spec 2026-07-28 stempelt `serverInfo` in die Resultate — mit Version.

Ohne Handshake traegt in der modernen Aera der `_meta`-Eintrag
`io.modelcontextprotocol/serverInfo` Name und Version. Der Server gab
`MCPServer` keine `version` mit; auf der Leitung stand `"version": ""`.
Geprueft an der Antwort einer echten Verbindung, nicht am Konstruktor-Argument.
"""

from __future__ import annotations

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types.version import LATEST_MODERN_VERSION

from openparldata_mcp import __version__
from openparldata_mcp.server import mcp

SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"

pytestmark = pytest.mark.usefixtures("offline_lifespan")


async def test_die_moderne_aera_stempelt_die_paketversion() -> None:
    async with Client(mcp, mode=LATEST_MODERN_VERSION) as client:
        result = await client.list_tools()

    stamp = (result.meta or {}).get(SERVER_INFO_KEY)
    assert stamp is not None, f"kein {SERVER_INFO_KEY} auf tools/list"
    assert stamp["name"] == "openparldata_mcp"
    assert stamp["version"] == __version__


async def test_der_handshake_meldet_dieselbe_version() -> None:
    async with Client(mcp, mode="legacy") as client:
        assert client.server_info is not None
        assert client.server_info.version == __version__


def test_die_version_ist_die_des_pakets_und_kein_literal() -> None:
    """Das Literal im `__init__` stand neben dem in `pyproject.toml` und wurde
    von nichts gehalten. Jetzt aus den Paket-Metadaten gelesen."""
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    assert __version__ == declared


async def test_ohne_argument_bleibt_die_version_leer() -> None:
    """Negativkontrolle: gleiches SDK, kein `version`."""
    async with Client(MCPServer("kontrolle"), mode=LATEST_MODERN_VERSION) as client:
        result = await client.list_tools()

    assert (result.meta or {})[SERVER_INFO_KEY]["version"] == ""
