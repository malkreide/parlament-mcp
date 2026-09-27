"""Angekuendigt wird nur, was der Server auch anbietet.

`MCPServer` registriert die Handler fuer Prompts und Ressourcen immer, und das
SDK leitet die Capabilities aus den Handlern ab. Gemessen vor der Behebung, in
beiden Aeren: `prompts` und `resources` angekuendigt, in `2026-07-28` mit
`subscribe=True` — fuer einen Server, der nur Tools registriert.

Geprueft ueber eine echte Verbindung je Aera: der Handshake traegt die
Capabilities in der `initialize`-Antwort, die moderne Aera in
`server/discover`. Beide Wege fuehren im SDK durch dieselbe Methode, aber ob
das so bleibt, sagt nur die Messung.
"""

from __future__ import annotations

from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types.version import LATEST_MODERN_VERSION

from parlament_mcp.server import advertise_honest_capabilities, mcp


async def test_der_handshake_kuendigt_nur_tools_an() -> None:
    async with Client(mcp, mode="legacy") as client:
        capabilities = client.server_capabilities

    assert capabilities.tools is not None
    assert capabilities.prompts is None
    assert capabilities.resources is None


async def test_die_moderne_aera_kuendigt_nur_tools_an() -> None:
    async with Client(mcp, mode="auto") as client:
        assert client.protocol_version == LATEST_MODERN_VERSION
        capabilities = (await client.session.discover()).capabilities

    assert capabilities.tools is not None
    assert capabilities.tools.list_changed is False, (
        "tools.listChanged verspricht notifications/tools/list_changed; dieser Server sendet keine"
    )
    assert capabilities.prompts is None
    assert capabilities.resources is None


async def test_wer_trotzdem_fragt_bekommt_leere_listen() -> None:
    """Die Handler bleiben: ein Client, der ohne Blick auf die Capabilities
    auflistet, bekommt eine leere Liste und kein «Method not found»."""
    async with Client(mcp, mode="legacy") as client:
        assert (await client.list_prompts()).prompts == []
        assert (await client.list_resources()).resources == []


async def test_eine_registrierung_bringt_die_capability_zurueck() -> None:
    """Die Pruefung laeuft je Aufruf. Wer spaeter einen Prompt oder eine
    Ressource registriert, muss an dieser Stelle nichts nachziehen."""
    server = MCPServer("kontrolle")
    advertise_honest_capabilities(server)

    @server.prompt()
    def gruss() -> str:
        return "Grüezi"

    @server.resource("kontrolle://info")
    def info() -> str:
        return "info"

    async with Client(server, mode="legacy") as client:
        capabilities = client.server_capabilities

    assert capabilities.prompts is not None
    assert capabilities.resources is not None


async def test_ein_template_allein_reicht_fuer_resources() -> None:
    server = MCPServer("kontrolle")
    advertise_honest_capabilities(server)

    @server.resource("kontrolle://eintrag/{key}")
    def eintrag(key: str) -> str:
        return key

    async with Client(server, mode="legacy") as client:
        assert client.server_capabilities.resources is not None


async def test_ohne_die_funktion_kuendigt_das_sdk_beides_an() -> None:
    """Negativkontrolle: gleiches SDK, nichts registriert, keine Uebersteuerung.
    Faellt dieser Test, leitet das SDK selbst ehrlich ab — dann ist die
    Funktion ueberfluessig und gehoert entfernt."""
    async with Client(MCPServer("kontrolle"), mode="legacy") as client:
        capabilities = client.server_capabilities

    assert capabilities.prompts is not None
    assert capabilities.resources is not None


async def test_ein_umgebautes_sdk_faellt_auf_die_eigene_ableitung_zurueck() -> None:
    """Fehlt eine der privaten Stellen, darf das `initialize` nicht brechen."""
    server = MCPServer("kontrolle")
    advertise_honest_capabilities(server)
    del server._prompt_manager

    async with Client(server, mode="legacy") as client:
        capabilities = client.server_capabilities

    assert capabilities.tools is not None
    assert capabilities.prompts is not None


async def test_das_sdk_verspricht_tool_benachrichtigungen_von_sich_aus() -> None:
    """Negativkontrolle zu `tools.listChanged`: gleiches SDK, moderne Aera,
    keine Uebersteuerung. Faellt dieser Test, setzt das SDK das Flag selbst
    ehrlich — dann ist dieser Teil der Funktion ueberfluessig."""
    async with Client(MCPServer("kontrolle"), mode="auto") as client:
        capabilities = (await client.session.discover()).capabilities

    assert capabilities.tools is not None
    assert capabilities.tools.list_changed is True


async def test_das_flag_bleibt_auch_im_fallback_ehrlich() -> None:
    """Fehlen die privaten Manager, faellt nur die Primitive-Pruefung weg.
    `tools.listChanged` haengt an keiner privaten Stelle."""
    server = MCPServer("kontrolle")
    advertise_honest_capabilities(server)
    del server._prompt_manager

    async with Client(server, mode="auto") as client:
        capabilities = (await client.session.discover()).capabilities

    assert capabilities.tools is not None
    assert capabilities.tools.list_changed is False


def test_niemand_aendert_die_tool_liste_zur_laufzeit() -> None:
    """`tools.listChanged=False` ist nur wahr, solange die Liste beim Import
    feststeht. Wer eine dieser Stellen einfuehrt, muss die Uebersteuerung im
    selben Commit zuruecknehmen — dieser Test ist der Ort, an dem es auffaellt."""
    import pathlib
    import re

    import parlament_mcp

    source = pathlib.Path(parlament_mcp.__file__).parent
    pattern = re.compile(
        r"\.(add_tool|remove_tool|notify_tools_changed)\("
        r"|ToolListChanged"
        r'|["\']notifications/tools/list_changed["\']'
    )
    hits = [
        f"{path.name}:{number}"
        for path in sorted(source.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert not hits, f"die Tool-Liste kann sich zur Laufzeit aendern: {hits}"
