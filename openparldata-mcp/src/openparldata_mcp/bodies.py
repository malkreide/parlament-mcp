"""Body-Cache und ``body_key``-Validierung.

Die API sagt nie Nein, sie sagt Nichts: Ein ungültiger ``body_key`` liefert
HTTP 200 mit leerem Array statt eines Fehlers (verifizierte Probe 2026-07-18).
Deshalb wird die Liste der Körperschaften (``/v1/bodies/?indexed=true``, 97
Einträge) einmal geladen und 24 h gecacht. Jedes Tool validiert ``body_key``
gegen diesen Cache VOR dem Request und wirft bei Unbekanntem einen sprechenden
Fehler mit Vorschlagsliste (Fuzzy-Match auf den Namen).
"""

from __future__ import annotations

import asyncio
import difflib
import time
from dataclasses import dataclass, field

from mcp.server.fastmcp.exceptions import ToolError

from openparldata_mcp.client import api_get, unwrap
from openparldata_mcp.config import (
    BODY_CACHE_TTL_SECONDS,
    FEDERAL_BODY_KEY,
    FEDERAL_REDIRECT,
)
from openparldata_mcp.localize import localize

# Öffentliche body_type-Werte → API-``type``-Werte.
# 26 Kantone (canton) + ~70 Gemeindeparlamente (city + municipality). Die
# API-Typen ``country`` (CHE, LIE) sind subnational nicht relevant und werden
# nirgends gelistet.
_BODY_TYPE_MAP = {
    "canton": ("canton",),
    "municipality": ("city", "municipality"),
}
_SUBNATIONAL_TYPES = ("canton", "city", "municipality")


@dataclass
class Body:
    """Eine Körperschaft (Kanton oder Gemeinde) aus dem Body-Cache."""

    body_key: str
    name: str
    type: str
    canton_key: str | None = None
    body_id: int | None = None


@dataclass
class _Cache:
    bodies: dict[str, Body] = field(default_factory=dict)
    loaded_at: float | None = None


_cache = _Cache()
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    # Lock lazy erzeugen, damit er an den laufenden Event-Loop gebunden ist.
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def _is_fresh() -> bool:
    return (
        _cache.loaded_at is not None
        and (time.time() - _cache.loaded_at) < BODY_CACHE_TTL_SECONDS
    )


def cache_age_seconds() -> float | None:
    """Alter des Body-Cache in Sekunden (oder ``None``, wenn nie geladen)."""
    if _cache.loaded_at is None:
        return None
    return time.time() - _cache.loaded_at


def _parse_bodies(rows: list[dict]) -> dict[str, Body]:
    out: dict[str, Body] = {}
    for r in rows:
        key = r.get("body_key")
        if not key:
            continue
        out[str(key)] = Body(
            body_key=str(key),
            name=localize(r.get("name")) or str(key),
            type=r.get("type") or "",
            canton_key=r.get("canton_key"),
            body_id=r.get("id"),
        )
    return out


async def ensure_loaded(force: bool = False) -> None:
    """Body-Cache lazy laden bzw. bei abgelaufener TTL erneuern."""
    if _is_fresh() and not force:
        return
    async with _get_lock():
        if _is_fresh() and not force:  # doppelt geprüft nach Lock-Erwerb
            return
        payload = await api_get("/bodies/", {"indexed": "true", "limit": 500})
        rows, _meta = unwrap(payload)
        _cache.bodies = _parse_bodies(rows)
        _cache.loaded_at = time.time()


def _suggest(body_key: str, limit: int = 5) -> list[str]:
    """Fuzzy-Vorschläge (auf Name UND Key) für einen unbekannten body_key."""
    if not _cache.bodies:
        return []
    # Kandidaten: "261 – Zürich (city)"
    label = {b.body_key: f"{b.body_key} – {b.name} ({b.type})" for b in _cache.bodies.values()}
    names = {b.name.lower(): b.body_key for b in _cache.bodies.values()}
    hits: list[str] = []
    seen: set[str] = set()
    # 1) Fuzzy auf Namen
    for name_match in difflib.get_close_matches(body_key.lower(), list(names), n=limit, cutoff=0.5):
        k = names[name_match]
        if k not in seen:
            seen.add(k)
            hits.append(label[k])
    # 2) Fuzzy auf Keys
    for k in difflib.get_close_matches(body_key, list(_cache.bodies), n=limit, cutoff=0.4):
        if k not in seen:
            seen.add(k)
            hits.append(label[k])
    return hits[:limit]


async def resolve_body(body_key: str, *, federal_hint: str = FEDERAL_REDIRECT) -> Body:
    """``body_key`` gegen den Cache validieren und die Körperschaft zurückgeben.

    - ``CHE`` (Bund) wird aktiv abgewiesen (``federal_hint``).
    - ``country``-Körperschaften (z.B. LIE) sind subnational nicht abgedeckt.
    - Unbekannte Keys werfen einen Fehler mit Fuzzy-Vorschlägen.
    """
    key = (body_key or "").strip()
    if not key:
        raise ToolError("body_key fehlt. Beispiel: '261' (Stadt Zürich) oder 'ZH' (Kanton Zürich).")

    if key.upper() == FEDERAL_BODY_KEY:
        raise ToolError(federal_hint)

    await ensure_loaded()
    body = _cache.bodies.get(key) or _cache.bodies.get(key.upper())
    if body is None:
        suggestions = _suggest(key)
        hint = (
            " Meintest du: " + "; ".join(suggestions) + "?"
            if suggestions
            else " Mit oparl_list_bodies lassen sich alle gültigen body_keys auflisten."
        )
        raise ToolError(f"Unbekannter body_key '{key}'.{hint}")

    if body.type not in _SUBNATIONAL_TYPES:
        raise ToolError(
            f"body_key '{key}' ({body.name}) ist keine subnationale Körperschaft "
            f"(Typ '{body.type}') und wird von diesem Server nicht abgedeckt."
        )
    return body


async def list_bodies(search: str | None = None, body_type: str | None = None) -> list[Body]:
    """Gecachte Körperschaften filtern (subnational; ``country`` ausgeschlossen)."""
    await ensure_loaded()
    allowed_types = _BODY_TYPE_MAP.get(body_type or "", _SUBNATIONAL_TYPES)
    needle = (search or "").strip().lower()
    out = [
        b
        for b in _cache.bodies.values()
        if b.type in allowed_types
        and (not needle or needle in b.name.lower() or needle in b.body_key.lower())
    ]
    return sorted(out, key=lambda b: (b.type, b.name))
