"""Async-HTTP-Client für die OpenParlData-API.

Kapselt:
  · einen über die Server-Lebensdauer gepoolten ``httpx.AsyncClient``
    (loop-bewusst neu aufgebaut, wenn der Event-Loop wechselt),
  · eine unveränderliche Egress-Allow-List (Defense-in-Depth),
  · die Übersetzung der API-Fehlerformate in sprechende ``ToolError``.

Fehlerbilder der API (verifiziert 2026-07-18):
  · 404  → ``{"detail": "..."}``
  · 400  → RFC-7807 ``offset-cap-exceeded`` inkl. ``max_offset`` + ``alternatives``
  · ungültiger ``body_key`` → HTTP 200 mit ``data: []`` ("Silent Empty" – die API
    sagt nie Nein, sie sagt Nichts; deshalb validieren wir body_key vorab gegen
    den Body-Cache, siehe ``bodies.py``).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from openparldata_mcp.config import BASE_URL, HTTP_TIMEOUT, MAX_OFFSET
from openparldata_mcp.logging_setup import get_logger

_logger = get_logger("openparldata_mcp.client")

# Unveränderliche Egress-Allow-List (nicht zur Laufzeit mutierbar/config-bar).
ALLOWED_HOSTS: frozenset[str] = frozenset({"api.openparldata.ch"})

# Zeitpunkt (Unix) des letzten erfolgreichen Abrufs – für oparl_source_status.
_last_success_epoch: float | None = None

_client: httpx.AsyncClient | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


class EgressNotAllowed(Exception):
    """Wird geworfen, wenn ein nicht erlaubter Host kontaktiert werden soll."""


def assert_host_allowed(url: str) -> None:
    """Bricht ab, wenn der Host der URL nicht in ``ALLOWED_HOSTS`` ist."""
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise EgressNotAllowed(
            f"Host nicht in Egress-Allow-List: {host!r} (erlaubt: {sorted(ALLOWED_HOSTS)})"
        )


def last_success_epoch() -> float | None:
    """Unix-Zeit des letzten erfolgreichen API-Abrufs (oder ``None``)."""
    return _last_success_epoch


def get_client() -> httpx.AsyncClient:
    """Geteilten AsyncClient zurückgeben (lazy, loop-bewusst neu aufgebaut)."""
    global _client, _client_loop
    running_loop = asyncio.get_running_loop()
    if _client is None or _client.is_closed or _client_loop is not running_loop:
        _client = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "openparldata-mcp/0.1 (+https://github.com/malkreide/openparldata-mcp)"},
        )
        _client_loop = running_loop
    return _client


async def aclose() -> None:
    """Gepoolten Client schliessen (vom Lifespan aufgerufen)."""
    global _client, _client_loop
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None
    _client_loop = None


def _translate_http_error(exc: httpx.HTTPStatusError) -> ToolError:
    """API-Fehlerformate in eine verständliche ToolError übersetzen."""
    resp = exc.response
    code = resp.status_code
    try:
        body = resp.json()
    except Exception:
        body = {}

    if code == 404:
        detail = body.get("detail") if isinstance(body, dict) else None
        return ToolError(f"Nicht gefunden: {detail or 'Ressource existiert nicht.'} "
                         "Bitte ID bzw. Parameter prüfen.")

    if code == 400 and isinstance(body, dict) and body.get("max_offset") is not None:
        max_off = body.get("max_offset", MAX_OFFSET)
        alt = (body.get("alternatives") or {}).get("bulk_export") or (
            "https://files.openparldata.ch/exports/"
        )
        return ToolError(
            f"Paginierungstiefe überschritten: Der Offset ist auf {max_off} begrenzt. "
            "Für vollständige Datensätze jenseits dieser Grenze ist der Bulk-Export "
            f"vorgesehen (Phase 2): {alt}"
        )

    if code == 400:
        detail = body.get("detail") or body.get("title") if isinstance(body, dict) else None
        return ToolError(f"Ungültige Anfrage (HTTP 400): {detail or 'Parameter prüfen.'}")

    if code == 429:
        return ToolError("Rate-Limit erreicht (HTTP 429). Bitte kurz warten und erneut versuchen.")
    if code in (502, 503, 504):
        return ToolError("Dienst vorübergehend nicht verfügbar. Bitte erneut versuchen.")
    return ToolError(f"API-Anfrage fehlgeschlagen (HTTP {code}).")


async def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET auf ``{BASE_URL}{path}`` ausführen und JSON zurückgeben.

    ``path`` beginnt mit ``/`` (z.B. ``/affairs/``). Leere/None-Parameter werden
    entfernt. Fehler werden in sprechende ``ToolError`` übersetzt.
    """
    global _last_success_epoch
    url = f"{BASE_URL}{path}"
    assert_host_allowed(url)
    clean = {k: v for k, v in (params or {}).items() if v is not None and v != ""}

    client = get_client()
    try:
        resp = await client.get(url, params=clean)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _logger.warning("api_http_error", status=exc.response.status_code, path=path)
        raise _translate_http_error(exc) from exc
    except httpx.TimeoutException as exc:
        _logger.warning("api_timeout", path=path)
        raise ToolError("Zeitüberschreitung: Die OpenParlData-API antwortet nicht. "
                        "Bitte erneut versuchen.") from exc
    except httpx.HTTPError as exc:
        _logger.warning("api_transport_error", path=path, error=type(exc).__name__)
        raise ToolError(f"Netzwerkfehler beim Zugriff auf die OpenParlData-API ({type(exc).__name__}).") from exc

    _last_success_epoch = time.time()
    return resp.json()


def unwrap(payload: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Einheitliches ``{"meta": ..., "data": [...]}``-Envelope aufteilen.

    Gibt ``(data, meta)`` zurück. Einzel-Ressourcen (ohne Envelope) werden als
    ``([payload], {})`` behandelt.
    """
    if isinstance(payload, dict) and "data" in payload:
        data = payload.get("data") or []
        if isinstance(data, dict):
            data = [data]
        return data, payload.get("meta") or {}
    if isinstance(payload, dict):
        return [payload], {}
    if isinstance(payload, list):
        return payload, {}
    return [], {}
