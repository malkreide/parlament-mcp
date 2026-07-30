"""Transport-Härtung und Bind-Weitergabe nach der Migration auf mcp 2.x.

Zwei Dinge an 2.x sind kein reiner Rename, und beide sitzen im HTTP-Pfad:

1. ``mcp.settings`` ist schreibgeschützt. Der 1.x-Weg, Host und Port vor
   ``run()`` über die Settings zu setzen, wirft jetzt ``ValueError`` — der
   Server wäre unter ``MCP_TRANSPORT=streamable-http`` gar nicht gestartet.
   ``run()`` nimmt den Bind stattdessen als kwargs entgegen.

2. ``host`` ist ein App-Argument, aus dem das SDK seine Host-Allow-List
   ableitet, und es defaultet auf ``127.0.0.1``. Ohne Weitergabe aktiviert 2.x
   automatisch ``127.0.0.1:*`` — jede Anfrage unter einem echten Hostnamen
   bekäme HTTP 421, genau auf einem ``MCP_HOST=0.0.0.0``-Deployment.

Die Factory ist dabei der heikle Punkt: uvicorn ruft ein ``--factory`` **ohne
Argumente** auf, ``--host`` konfiguriert also nur den Listener und erreicht die
App nie. Der Bind muss aus der Umgebung kommen.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from openparldata_mcp.server import build_transport_security, create_http_app

_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("MCP_ALLOWED_HOSTS", "MCP_ALLOWED_ORIGINS", "MCP_HOST", "MCP_PORT", "PORT"):
        monkeypatch.delenv(var, raising=False)


# ─────────────────────────── Allow-List-Ableitung ──────────────────────────────
def test_loopback_bind_is_protected():
    sec = build_transport_security("127.0.0.1", 8080)
    assert sec is not None
    assert sec.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8080" in sec.allowed_hosts


def test_wildcard_bind_without_allowlist_stays_off():
    """Auf 0.0.0.0 ist der erreichbare Name unbekannt.

    Der SDK-Loopback-Default ist an dieser Stelle genau eine Vermutung — und
    diese Vermutung *ist* das 421. Lieber sichtbar aus.
    """
    assert build_transport_security("0.0.0.0", 8080) is None


def test_wildcard_bind_with_allowlist_is_protected(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "opd.example.ch")
    sec = build_transport_security("0.0.0.0", 8080)
    assert sec is not None
    assert "opd.example.ch" in sec.allowed_hosts
    # Loopback bleibt drin, sonst brechen Container-Health-Checks.
    assert "127.0.0.1:8080" in sec.allowed_hosts


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_all_loopback_forms_count_as_local(host):
    assert build_transport_security(host, 8080) is not None


def test_configured_cors_origins_pass_the_transport_check(monkeypatch):
    """CORS und Transport-Prüfung müssen sich einig sein.

    Sonst weist der Server genau die Browser-Clients ab, die CORS erlaubt.
    """
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://claude.ai")
    sec = build_transport_security("127.0.0.1", 8080)
    assert "https://claude.ai" in sec.allowed_origins


def test_wildcard_origin_is_not_copied(monkeypatch):
    """``*`` ist als Origin nicht ausdrückbar — literal verglichen erlaubt es
    nichts und macht die Liste unlesbar."""
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "*")
    sec = build_transport_security("127.0.0.1", 8080)
    assert "*" not in sec.allowed_origins


# ─────────────────────────── Die Factory ───────────────────────────────────────
def test_the_factory_reads_the_bind_from_the_environment(monkeypatch):
    """Der Kern des Fixes.

    uvicorn ruft ``--factory`` ohne Argumente auf. Käme der Bind nicht aus der
    Umgebung, sähe die App den Default ``127.0.0.1`` und schaltete eine
    Loopback-Allow-List scharf — das 421.
    """
    import openparldata_mcp.server as srv

    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "9100")
    captured: dict = {}
    real = type(srv.mcp).streamable_http_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(srv.mcp), "streamable_http_app", _spy)
    create_http_app()
    assert captured["host"] == "0.0.0.0"
    # Ohne Allow-List bewusst None: das SDK soll auf einem 0.0.0.0-Bind nichts
    # erzwingen, was es nur raten kann.
    assert captured["transport_security"] is None


def test_the_factory_passes_the_allowlist_through(monkeypatch):
    import openparldata_mcp.server as srv

    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "opd.example.ch")
    captured: dict = {}
    real = type(srv.mcp).streamable_http_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(srv.mcp), "streamable_http_app", _spy)
    create_http_app()
    assert "opd.example.ch" in captured["transport_security"].allowed_hosts


# ─────────────────────────── Durch den echten ASGI-Stack ───────────────────────
def _post_init(app, host_header: str) -> int:
    with TestClient(app, raise_server_exceptions=False) as client:
        return client.post(
            "/mcp", headers={**_HEADERS, "Host": host_header}, json=_INIT
        ).status_code


def test_a_public_bind_without_an_allowlist_is_reachable(monkeypatch):
    """Die Regression selbst — und der Fall, in dem ``host`` wirklich trägt.

    Ist ``transport_security`` gesetzt, benutzt das SDK die übergebene Liste und
    der ``host``-Kwarg ändert nichts. Tragend wird er genau hier: ohne
    Allow-List leitet 2.x seine Prüfung aus ``host`` ab, und der Default
    ``127.0.0.1`` erzeugt das 421 auf einem 0.0.0.0-Bind.
    """
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    assert _post_init(create_http_app(), "opd.example.ch") == 200


def test_an_allowlisted_host_is_admitted(monkeypatch):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "opd.example.ch")
    assert _post_init(create_http_app(), "opd.example.ch") == 200


def test_foreign_host_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "opd.example.ch")
    assert _post_init(create_http_app(), "evil.example.com") == 421


def test_right_host_wrong_port_is_rejected(monkeypatch):
    """Der tragende Fall.

    ``evil.example.com`` allein beweist wenig — eine zurückfallende
    Loopback-Policy würde ihn ebenfalls abweisen. Nur „richtiger Hostname,
    falscher Port" unterscheidet eine portgenaue Allow-List von einer, die
    alles durchlässt.
    """
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "opd.example.ch:8080")
    assert _post_init(create_http_app(), "opd.example.ch:9999") == 421


# ─────────────────────────── Der Bind in main() ────────────────────────────────
def test_settings_are_read_only_in_2x():
    """Warum der 1.x-Weg nicht bloss unschön, sondern tot ist.

    ``mcp.settings.host = …`` war unter 1.x die einzige Möglichkeit. Unter 2.x
    wirft dieselbe Zeile ``ValueError`` — der Server wäre auf HTTP-Transport
    nicht mehr gestartet. Deshalb steht hier ein Test und kein Kommentar.
    """
    import openparldata_mcp.server as srv

    with pytest.raises(ValueError):
        srv.mcp.settings.host = "0.0.0.0"


def test_main_hands_the_bind_to_run(monkeypatch):
    """Der Bind muss als kwarg an ``run()`` — von dort erreicht er die
    Allow-List. Ginge er verloren, liefe der Server auf Loopback statt auf dem
    konfigurierten Interface."""
    import openparldata_mcp.server as srv

    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "9100")
    monkeypatch.setattr("sys.argv", ["openparldata-mcp"])
    captured: dict = {}
    monkeypatch.setattr(type(srv.mcp), "run", lambda self, **kw: captured.update(kw))
    srv.main()
    assert captured == {
        "transport": "streamable-http",
        "host": "0.0.0.0",
        "port": 9100,
    }


def test_stdio_needs_no_bind(monkeypatch):
    """stdio hat keinen Listener — ein Bind wäre dort sinnlos."""
    import openparldata_mcp.server as srv

    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.setattr("sys.argv", ["openparldata-mcp"])
    captured: dict = {}
    monkeypatch.setattr(type(srv.mcp), "run", lambda self, **kw: captured.update(kw))
    srv.main()
    assert captured == {"transport": "stdio"}
