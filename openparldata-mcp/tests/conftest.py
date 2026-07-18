"""Gemeinsame Test-Fixtures: globalen Zustand (Body-Cache, HTTP-Client) isolieren."""

from __future__ import annotations

import pytest

from openparldata_mcp import bodies as body_cache
from openparldata_mcp import client as client_mod

# Minimaler Body-Index für hermetische Tests (kein echtes Netzwerk).
BODIES_FIXTURE = {
    "meta": {"total_records": 4},
    "data": [
        {"id": 1, "body_key": "261", "name": {"de": "Zürich"}, "type": "city", "canton_key": "ZH"},
        {"id": 2, "body_key": "230", "name": {"de": "Winterthur"}, "type": "city", "canton_key": "ZH"},
        {"id": 3, "body_key": "ZH", "name": {"de": "Zürich"}, "type": "canton", "canton_key": "ZH"},
        {"id": 4, "body_key": "LIE", "name": {"de": "Liechtenstein"}, "type": "country", "canton_key": None},
    ],
}


@pytest.fixture(autouse=True)
def _reset_state():
    """Vor jedem Test globalen Cache/Client-Zustand zurücksetzen."""
    body_cache._cache.bodies = {}
    body_cache._cache.loaded_at = None
    body_cache._lock = None
    client_mod._client = None
    client_mod._client_loop = None
    client_mod._last_success_epoch = None
    yield
