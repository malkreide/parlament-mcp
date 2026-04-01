"""Tests for parlament-mcp server."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from parlament_mcp.server import (
    GetBusinessInput,
    GetSessionsInput,
    GetVotesInput,
    SearchBusinessInput,
    SearchMembersInput,
    _fmt_business,
    _parse_date,
    parlament_get_sessions,
    parlament_get_votes,
    parlament_search_business,
    parlament_search_members,
)

# ---------------------------------------------------------------------------
# Unit tests – no network
# ---------------------------------------------------------------------------


def test_parse_date_valid():
    assert _parse_date("/Date(1735689600000)/") == "2025-01-01"


def test_parse_date_none():
    assert _parse_date(None) == ""


def test_parse_date_empty():
    assert _parse_date("") == ""


def test_fmt_business_basic():
    raw = {
        "ID": 20261009,
        "BusinessShortNumber": "26.1009",
        "BusinessTypeName": "Anfrage",
        "Title": "Künstliche Intelligenz und digitale Infrastruktur",
        "BusinessStatusText": "Eingereicht",
        "BusinessStatusDate": "/Date(1735689600000)/",
        "SubmittedBy": "Müller Hans",
        "SubmissionDate": "/Date(1735689600000)/",
        "SubmissionCouncilAbbreviation": "NR",
        "ResponsibleDepartmentAbbreviation": None,
        "Description": "Kurzbeschreibung",
        "TagNames": None,
    }
    result = _fmt_business(raw)
    assert result["id"] == 20261009
    assert result["type"] == "Anfrage"
    assert "Intelligenz" in result["title"]


# ---------------------------------------------------------------------------
# Integration tests – mocked HTTP
# ---------------------------------------------------------------------------

MOCK_BUSINESS = [
    {
        "ID": 20261009,
        "BusinessShortNumber": "26.1009",
        "BusinessTypeName": "Anfrage",
        "Title": "Künstliche Intelligenz und digitale Infrastruktur",
        "BusinessStatusText": "Eingereicht",
        "BusinessStatusDate": "/Date(1735689600000)/",
        "SubmittedBy": "Test Person",
        "SubmissionDate": "/Date(1735689600000)/",
        "SubmissionCouncilAbbreviation": "NR",
        "SubmissionCouncilName": "Nationalrat",
        "ResponsibleDepartmentAbbreviation": "UVEK",
        "ResponsibleDepartmentName": "UVEK",
        "Description": "Testbeschreibung",
        "TagNames": "KI, Digitalisierung",
    }
]

MOCK_MEMBER = [
    {
        "ID": 4300,
        "FirstName": "Anna",
        "LastName": "Tester",
        "CouncilAbbreviation": "NR",
        "CantonAbbreviation": "ZH",
        "PartyAbbreviation": "SP",
        "ParlGroupAbbreviation": "S",
        "Active": True,
        "DateJoining": "/Date(1609459200000)/",
    }
]

MOCK_SESSION = [
    {
        "ID": 5212,
        "SessionName": "Sommersession 2025",
        "Abbreviation": "SS25",
        "StartDate": "/Date(1748736000000)/",
        "EndDate": "/Date(1749945600000)/",
        "TypeName": "Ordentliche Session",
        "LegislativePeriodNumber": 52,
    }
]


@pytest.fixture
def mock_odata():
    """Patch _odata_get to return mock data."""
    with patch("parlament_mcp.server._odata_get", new_callable=AsyncMock) as mock:
        yield mock


@pytest.mark.asyncio
async def test_search_business_markdown(mock_odata):
    mock_odata.return_value = MOCK_BUSINESS
    params = SearchBusinessInput(keyword="KI", keyword2="Schule", status="Eingereicht")
    result = await parlament_search_business(params)
    assert "Künstliche Intelligenz" in result
    assert "Eingereicht" in result
    assert "Curia Vista" in result


@pytest.mark.asyncio
async def test_search_business_json(mock_odata):
    mock_odata.return_value = MOCK_BUSINESS
    params = SearchBusinessInput(keyword="KI", response_format="json")
    result = await parlament_search_business(params)
    data = json.loads(result)
    assert data["count"] == 1
    assert data["results"][0]["type"] == "Anfrage"


@pytest.mark.asyncio
async def test_search_business_empty(mock_odata):
    mock_odata.return_value = []
    params = SearchBusinessInput(keyword="xyz_nonexistent_12345")
    result = await parlament_search_business(params)
    assert "Keine Vorstösse" in result


@pytest.mark.asyncio
async def test_search_members_zh(mock_odata):
    mock_odata.return_value = MOCK_MEMBER
    params = SearchMembersInput(canton="ZH")
    result = await parlament_search_members(params)
    assert "Anna Tester" in result
    assert "ZH" in result


@pytest.mark.asyncio
async def test_get_sessions(mock_odata):
    mock_odata.return_value = MOCK_SESSION
    params = GetSessionsInput()
    result = await parlament_get_sessions(params)
    assert "Sommersession" in result


# ---------------------------------------------------------------------------
# Live tests – hit real API (excluded from CI)
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_search_ki():
    """Live: search for 'Künstliche Intelligenz' motions."""
    params = SearchBusinessInput(keyword="Künstliche Intelligenz", limit=5)
    result = await parlament_search_business(params)
    assert len(result) > 50
    assert "Künstliche Intelligenz" in result or "Keine Vorstösse" in result


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_zh_members():
    """Live: fetch active ZH council members."""
    params = SearchMembersInput(canton="ZH", active_only=True, limit=5)
    result = await parlament_search_members(params)
    assert "ZH" in result


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_sessions():
    """Live: list most recent sessions."""
    params = GetSessionsInput(limit=5)
    result = await parlament_get_sessions(params)
    assert "Session" in result or "5" in result
