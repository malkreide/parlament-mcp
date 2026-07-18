"""Zentrale Konfiguration via pydantic-settings.

Die Server-Konfiguration wird in einem einzigen, typgeprüften ``Settings``-Objekt
gebündelt. Felder werden aus ``MCP_*``-Environment-Variablen geladen (z.B.
``MCP_TRANSPORT``, ``MCP_HOST``, ``MCP_PORT``).
"""

from __future__ import annotations

import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

# MCP-Spec-Version, gegen die dieser Server getestet/gepinnt ist.
PROTOCOL_VERSION = "2025-06-18"

# ─────────────────────────── Datenquelle / Lizenz ──────────────────────────────
BASE_URL = "https://api.openparldata.ch/v1"
BODIES_INDEX_URL = f"{BASE_URL}/bodies/?indexed=true&limit=500"

DATA_SOURCE = "OpenParlData.ch"
DATA_LICENSE = "CC BY 4.0"
# Von der API vorgeschriebene Attribution (Lizenzbedingung CC BY 4.0).
DATA_ATTRIBUTION = "Source: OpenParlData.ch"

# ─────────────────────────── Abgrenzung Bundesebene ────────────────────────────
# Dieser Server deckt AUSSCHLIESSLICH die subnationale Ebene ab (26 Kantone +
# ~70 Gemeindeparlamente). Die Bundesebene (body_key="CHE") wird aktiv abgewiesen.
FEDERAL_BODY_KEY = "CHE"
FEDERAL_REDIRECT = (
    "Der body_key 'CHE' bezeichnet die Bundesebene. Dieser Server deckt nur die "
    "subnationale Ebene ab (Kantone und Gemeinden). Für die Bundesebene ist "
    "'parlament-mcp' (Curia Vista) die geeignete Quelle."
)
# oparl_search_interests verweist zusätzlich auf lobbywatch-mcp.
FEDERAL_INTERESTS_REDIRECT = (
    "Interessenbindungen auf Bundesebene (body_key='CHE') sind hier nicht "
    "verfügbar. Nutze dafür 'lobbywatch-mcp' – dort sind die Bindungen "
    "redaktionell geprüft und mit einer Branchen-Taxonomie versehen. Für "
    "allgemeine Bundes-Parlamentsdaten ist 'parlament-mcp' (Curia Vista) die Quelle."
)

# ─────────────────────────── Skalierungs-Guardrails ────────────────────────────
# /v1/votes/ enthält >47 Mio. Einzelstimmen. voting_id ist Pflicht, limit hart
# gedeckelt (API-Maximum wäre 1000).
VOTES_MAX_LIMIT = 500
# Ab hier antwortet die API mit RFC-7807 (offset-cap-exceeded) → Bulk-Export.
MAX_OFFSET = 100_000

HTTP_TIMEOUT = 30.0
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
# Body-Cache aus /v1/bodies/?indexed=true (97 Einträge), 24 h Gültigkeit.
BODY_CACHE_TTL_SECONDS = 24 * 60 * 60


class Settings(BaseSettings):
    """Server-Laufzeitkonfiguration. Defaults sind lokal-sicher."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: str = "INFO"
    json_logs: bool = True


def warn_on_dangerous_binding(host: str) -> None:
    """Warnt, wenn ausserhalb eines Container-Kontexts an 0.0.0.0 gebunden wird
    (NeighborJack-Risiko)."""
    import os

    if host in ("0.0.0.0", "::"):
        in_container = (
            os.path.exists("/.dockerenv")
            or os.environ.get("KUBERNETES_SERVICE_HOST")
            or os.environ.get("RAILWAY_PROJECT_ID")
            or os.environ.get("RENDER")
        )
        if not in_container:
            sys.stderr.write(
                f"WARNUNG: Bindung an {host} ausserhalb eines Container-Kontexts "
                "exponiert den Server im lokalen Netzwerk (NeighborJack-Risiko). "
                "Für lokale Nutzung MCP_HOST=127.0.0.1 setzen.\n"
            )
