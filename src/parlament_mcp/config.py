"""Zentrale Konfiguration via pydantic-settings (ARCH-004).

Statt verstreuter ``os.environ``-Zugriffe wird die Server-Konfiguration in
einem einzigen, typgeprüften ``Settings``-Objekt gebündelt. Felder werden aus
``MCP_*``-Environment-Variablen geladen (z.B. ``MCP_TRANSPORT``, ``MCP_HOST``).
"""

from __future__ import annotations

import sys

from mcp.types.version import LATEST_HANDSHAKE_VERSION
from pydantic_settings import BaseSettings, SettingsConfigDict

# Die Revision, die `server_start` ins Log schreibt (ARCH-012).
#
# Hier stand `"2025-06-18"` — drei Revisionen alt. Ein Literal an dieser Stelle
# ist eine zweite Wahrheit neben dem SDK, und zweite Wahrheiten driften: seit
# dem Umstieg auf `mcp` 2.x handelt dieser Server `2025-11-25` aus, geloggt
# wurde weiter die alte Zahl. Ein Log, das etwas anderes sagt als die Leitung,
# ist beim Debuggen schlimmer als gar keines.
#
# Deshalb abgeleitet statt geschrieben. `LATEST_HANDSHAKE_VERSION` und nicht
# `LATEST_PROTOCOL_VERSION`: Letzteres ist ein Alias auf die moderne
# Envelope-Aera, waehrend der Wert hier die Aera beschreibt, in der heutige
# Clients sprechen. `tests/test_protocol_version.py` pinnt beide, die Ableitung
# kann also nicht unbemerkt wandern.
PROTOCOL_VERSION = LATEST_HANDSHAKE_VERSION

# Datenquelle / Lizenz (CH-004 — OGD-CH-Attribution).
DATA_SOURCE = "Curia Vista – Schweizer Parlament (ws.parlament.ch)"
DATA_LICENSE = "CC BY 4.0"


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
    otel_enabled: bool = True


def warn_on_dangerous_binding(host: str) -> None:
    """Warnt, wenn ausserhalb eines Container-Kontexts an 0.0.0.0 gebunden wird
    (SEC-016, NeighborJack)."""
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
