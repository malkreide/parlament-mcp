"""
parlament-mcp – Swiss Parliament MCP Server
Connects AI models to ws.parlament.ch (Curia Vista OData API).
No authentication required (Phase 1 – No-Auth-First).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://ws.parlament.ch/odata.svc"
DEFAULT_LANG = "DE"
DEFAULT_TIMEOUT = 20.0
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Business type IDs (Curia Vista)
BUSINESS_TYPE_NAMES = {
    5: "Motion",
    6: "Postulat",
    8: "Interpellation",
    9: "Dringliche Interpellation",
    12: "Einfache Anfrage",
    18: "Anfrage",
    4: "Parlamentarische Initiative",
    3: "Standesinitiative",
    1: "Geschäft des Bundesrates",
}

# ---------------------------------------------------------------------------
# FastMCP initialisation  (FastMCP v1.26.0 pattern)
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "parlament_mcp",
    instructions=(
        "Swiss Parliament MCP Server – access Curia Vista data: "
        "parliamentary motions (Vorstösse), votes, members, sessions, "
        "and debate transcripts via the ws.parlament.ch OData API."
    ),
)

transport = os.getenv("MCP_TRANSPORT", "stdio")
if transport == "sse":
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = int(os.getenv("PORT", "8080"))

# ---------------------------------------------------------------------------
# Shared HTTP client helper
# ---------------------------------------------------------------------------


async def _odata_get(
    entity: str,
    filters: list[str] | None = None,
    orderby: str | None = None,
    top: int = DEFAULT_LIMIT,
    skip: int = 0,
    select: list[str] | None = None,
    lang: str = DEFAULT_LANG,
) -> list[dict[str, Any]]:
    """Execute an OData GET request and return the result list."""
    params: dict[str, str] = {
        "$format": "json",
        "$top": str(min(top, MAX_LIMIT)),
    }
    if skip:
        params["$skip"] = str(skip)

    # Always filter by language
    lang_filter = f"Language eq '{lang}'"
    all_filters = [lang_filter] + (filters or [])
    params["$filter"] = " and ".join(f"({f})" for f in all_filters)

    if orderby:
        params["$orderby"] = orderby
    if select:
        params["$select"] = ",".join(select)

    url = f"{BASE_URL}/{entity}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = client.build_request("GET", url, params=params)
        response = await client.send(resp)
        response.raise_for_status()
        data = response.json()
        return data.get("d", [])


def _parse_date(ms_date: str | None) -> str:
    """Convert OData /Date(...)/ to ISO string."""
    if not ms_date:
        return ""
    try:
        ms = int(ms_date.replace("/Date(", "").replace(")/", ""))
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ms_date


def _fmt_business(b: dict) -> dict:
    """Return a clean Business dict for tool responses."""
    return {
        "id": b.get("ID"),
        "short_number": b.get("BusinessShortNumber"),
        "type": b.get("BusinessTypeName"),
        "title": b.get("Title"),
        "status": b.get("BusinessStatusText"),
        "status_date": _parse_date(b.get("BusinessStatusDate")),
        "submitted_by": b.get("SubmittedBy"),
        "submission_date": _parse_date(b.get("SubmissionDate")),
        "council": b.get("SubmissionCouncilAbbreviation"),
        "department": b.get("ResponsibleDepartmentAbbreviation"),
        "description": (b.get("Description") or "")[:400],
        "tags": b.get("TagNames"),
    }


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class Language(str, Enum):
    DE = "DE"
    FR = "FR"
    IT = "IT"


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class SearchBusinessInput(BaseModel):
    """Input for searching parliamentary businesses (Vorstösse)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: Optional[str] = Field(
        default=None,
        description=(
            "Keyword to search in the title. "
            "Examples: 'Künstliche Intelligenz', 'Bildung', 'Digitalisierung', 'Schule', 'KI'"
        ),
        max_length=200,
    )
    keyword2: Optional[str] = Field(
        default=None,
        description="Second keyword (ANDed with keyword). Example: 'Schule' when keyword='KI'.",
        max_length=200,
    )
    business_type: Optional[str] = Field(
        default=None,
        description=(
            "Filter by business type. Valid values: 'Motion', 'Postulat', 'Interpellation', "
            "'Parlamentarische Initiative', 'Standesinitiative', 'Anfrage', 'Einfache Anfrage'"
        ),
    )
    status: Optional[str] = Field(
        default=None,
        description=(
            "Filter by status. Common values: 'Eingereicht' (pending/open), "
            "'Erledigt' (closed), 'Überwiesen an den Bundesrat' (referred to Federal Council), "
            "'Angenommen' (accepted), 'Abgelehnt' (rejected)"
        ),
    )
    submitted_after: Optional[str] = Field(
        default=None,
        description="Filter businesses submitted after this date (ISO format YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    council: Optional[str] = Field(
        default=None,
        description="Filter by submitting council: 'NR' (Nationalrat) or 'SR' (Ständerat).",
    )
    limit: int = Field(
        default=20,
        description="Maximum number of results (1–100).",
        ge=1,
        le=MAX_LIMIT,
    )
    offset: int = Field(default=0, description="Offset for pagination.", ge=0)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (readable) or 'json' (structured).",
    )


class GetBusinessInput(BaseModel):
    """Input for fetching a single business by ID."""

    model_config = ConfigDict(extra="forbid")

    business_id: int = Field(
        ..., description="The numeric Curia Vista business ID (e.g. 20254750)."
    )
    language: Language = Field(default=Language.DE, description="Response language.")


class SearchMembersInput(BaseModel):
    """Input for searching council members (Parlamentarier)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    canton: Optional[str] = Field(
        default=None,
        description="Filter by canton abbreviation, e.g. 'ZH', 'BE', 'GE', 'AG'.",
        max_length=2,
    )
    last_name: Optional[str] = Field(
        default=None,
        description="Filter by last name (partial match).",
        max_length=100,
    )
    council: Optional[str] = Field(
        default=None,
        description="Filter by council: 'NR' (Nationalrat) or 'SR' (Ständerat).",
    )
    party: Optional[str] = Field(
        default=None,
        description="Filter by party abbreviation, e.g. 'SP', 'SVP', 'FDP', 'Mitte', 'Grüne'.",
        max_length=20,
    )
    active_only: bool = Field(
        default=True,
        description="If true, return only currently active members.",
    )
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetVotesInput(BaseModel):
    """Input for fetching parliamentary votes (Abstimmungen)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: Optional[str] = Field(
        default=None,
        description="Keyword in the vote's business title (e.g. 'Bildung', 'KI').",
        max_length=200,
    )
    session_id: Optional[int] = Field(
        default=None,
        description="Filter votes from a specific session ID.",
    )
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetSessionsInput(BaseModel):
    """Input for listing parliamentary sessions."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetTranscriptsInput(BaseModel):
    """Input for fetching debate transcripts."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: Optional[str] = Field(
        default=None,
        description="Keyword to search in the transcript text (e.g. 'KI', 'Schule').",
        max_length=200,
    )
    speaker_name: Optional[str] = Field(
        default=None,
        description="Filter by speaker last name.",
        max_length=100,
    )
    session_id: Optional[int] = Field(
        default=None,
        description="Filter transcripts from a specific session.",
    )
    council: Optional[str] = Field(
        default=None,
        description="Filter by council: 'NR' or 'SR'.",
    )
    limit: int = Field(default=15, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="parlament_search_business",
    annotations={
        "title": "Search Parliamentary Businesses (Vorstösse)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_search_business(params: SearchBusinessInput) -> str:
    """Search parliamentary businesses (motions, interpellations, postulates, etc.).

    Returns Curia Vista business records from ws.parlament.ch. Use this tool to
    find pending motions on AI in schools, digitisation initiatives, education
    policy, or any other topic of interest to the KI-Fachgruppe.

    Anchor query example: 'Welche Vorstösse zu KI in der Schule sind hängig?'
    → keyword='KI', keyword2='Schule', status='Eingereicht'

    Args:
        params (SearchBusinessInput): Search parameters including keyword(s),
            business type, status, council, date filter, pagination.

    Returns:
        str: Formatted list of matching parliamentary businesses with ID, type,
             title, status, submitter, and submission date.
    """
    filters: list[str] = []

    if params.keyword:
        kw = params.keyword.replace("'", "''")
        filters.append(f"substringof('{kw}',Title)")
    if params.keyword2:
        kw2 = params.keyword2.replace("'", "''")
        filters.append(f"substringof('{kw2}',Title)")
    if params.business_type:
        bt = params.business_type.replace("'", "''")
        filters.append(f"BusinessTypeName eq '{bt}'")
    if params.status:
        st = params.status.replace("'", "''")
        filters.append(f"BusinessStatusText eq '{st}'")
    if params.council:
        council_map = {"NR": "Nationalrat", "SR": "Ständerat"}
        council_name = council_map.get(params.council.upper(), params.council)
        filters.append(f"SubmissionCouncilName eq '{council_name}'")
    if params.submitted_after:
        # OData datetime filter
        dt_ms = int(
            datetime.strptime(params.submitted_after, "%Y-%m-%d")
            .replace(tzinfo=timezone.utc)
            .timestamp()
            * 1000
        )
        filters.append(f"SubmissionDate gt datetime'{params.submitted_after}T00:00:00'")

    try:
        results = await _odata_get(
            "Business",
            filters=filters,
            orderby="SubmissionDate desc",
            top=params.limit,
            skip=params.offset,
        )
    except httpx.HTTPStatusError as e:
        return f"Fehler beim Abrufen der Daten: HTTP {e.response.status_code}"
    except httpx.TimeoutException:
        return "Fehler: Zeitüberschreitung beim Abrufen der Parlamentsdaten."

    if not results:
        return "Keine Vorstösse gefunden für die angegebenen Suchkriterien."

    cleaned = [_fmt_business(b) for b in results]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "count": len(cleaned),
                "offset": params.offset,
                "results": cleaned,
            },
            indent=2,
            ensure_ascii=False,
        )

    # Markdown output
    lines = [
        f"## Parlamentarische Vorstösse ({len(cleaned)} Treffer)\n",
    ]
    if params.keyword:
        kws = params.keyword
        if params.keyword2:
            kws += f" + {params.keyword2}"
        lines.append(f"**Suche:** {kws}")
    if params.status:
        lines.append(f"**Status:** {params.status}")
    lines.append("")

    for b in cleaned:
        lines.append(f"### {b['short_number']} – {b['title']}")
        lines.append(f"- **Typ:** {b['type']}")
        lines.append(f"- **Status:** {b['status']} ({b['status_date']})")
        lines.append(f"- **Eingereicht von:** {b['submitted_by']} ({b['council']})")
        lines.append(f"- **Datum:** {b['submission_date']}")
        if b["department"]:
            lines.append(f"- **Departement:** {b['department']}")
        if b["description"]:
            lines.append(f"- **Beschreibung:** {b['description']}")
        lines.append(
            f"- **Curia Vista:** https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={b['id']}"
        )
        lines.append("")

    if len(cleaned) == params.limit:
        lines.append(
            f"*Weitere Ergebnisse mit `offset={params.offset + params.limit}` abrufbar.*"
        )

    return "\n".join(lines)


@mcp.tool(
    name="parlament_get_business",
    annotations={
        "title": "Get Parliamentary Business Detail",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_get_business(params: GetBusinessInput) -> str:
    """Fetch full details of a single parliamentary business by its Curia Vista ID.

    Use this after a search to get complete information including the initial
    situation, proceedings, motion text, and Federal Council response.

    Args:
        params (GetBusinessInput): Business ID and language.

    Returns:
        str: Full business details including texts, status history, and links.
    """
    try:
        url = f"{BASE_URL}/Business(ID={params.business_id},Language='{params.language.value}')"
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(url, params={"$format": "json"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Vorstoss mit ID {params.business_id} nicht gefunden."
        return f"API-Fehler: HTTP {e.response.status_code}"
    except httpx.TimeoutException:
        return "Zeitüberschreitung beim Abrufen der Daten."

    b = data.get("d", data)
    if not b or not b.get("ID"):
        return f"Vorstoss mit ID {params.business_id} nicht gefunden."

    lines = [
        f"# {b.get('BusinessShortNumber')} – {b.get('Title')}",
        "",
        f"**Typ:** {b.get('BusinessTypeName')}",
        f"**Status:** {b.get('BusinessStatusText')} ({_parse_date(b.get('BusinessStatusDate'))})",
        f"**Eingereicht von:** {b.get('SubmittedBy')}",
        f"**Rat:** {b.get('SubmissionCouncilName')}",
        f"**Eingereicht am:** {_parse_date(b.get('SubmissionDate'))}",
    ]
    if b.get("ResponsibleDepartmentName"):
        lines.append(f"**Departement:** {b.get('ResponsibleDepartmentName')}")
    lines.append(
        f"**Curia Vista:** https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={b.get('ID')}"
    )

    if b.get("Description"):
        lines += ["", "## Beschreibung", b.get("Description", "")]
    if b.get("InitialSituation"):
        lines += ["", "## Ausgangslage", b.get("InitialSituation", "")]
    if b.get("SubmittedText"):
        lines += ["", "## Vorstosstext", b.get("SubmittedText", "")]
    if b.get("MotionText"):
        lines += ["", "## Motion / Antrag", b.get("MotionText", "")]
    if b.get("FederalCouncilResponseText"):
        lines += ["", "## Antwort des Bundesrats", b.get("FederalCouncilResponseText", "")]
    if b.get("Proceedings"):
        lines += ["", "## Beratungen", b.get("Proceedings", "")]
    if b.get("TagNames"):
        lines += ["", f"**Tags:** {b.get('TagNames')}"]

    return "\n".join(lines)


@mcp.tool(
    name="parlament_search_members",
    annotations={
        "title": "Search Council Members (Parlamentarier)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_search_members(params: SearchMembersInput) -> str:
    """Search for members of the National Council (Nationalrat) or Council of States (Ständerat).

    Useful for finding all Zurich members ('ZH') or members of a specific party.
    Synergy: combine with parlament_search_business to find who submitted motions
    on digitisation or AI in Zurich's political sphere.

    Args:
        params (SearchMembersInput): Search filters including canton, name, council, party.

    Returns:
        str: List of council members with name, council, canton, party, and group.
    """
    filters: list[str] = []
    if params.active_only:
        filters.append("Active eq true")
    if params.canton:
        filters.append(f"CantonAbbreviation eq '{params.canton.upper()}'")
    if params.last_name:
        ln = params.last_name.replace("'", "''")
        filters.append(f"substringof('{ln}',LastName)")
    if params.council:
        council_map = {"NR": "Nationalrat", "SR": "Ständerat"}
        cn = council_map.get(params.council.upper(), params.council)
        filters.append(f"CouncilName eq '{cn}'")
    if params.party:
        pa = params.party.replace("'", "''")
        filters.append(f"PartyAbbreviation eq '{pa}'")

    try:
        results = await _odata_get(
            "MemberCouncil",
            filters=filters,
            orderby="LastName asc",
            top=params.limit,
            skip=params.offset,
        )
    except httpx.HTTPStatusError as e:
        return f"API-Fehler: HTTP {e.response.status_code}"
    except httpx.TimeoutException:
        return "Zeitüberschreitung."

    if not results:
        return "Keine Ratsmitglieder gefunden."

    if params.response_format == ResponseFormat.JSON:
        cleaned = [
            {
                "id": m.get("ID"),
                "name": f"{m.get('FirstName')} {m.get('LastName')}",
                "council": m.get("CouncilAbbreviation"),
                "canton": m.get("CantonAbbreviation"),
                "party": m.get("PartyAbbreviation"),
                "group": m.get("ParlGroupAbbreviation"),
                "active": m.get("Active"),
                "joining": _parse_date(m.get("DateJoining")),
            }
            for m in results
        ]
        return json.dumps({"count": len(cleaned), "results": cleaned}, indent=2, ensure_ascii=False)

    lines = [f"## Ratsmitglieder ({len(results)} Treffer)\n"]
    for m in results:
        name = f"{m.get('FirstName')} {m.get('LastName')}"
        council = m.get("CouncilAbbreviation", "")
        canton = m.get("CantonAbbreviation", "")
        party = m.get("PartyAbbreviation", "")
        group = m.get("ParlGroupAbbreviation", "")
        lines.append(f"- **{name}** ({council}, {canton}) – {party} / {group}")

    return "\n".join(lines)


@mcp.tool(
    name="parlament_get_votes",
    annotations={
        "title": "Get Parliamentary Votes (Abstimmungen)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_get_votes(params: GetVotesInput) -> str:
    """Fetch parliamentary votes (Abstimmungen im Rat) with Ja/Nein meaning.

    Use this to see how the council voted on specific topics like AI regulation,
    education funding, or digitisation projects.

    Args:
        params (GetVotesInput): Keyword, session ID, pagination.

    Returns:
        str: List of votes with business title, session, and Ja/Nein semantics.
    """
    filters: list[str] = []
    if params.keyword:
        kw = params.keyword.replace("'", "''")
        filters.append(f"substringof('{kw}',BusinessTitle)")
    if params.session_id:
        filters.append(f"IdSession eq {params.session_id}")

    try:
        results = await _odata_get(
            "Vote",
            filters=filters,
            orderby="ID desc",
            top=params.limit,
            skip=params.offset,
        )
    except httpx.HTTPStatusError as e:
        return f"API-Fehler: HTTP {e.response.status_code}"
    except httpx.TimeoutException:
        return "Zeitüberschreitung."

    if not results:
        return "Keine Abstimmungen gefunden."

    if params.response_format == ResponseFormat.JSON:
        cleaned = [
            {
                "id": v.get("ID"),
                "business_number": v.get("BusinessShortNumber"),
                "business_title": v.get("BusinessTitle"),
                "session": v.get("SessionName") or v.get("IdSession"),
                "meaning_yes": v.get("MeaningYes"),
                "meaning_no": v.get("MeaningNo"),
                "vote_end": _parse_date(v.get("VoteEnd")),
            }
            for v in results
        ]
        return json.dumps({"count": len(cleaned), "results": cleaned}, indent=2, ensure_ascii=False)

    lines = [f"## Parlamentarische Abstimmungen ({len(results)} Treffer)\n"]
    for v in results:
        lines.append(f"### {v.get('BusinessShortNumber')} – {v.get('BusinessTitle', '')[:80]}")
        lines.append(f"- **Session:** {v.get('SessionName') or v.get('IdSession')}")
        lines.append(f"- **Datum:** {_parse_date(v.get('VoteEnd'))}")
        lines.append(f"- **Ja bedeutet:** {v.get('MeaningYes', '–')}")
        lines.append(f"- **Nein bedeutet:** {v.get('MeaningNo', '–')}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool(
    name="parlament_get_sessions",
    annotations={
        "title": "List Parliamentary Sessions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_get_sessions(params: GetSessionsInput) -> str:
    """List recent parliamentary sessions (Sessionen) with dates.

    Use session IDs from this list to filter votes or transcripts.

    Args:
        params (GetSessionsInput): Limit, offset, format.

    Returns:
        str: List of sessions with ID, name, start/end dates.
    """
    try:
        results = await _odata_get(
            "Session",
            orderby="ID desc",
            top=params.limit,
            skip=params.offset,
        )
    except Exception as e:
        return f"Fehler: {e}"

    if not results:
        return "Keine Sessionen gefunden."

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            [
                {
                    "id": s.get("ID"),
                    "name": s.get("SessionName") or s.get("Abbreviation"),
                    "start": _parse_date(s.get("StartDate")),
                    "end": _parse_date(s.get("EndDate")),
                    "type": s.get("TypeName"),
                    "legislative_period": s.get("LegislativePeriodNumber"),
                }
                for s in results
            ],
            indent=2,
            ensure_ascii=False,
        )

    lines = ["## Parlamentarische Sessionen\n"]
    for s in results:
        name = s.get("SessionName") or s.get("Abbreviation") or f"Session {s.get('ID')}"
        start = _parse_date(s.get("StartDate"))
        end = _parse_date(s.get("EndDate"))
        lp = s.get("LegislativePeriodNumber")
        lines.append(f"- **{name}** (ID: {s.get('ID')}) | {start} – {end} | LP {lp}")
    return "\n".join(lines)


@mcp.tool(
    name="parlament_get_transcripts",
    annotations={
        "title": "Get Debate Transcripts (Ratsdebatten)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_get_transcripts(params: GetTranscriptsInput) -> str:
    """Fetch excerpts from parliamentary debate transcripts (Amtliches Bulletin).

    Use this to find what specific councillors said about AI, digitisation in schools,
    or any other topic. Synergy with fedlex-mcp: trace from law text → parliamentary debate.

    Args:
        params (GetTranscriptsInput): Keyword, speaker, session, council, pagination.

    Returns:
        str: Transcript excerpts with speaker, date, council, and text snippet.
    """
    filters: list[str] = []
    if params.keyword:
        kw = params.keyword.replace("'", "''")
        filters.append(f"substringof('{kw}',Text)")
    if params.speaker_name:
        sn = params.speaker_name.replace("'", "''")
        filters.append(f"substringof('{sn}',SpeakerLastName)")
    if params.session_id:
        filters.append(f"IdSession eq {params.session_id}")
    if params.council:
        council_map = {"NR": "Nationalrat", "SR": "Ständerat"}
        cn = council_map.get(params.council.upper(), params.council)
        filters.append(f"CouncilName eq '{cn}'")

    try:
        results = await _odata_get(
            "Transcript",
            filters=filters,
            orderby="MeetingDate desc",
            top=params.limit,
            skip=params.offset,
        )
    except httpx.HTTPStatusError as e:
        return f"API-Fehler: HTTP {e.response.status_code}"
    except httpx.TimeoutException:
        return "Zeitüberschreitung beim Abrufen der Debatten."

    if not results:
        return "Keine Transkripte gefunden für die angegebenen Kriterien."

    if params.response_format == ResponseFormat.JSON:
        cleaned = [
            {
                "speaker": t.get("SpeakerFullName"),
                "function": t.get("SpeakerFunction"),
                "canton": t.get("CantonAbbreviation"),
                "group": t.get("ParlGroupAbbreviation"),
                "council": t.get("CouncilName"),
                "date": t.get("MeetingDate", "")[:10],
                "session": t.get("IdSession"),
                "text_snippet": (t.get("Text") or "")[:500],
            }
            for t in results
        ]
        return json.dumps({"count": len(cleaned), "results": cleaned}, indent=2, ensure_ascii=False)

    lines = [f"## Ratsdebatten ({len(results)} Treffer)\n"]
    for t in results:
        speaker = t.get("SpeakerFullName", "Unbekannt")
        function = t.get("SpeakerFunction", "")
        canton = t.get("CantonAbbreviation", "")
        group = t.get("ParlGroupAbbreviation", "")
        date = (t.get("MeetingDate") or "")[:10]
        text = (t.get("Text") or "")[:400]

        lines.append(f"### {speaker} ({function}, {canton}, {group})")
        lines.append(f"**Datum:** {date} | **Rat:** {t.get('CouncilName', '')} | **Session:** {t.get('IdSession', '')}")
        if t.get("VoteBusinessTitle"):
            lines.append(f"**Vorstoss:** {t.get('VoteBusinessTitle')}")
        lines.append(f"\n> {text}…\n")

    if len(results) == params.limit:
        lines.append(f"*Weitere mit `offset={params.offset + params.limit}` abrufbar.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport=transport)
