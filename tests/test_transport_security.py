"""Eingehende Host/Origin-Prüfung des Streamable-HTTP-Transports (SEC-005).

Auslöser war kein fehlender Schutz, sondern ein zu strenger an der falschen
Adresse. mcp 2.x aktiviert automatisch eine Allow-List auf ``127.0.0.1:*``, wenn
das ``host``-Argument der App loopback-artig aussieht — und
``streamable_http_app()`` defaultet genau darauf.

Die Besonderheit hier: ``create_http_app()`` ist eine uvicorn-``--factory`` und
bekommt **keine Argumente**. Die im Docstring dokumentierte Zeile
``uvicorn … --factory --host 0.0.0.0`` gibt den Bind also an uvicorn, nicht an
die App. Die Factory muss ihn aus denselben Settings lesen wie ``main()``, sonst
sieht die App weiterhin den Loopback-Default und antwortet mit HTTP 421.

Der Server hat zwei HTTP-Pfade; nur dieser war betroffen. ``main()`` ruft
``mcp.run(transport=…, host=settings.host, …)``, dort sieht das SDK den echten
Bind.

Die Bearer-Auth ersetzt das nicht: sie prüft, *wer* fragt, nicht *unter welchem
Namen* der Server angesprochen wird. Ein Rebinding-Angriff läuft in einem
Browser, der das Token bereits hält.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from parlament_mcp.server import build_transport_security, create_http_app

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
    for var in (
        "MCP_ALLOWED_HOSTS",
        "MCP_ALLOWED_ORIGINS",
        "MCP_BEARER_TOKENS",
        "MCP_HOST",
        "MCP_PORT",
        "PORT",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def test_loopback_bind_is_protected():
    sec = build_transport_security("127.0.0.1", 8080)
    assert sec is not None
    assert sec.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8080" in sec.allowed_hosts


def test_wildcard_bind_without_allowlist_stays_off():
    """Der eigentliche Fix.

    Auf 0.0.0.0 ist der erreichbare Name hier unbekannt, und der
    SDK-Loopback-Default ist genau eine Vermutung — er reproduziert das 421.
    """
    assert build_transport_security("0.0.0.0", 8080) is None


def test_wildcard_bind_with_allowlist_is_protected(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "parlament.example.ch")
    sec = build_transport_security("0.0.0.0", 8080)
    assert sec is not None
    assert "parlament.example.ch" in sec.allowed_hosts
    # Loopback bleibt drin, sonst brechen Container-Health-Checks.
    assert "127.0.0.1:8080" in sec.allowed_hosts


def test_cors_origins_pass_the_transport_check(monkeypatch):
    """Sonst weist der Transport genau die Browser-Clients ab, die CORS erlaubt."""
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://claude.ai")
    sec = build_transport_security("127.0.0.1", 8080)
    assert "https://claude.ai" in sec.allowed_origins


def test_wildcard_cors_is_not_copied(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "*")
    sec = build_transport_security("127.0.0.1", 8080)
    assert "*" not in sec.allowed_origins


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_all_loopback_forms_count_as_local(host):
    assert build_transport_security(host, 8080) is not None


def _post(app, host_header: str) -> int:
    with TestClient(app) as client:
        return client.post(
            "/mcp", headers={"Host": host_header, **_HEADERS}, json=_INIT
        ).status_code


def test_the_factory_reads_the_bind_from_the_environment(monkeypatch):
    """Der Kern der Sache.

    uvicorn ruft die Factory ohne Argumente auf, `--host` erreicht sie nie. Nur
    weil sie MCP_HOST liest, kommt der echte Bind in der App an — ohne das wäre
    es der Loopback-Default und damit 421.
    """
    import parlament_mcp.server as srv

    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    captured: dict = {}
    real = type(srv.mcp).streamable_http_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(srv.mcp), "streamable_http_app", _spy)
    create_http_app()
    assert captured["host"] == "0.0.0.0"


def test_a_public_bind_is_reachable_again(monkeypatch):
    """Die Regression selbst, durch den echten ASGI-Stack."""
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    assert _post(create_http_app(), "parlament.example.ch") == 200


def test_configured_host_is_served(monkeypatch):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "parlament.example.ch")
    assert _post(create_http_app(), "parlament.example.ch") == 200


def test_foreign_host_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "parlament.example.ch")
    assert _post(create_http_app(), "evil.example.com") == 421


def test_right_host_wrong_port_is_rejected(monkeypatch):
    """Der tragende Fall.

    ``evil.example.com`` allein beweist wenig: ein zurückfallender
    Loopback-Default würde ihn ebenfalls abweisen. Nur „richtiger Hostname,
    falscher Port" unterscheidet eine portgenaue Allow-List von einer, die alles
    durchlässt.
    """
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "parlament.example.ch:8080")
    assert _post(create_http_app(), "parlament.example.ch:9999") == 421


def test_the_host_check_is_not_the_bearer_check(monkeypatch):
    """Zwei getrennte Kontrollen — mit einem Token ändert sich am Host nichts.

    Genau darum ersetzt MCP_BEARER_TOKENS die Allow-List nicht: ein
    Rebinding-Angriff läuft in einem Browser, der das Token bereits hält, und
    scheitert nur an der Host-Prüfung.
    """
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "parlament.example.ch")
    monkeypatch.setenv("MCP_BEARER_TOKENS", "s3cret")
    app = create_http_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={
                "Host": "evil.example.com",
                "Authorization": "Bearer s3cret",
                **_HEADERS,
            },
            json=_INIT,
        )
    assert response.status_code == 421
