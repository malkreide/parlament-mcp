"""SEP-2577: keine Log-Benachrichtigungen an den Client.

Spec `2026-07-28` kuendigt die logging-Capability ab. Die Tool-Wrapper
schickten bei jedem Aufruf ein `ctx.info(...)` — gemessen am publizierten
Paket 0.4.0: das SDK warnt dafuer mit `MCPDeprecationWarning`, und ein Client,
der Logmeldungen abonniert, bekam pro Aufruf eine `notifications/message`.
Die Diagnose liegt ohnehin im structlog-Strom auf stderr (`tool_invoked`,
`tool_succeeded`, `tool_failed`) und im OTel-Span je Aufruf.

Geprueft ueber eine echte Verbindung je Aera, mit einem Client, der
ausdruecklich jede Stufe abonniert: kommt trotzdem nichts an, sendet der
Server nichts. Die Negativkontrolle zeigt, dass dieser Aufbau eine gesendete
Meldung auch wirklich saehe.
"""

from __future__ import annotations

import pathlib
import re
import warnings

import httpx
import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import Context, MCPServer
from mcp.shared.exceptions import MCPDeprecationWarning

import parlament_mcp
from parlament_mcp.server import mcp

AUFRUF = ("parlament_search_transcripts", {"params": {"keyword": "Bildung", "limit": 1}})


async def _messen(server: MCPServer, mode: str, name: str, arguments: dict) -> tuple[int, int]:
    """(Logmeldungen beim Client, MCPDeprecationWarnings) fuer einen Aufruf.

    Aufgezeichnet statt in Fehler verwandelt: der Tool-Wrapper faengt jede
    Exception aus dem Logging ab, eine zur Exception gemachte Warnung waere
    also verschluckt worden und der Test gegen den alten Code gruen geblieben.
    """
    empfangen: list = []

    async def mitschreiben(params) -> None:
        empfangen.append(params)

    with warnings.catch_warnings(record=True) as gewarnt:
        warnings.simplefilter("always")
        async with Client(
            server, mode=mode, log_level="debug", logging_callback=mitschreiben
        ) as client:
            ergebnis = await client.call_tool(name, arguments)

    assert not ergebnis.is_error, ergebnis
    veraltet = [w for w in gewarnt if issubclass(w.category, MCPDeprecationWarning)]
    return len(empfangen), len(veraltet)


@pytest.mark.parametrize("mode", ["legacy", "auto"])
async def test_ein_tool_aufruf_sendet_keine_logmeldung(mode: str) -> None:
    """Gemessen vor der Behebung, in beiden Aeren: 2 Meldungen, 6 Warnungen."""
    with respx.mock:
        respx.route().mock(return_value=httpx.Response(200, json={"d": []}))
        meldungen, warnungen = await _messen(mcp, mode, *AUFRUF)

    assert meldungen == 0, f"{mode}: der Server sendete {meldungen} Logmeldung(en)"
    assert warnungen == 0, f"{mode}: {warnungen} MCPDeprecationWarning (SEP-2577)"


@pytest.mark.parametrize("mode", ["legacy", "auto"])
async def test_der_aufbau_saehe_eine_gesendete_meldung(mode: str) -> None:
    """Negativkontrolle: ein Tool, das `ctx.info` ruft. Faellt dieser Test,
    sieht der Aufbau oben nichts mehr — dann waere sein Gruen wertlos."""
    kontrolle = MCPServer("kontrolle")

    @kontrolle.tool()
    async def sprich(ctx: Context) -> str:
        await ctx.info("hallo")
        return "ok"

    meldungen, warnungen = await _messen(kontrolle, mode, "sprich", {})
    assert meldungen == 1
    assert warnungen > 0


def test_kein_client_logging_im_quelltext() -> None:
    """Wache: wer die Aufrufe wieder einfuehrt, stoesst hier darauf."""
    muster = re.compile(r"\bctx\.(debug|info|warning|error|log)\(|send_log_message")
    quelle = pathlib.Path(parlament_mcp.__file__).parent
    treffer = [
        f"{pfad.name}:{nr}"
        for pfad in sorted(quelle.rglob("*.py"))
        for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1)
        if muster.search(zeile)
    ]
    assert not treffer, f"Client-Logging per ctx (SEP-2577): {treffer}"
