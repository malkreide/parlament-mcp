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
        {
            "id": 2,
            "body_key": "230",
            "name": {"de": "Winterthur"},
            "type": "city",
            "canton_key": "ZH",
        },
        {"id": 3, "body_key": "ZH", "name": {"de": "Zürich"}, "type": "canton", "canton_key": "ZH"},
        {
            "id": 4,
            "body_key": "LIE",
            "name": {"de": "Liechtenstein"},
            "type": "country",
            "canton_key": None,
        },
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


@pytest.fixture
def offline_lifespan():
    """Fuer Tests, die den Server ueber einen echten `Client` ansprechen.

    Der Lifespan waermt den Body-Cache vor und fragt dafuer die Live-API. Ein
    `Client(mcp)` faehrt den Lifespan mit — ohne diese Fixture ginge jeder
    solche Test ins Netz. `respx` beantwortet genau diese eine Anfrage und
    laesst jede andere scheitern.
    """
    import httpx
    import respx

    from openparldata_mcp.config import BASE_URL

    with respx.mock(assert_all_called=False) as router:
        router.get(f"{BASE_URL}/bodies/").mock(
            return_value=httpx.Response(200, json=BODIES_FIXTURE)
        )
        yield router
