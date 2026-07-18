"""Tests für Body-Cache, body_key-Validierung und CHE-Abweisung."""

from __future__ import annotations

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from openparldata_mcp import bodies as body_cache
from openparldata_mcp.config import BASE_URL, FEDERAL_INTERESTS_REDIRECT

from conftest import BODIES_FIXTURE


def _mock_bodies(router: respx.Router) -> None:
    router.get(f"{BASE_URL}/bodies/").mock(return_value=httpx.Response(200, json=BODIES_FIXTURE))


@respx.mock
async def test_resolve_valid_body():
    _mock_bodies(respx.mock)
    body = await body_cache.resolve_body("261")
    assert body.name == "Zürich"
    assert body.type == "city"


@respx.mock
async def test_che_is_rejected_before_any_request():
    # Kein Body-Mock nötig: CHE wird VOR dem Netzwerk abgewiesen.
    with pytest.raises(ToolError, match="parlament-mcp"):
        await body_cache.resolve_body("CHE")


@respx.mock
async def test_che_interests_hint_points_to_lobbywatch():
    with pytest.raises(ToolError, match="lobbywatch-mcp"):
        await body_cache.resolve_body("CHE", federal_hint=FEDERAL_INTERESTS_REDIRECT)


@respx.mock
async def test_unknown_body_key_yields_fuzzy_suggestion():
    _mock_bodies(respx.mock)
    with pytest.raises(ToolError, match="Meintest du"):
        await body_cache.resolve_body("Zurich")  # tippfehler -> fuzzy auf Zürich


@respx.mock
async def test_country_type_is_out_of_scope():
    _mock_bodies(respx.mock)
    with pytest.raises(ToolError, match="subnationale"):
        await body_cache.resolve_body("LIE")


@respx.mock
async def test_list_bodies_filters_by_type_and_excludes_country():
    _mock_bodies(respx.mock)
    cantons = await body_cache.list_bodies(body_type="canton")
    assert [b.body_key for b in cantons] == ["ZH"]
    munis = await body_cache.list_bodies(body_type="municipality")
    assert {b.body_key for b in munis} == {"261", "230"}
    # LIE (country) darf nie erscheinen
    all_bodies = await body_cache.list_bodies()
    assert "LIE" not in {b.body_key for b in all_bodies}
