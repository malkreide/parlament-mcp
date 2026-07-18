"""Hermetische Tool-Tests (respx-Mocks für die OpenParlData-API)."""

from __future__ import annotations

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from openparldata_mcp import server as s
from openparldata_mcp.config import BASE_URL

from conftest import BODIES_FIXTURE


def _mock_bodies(router: respx.Router) -> None:
    router.get(f"{BASE_URL}/bodies/").mock(return_value=httpx.Response(200, json=BODIES_FIXTURE))


def _envelope(rows, total):
    return {"meta": {"total_records": total}, "data": rows}


@respx.mock
async def test_all_13_tools_registered():
    tools = await s.mcp.list_tools()
    names = {t.name for t in tools}
    assert len(names) == 13
    assert names == {
        "oparl_list_bodies", "oparl_search_affairs", "oparl_get_affair",
        "oparl_get_affair_documents", "oparl_compare_bodies", "oparl_search_persons",
        "oparl_get_person", "oparl_get_person_interests", "oparl_search_interests",
        "oparl_get_votings", "oparl_get_voting_results", "oparl_search_meetings",
        "oparl_source_status",
    }


@respx.mock
async def test_tool_annotations_are_read_only():
    tools = {t.name: t for t in await s.mcp.list_tools()}
    ann = tools["oparl_search_affairs"].annotations
    assert ann.readOnlyHint is True
    assert ann.destructiveHint is False
    assert ann.idempotentHint is True


@respx.mock
async def test_search_affairs_localizes_and_counts():
    _mock_bodies(respx.mock)
    respx.mock.get(f"{BASE_URL}/affairs/").mock(
        return_value=httpx.Response(200, json=_envelope(
            [{"id": 1, "body_key": "261", "title": {"de": "Tagesschule Rütihof"},
              "type_name": {"de": "Weisung"}, "state_name": {"de": "InBearbeitung"},
              "begin_date": "2024-05-01T00:00:00"}], 68))
    )
    r = await s.oparl_search_affairs(s.SearchAffairsInput(body_key="261", search="Tagesschule"))
    assert r.total_available == 68
    assert r.results[0].title == "Tagesschule Rütihof"
    assert r.results[0].begin_date == "2024-05-01"
    assert r.attribution == "Source: OpenParlData.ch"


@respx.mock
async def test_search_affairs_rejects_federal():
    with pytest.raises(ToolError, match="parlament-mcp"):
        await s.oparl_search_affairs(s.SearchAffairsInput(body_key="CHE", search="x"))


@respx.mock
async def test_documents_truncate_explicitly():
    _mock_bodies(respx.mock)
    long_text = "x" * 5000
    respx.mock.get(f"{BASE_URL}/affairs/42/docs").mock(
        return_value=httpx.Response(200, json=_envelope(
            [{"id": 7, "name": {"de": "Weisung"}, "category": {"de": "Dokument"},
              "format": "application/pdf", "text": long_text}], 1))
    )
    r = await s.oparl_get_affair_documents(s.GetAffairDocumentsInput(affair_id=42, max_chars=1000))
    doc = r.results[0]
    assert doc.text_truncated is True
    assert doc.text_total_chars == 5000
    assert len(doc.text) == 1000
    assert doc.category == "Dokument"


@respx.mock
async def test_documents_no_truncation_when_short():
    _mock_bodies(respx.mock)
    respx.mock.get(f"{BASE_URL}/affairs/42/docs").mock(
        return_value=httpx.Response(200, json=_envelope(
            [{"id": 7, "name": "Bericht", "text": "kurz"}], 1))
    )
    r = await s.oparl_get_affair_documents(s.GetAffairDocumentsInput(affair_id=42, max_chars=1000))
    assert r.results[0].text_truncated is False
    assert r.results[0].text_total_chars == 4


@respx.mock
async def test_interests_carry_data_quality_flag():
    _mock_bodies(respx.mock)
    respx.mock.get(f"{BASE_URL}/interests/").mock(
        return_value=httpx.Response(200, json=_envelope(
            [{"id": 1, "name": {"de": "2007"}, "role_name": None, "group": None}], 1))
    )
    r = await s.oparl_search_interests(s.SearchInterestsInput(body_key="ZH"))
    assert r.data_quality == "unverified_source_data"
    assert r.results[0].organisation == "2007"  # Parsing-Artefakt bleibt sichtbar


@respx.mock
async def test_search_interests_federal_points_to_lobbywatch():
    with pytest.raises(ToolError, match="lobbywatch-mcp"):
        await s.oparl_search_interests(s.SearchInterestsInput(body_key="CHE"))


def test_voting_results_requires_voting_id_and_caps_limit():
    # voting_id ist Pflicht (Feld ohne Default).
    with pytest.raises(Exception):
        s.GetVotingResultsInput(limit=10)
    # limit > 500 wird vom Schema abgewiesen (Skalierungs-Guardrail).
    with pytest.raises(Exception):
        s.GetVotingResultsInput(voting_id=1, limit=999)
    ok = s.GetVotingResultsInput(voting_id=1, limit=500)
    assert ok.limit == 500


@respx.mock
async def test_get_votings_requires_a_selector():
    with pytest.raises(ToolError, match="affair_id oder body_key"):
        await s.oparl_get_votings(s.GetVotingsInput())


@respx.mock
async def test_offset_cap_error_is_translated():
    _mock_bodies(respx.mock)
    problem = {
        "type": "https://api.openparldata.ch/problems/offset-cap-exceeded",
        "title": "Pagination depth too high", "status": 400,
        "detail": "too deep", "max_offset": 100000,
        "alternatives": {"bulk_export": "https://files.openparldata.ch/exports/affairs.ndjson.gz"},
    }
    respx.mock.get(f"{BASE_URL}/affairs/").mock(return_value=httpx.Response(400, json=problem))
    with pytest.raises(ToolError, match="Bulk-Export"):
        await s.oparl_search_affairs(s.SearchAffairsInput(body_key="261", offset=100))


@respx.mock
async def test_list_bodies_resolves_zurich_keys():
    _mock_bodies(respx.mock)
    r = await s.oparl_list_bodies(s.ListBodiesInput(search="Zürich"))
    keys = {b.body_key for b in r.results}
    assert keys == {"261", "ZH"}  # Winterthur matcht nicht auf "Zürich"
