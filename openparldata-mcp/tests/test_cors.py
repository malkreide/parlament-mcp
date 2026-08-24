"""SDK-004: CORS-Freigabeliste dieses Servers — Header wie Methoden.

Zwei Befunde in derselben Middleware, und der zweite macht den ersten erst
wirksam:

1. **Die Routing-Header der Spec `2026-07-28` fehlten.** `Mcp-Method`,
   `Mcp-Name` und `Mcp-Protocol-Version` tragen seit dieser Revision die
   Wegwahl einer streamable-http-Anfrage. Ein Browser darf einen nicht
   safelisteten Header gar nicht erst senden, wenn der Server ihn nicht nennt —
   **jede** Cross-Origin-Anfrage starb am Preflight, vor dem ersten MCP-Byte.
   Gemessen vorher: `mcp-method` → 400, `mcp-protocol-version` → 400.

2. **`DELETE` fehlte in `allow_methods`.** Ein Browser-Client konnte Sessions
   öffnen, aber nie schliessen.

Punkt 2 allein hätte nichts gebracht: Wer wegen (1) nicht einmal eine Anfrage
durchbringt, kann auch keine Session beenden.

stdio- und Python-Clients kennen keinen Preflight und merkten von beidem
nichts — deshalb fiel es nicht auf, obwohl der Schwester-Server im selben
Repository die Routing-Header längst führte.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from openparldata_mcp.server import (
    CORS_ALLOW_HEADERS,
    CORS_ALLOW_METHODS,
    CORS_ROUTING_HEADERS,
    create_http_app,
)

ORIGIN = "https://client.example"
ENDPOINT = "/mcp"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", ORIGIN)
    monkeypatch.setenv("MCP_BEARER_TOKENS", "test-token-not-a-real-secret")
    return TestClient(create_http_app())


def preflight(client: TestClient, header: str = "content-type", methode: str = "POST"):
    """Ein echter Preflight gegen die zusammengebaute App.

    Header und Methode reiten auf der Anfrage, statt von der Antwort abgelesen
    zu werden: Starlette beantwortet einen Preflight, der etwas nicht
    Freigegebenes nennt, mit **400 und ohne `Access-Control-Allow-Origin`** —
    das ist die Ablehnung, um die es geht.
    """
    return client.options(
        ENDPOINT,
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": methode,
            "Access-Control-Request-Headers": header,
        },
    )


@pytest.mark.parametrize("header", CORS_ALLOW_HEADERS)
def test_jeder_freigegebene_header_passiert_den_preflight(client, header: str) -> None:
    """Einzeln parametrisiert: ein Sammelaufruf bliebe grün, wenn nur einer der
    Header freigegeben wäre und Starlette den Rest durchwinkte."""
    resp = preflight(client, header)
    assert resp.status_code == 200, f"Preflight mit {header} abgewiesen"
    assert header.lower() in resp.headers["access-control-allow-headers"].lower()


def test_ein_nicht_freigegebener_header_wird_abgewiesen(client) -> None:
    """Die Gegenkontrolle: ohne sie wäre der Test darüber auch gegen eine
    Header-Wildcard grün."""
    assert preflight(client, "x-beliebiger-header").status_code == 400


def test_die_liste_nennt_jeden_routing_header_den_das_sdk_liest() -> None:
    """Gegen die SDK-Konstanten gehalten, nicht gegen abgeschriebenen Spec-Text.

    `mcp.shared.inbound` ist das, womit der Server eine Anfrage tatsächlich
    einordnet. Eine Umbenennung dort fällt hier als roter Test auf statt als
    Browser-Client, der ohne sichtbaren Grund nicht mehr verbindet.
    """
    from mcp.shared.inbound import (
        MCP_METHOD_HEADER,
        MCP_NAME_HEADER,
        MCP_PROTOCOL_VERSION_HEADER,
    )

    erlaubt = {h.lower() for h in CORS_ALLOW_HEADERS}
    noetig = {MCP_METHOD_HEADER, MCP_NAME_HEADER, MCP_PROTOCOL_VERSION_HEADER}
    assert noetig <= erlaubt, f"nicht freigegeben: {sorted(noetig - erlaubt)}"
    assert {h.lower() for h in CORS_ROUTING_HEADERS} == noetig


def test_die_liste_nennt_den_wiederaufnahme_header() -> None:
    """`Last-Event-ID` setzt einen abgerissenen SSE-Strom fort. Fehlt er, bricht
    ausschliesslich die Wiederaufnahme nach Paketverlust — unter Last, in
    Produktion, ohne dass ein Test etwas dazu sagt."""
    from mcp.server.streamable_http import LAST_EVENT_ID_HEADER

    assert LAST_EVENT_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_die_liste_nennt_den_session_header() -> None:
    from mcp.server.streamable_http import MCP_SESSION_ID_HEADER

    assert MCP_SESSION_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


@pytest.mark.parametrize("methode", ["GET", "POST", "DELETE"])
def test_jede_freigegebene_methode_passiert_den_preflight(client, methode: str) -> None:
    resp = preflight(client, methode=methode)
    assert resp.status_code == 200, f"Preflight fuer {methode} abgewiesen"
    assert methode.lower() in resp.headers["access-control-allow-methods"].lower()


def test_eine_nicht_freigegebene_methode_wird_abgewiesen(client) -> None:
    """Die Gegenkontrolle zur Methodenliste."""
    assert preflight(client, methode="PATCH").status_code == 400


def test_die_methodenliste_nennt_die_sessionbeendigung() -> None:
    """`DELETE` ist der Grund für diese Liste; die Zusicherung hält ihn fest,
    auch wenn jemand die Liste später umbaut."""
    assert "DELETE" in CORS_ALLOW_METHODS


def test_keine_wildcard_in_den_listen() -> None:
    """Die Regression, die dieser Test abfängt, wäre genau ein Zeichen."""
    assert "*" not in CORS_ALLOW_HEADERS
    assert "*" not in CORS_ALLOW_METHODS


def test_der_preflight_braucht_kein_bearer_token(client) -> None:
    """Reihenfolge-Wächter: Ein Browser sendet auf einem `OPTIONS` niemals
    `Authorization`. Liefe die Auth vor CORS, bekäme jeder Preflight 401 und
    Browser-Clients wären ganz ausgesperrt — mit einem Symptom, das auf die
    falsche Schicht zeigt."""
    resp = preflight(client)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGIN
