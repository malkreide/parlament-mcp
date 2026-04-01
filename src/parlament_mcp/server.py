#!/usr/bin/env python3
"""
parlament-mcp – Schweizer Parlament MCP Server – v0.1.0

AI-nativer Zugang zum Schweizer Bundesparament via Curia Vista OData API:
  · Vorstösse (Motionen, Postulate, Interpellationen, Anfragen)
  · Abstimmungen im Rat
  · Ratsmitglieder (National- und Ständerat)
  · Sessionen
  · Debatten-Transkripte (Amtliches Bulletin)

Kein API-Schlüssel erforderlich. Alle Daten öffentlich zugänglich.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────── Server ────────────────────────────────────────────
mcp = FastMCP("parlament_mcp")

# ─────────────────────────── Konstanten ────────────────────────────────────────
BASE_URL = "https://ws.parlament.ch/odata.svc"
DEFAULT_LANG = "DE"
HTTP_TIMEOUT = 20.0
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Geschäftstyp-IDs (Curia Vista)
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


# ─────────────────────────── Enums ─────────────────────────────────────────────
class Language(StrEnum):
    """Verfügbare Sprachen der Curia Vista API."""
    DE = "DE"
    FR = "FR"
    IT = "IT"


class ResponseFormat(StrEnum):
    """Ausgabeformat für Tool-Antworten."""
    MARKDOWN = "markdown"
    JSON = "json"


# ─────────────────────────── Hilfsfunktionen ───────────────────────────────────
async def _odata_get(
    entity: str,
    filters: list[str] | None = None,
    orderby: str | None = None,
    top: int = DEFAULT_LIMIT,
    skip: int = 0,
    select: list[str] | None = None,
    lang: str = DEFAULT_LANG,
) -> list[dict[str, Any]]:
    """OData-GET-Anfrage ausführen und Ergebnisliste zurückgeben."""
    params: dict[str, str] = {
        "$format": "json",
        "$top": str(min(top, MAX_LIMIT)),
    }
    if skip:
        params["$skip"] = str(skip)

    # Immer nach Sprache filtern
    lang_filter = f"Language eq '{lang}'"
    all_filters = [lang_filter] + (filters or [])
    params["$filter"] = " and ".join(f"({f})" for f in all_filters)

    if orderby:
        params["$orderby"] = orderby
    if select:
        params["$select"] = ",".join(select)

    url = f"{BASE_URL}/{entity}"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = client.build_request("GET", url, params=params)
        response = await client.send(resp)
        response.raise_for_status()
        data = response.json()
        return data.get("d", [])


def _handle_error(e: Exception) -> str:
    """Einheitliche, handlungsorientierte Fehlermeldungen (auf Deutsch)."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 404:
            return "Fehler: Ressource nicht gefunden. Bitte ID oder Parameter prüfen."
        if code == 429:
            return "Fehler: Rate-Limit erreicht. Bitte kurz warten und erneut versuchen."
        if code in (503, 502):
            return "Fehler: Dienst vorübergehend nicht verfügbar. Bitte erneut versuchen."
        return f"Fehler: API-Anfrage fehlgeschlagen (HTTP {code})."
    if isinstance(e, httpx.TimeoutException):
        return "Fehler: Zeitüberschreitung. Der Dienst antwortet nicht. Bitte erneut versuchen."
    return f"Fehler: Unerwarteter Fehler ({type(e).__name__}): {e}"


def _parse_date(ms_date: str | None) -> str:
    """OData /Date(...)/ in ISO-String umwandeln."""
    if not ms_date:
        return ""
    try:
        ms = int(ms_date.replace("/Date(", "").replace(")/", ""))
        return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d")
    except Exception:
        return ms_date


def _fmt_business(b: dict) -> dict:
    """Geschäft-Dict für Tool-Antworten aufbereiten."""
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


# ─────────────────────────── Eingabemodelle ────────────────────────────────────
class SearchBusinessInput(BaseModel):
    """Eingabe für die Suche nach parlamentarischen Vorstössen."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: str | None = Field(
        default=None,
        description=(
            "Stichwort für die Titelsuche. "
            "Beispiele: 'Künstliche Intelligenz', 'Bildung', 'Digitalisierung', 'Schule', 'KI'"
        ),
        max_length=200,
    )
    keyword2: str | None = Field(
        default=None,
        description="Zweites Stichwort (UND-verknüpft). Beispiel: 'Schule' wenn keyword='KI'.",
        max_length=200,
    )
    business_type: str | None = Field(
        default=None,
        description=(
            "Nach Geschäftstyp filtern. Gültige Werte: 'Motion', 'Postulat', 'Interpellation', "
            "'Parlamentarische Initiative', 'Standesinitiative', 'Anfrage', 'Einfache Anfrage'"
        ),
    )
    status: str | None = Field(
        default=None,
        description=(
            "Nach Status filtern. Häufige Werte: 'Eingereicht' (hängig), "
            "'Erledigt' (abgeschlossen), 'Überwiesen an den Bundesrat', "
            "'Angenommen', 'Abgelehnt'"
        ),
    )
    submitted_after: str | None = Field(
        default=None,
        description="Vorstösse nach diesem Datum (ISO-Format JJJJ-MM-TT).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    council: str | None = Field(
        default=None,
        description="Nach Rat filtern: 'NR' (Nationalrat) oder 'SR' (Ständerat).",
    )
    limit: int = Field(
        default=20,
        description="Maximale Anzahl Ergebnisse (1–100).",
        ge=1,
        le=MAX_LIMIT,
    )
    offset: int = Field(default=0, description="Offset für Paginierung.", ge=0)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' (lesbar) oder 'json' (strukturiert).",
    )


class GetBusinessInput(BaseModel):
    """Eingabe zum Abrufen eines einzelnen Vorstosses nach ID."""

    model_config = ConfigDict(extra="forbid")

    business_id: int = Field(
        ..., description="Numerische Curia Vista Geschäfts-ID (z.B. 20254750)."
    )
    language: Language = Field(default=Language.DE, description="Antwortsprache.")


class SearchMembersInput(BaseModel):
    """Eingabe für die Suche nach Ratsmitgliedern (Parlamentarier·innen)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    canton: str | None = Field(
        default=None,
        description="Nach Kanton filtern, z.B. 'ZH', 'BE', 'GE', 'AG'.",
        max_length=2,
    )
    last_name: str | None = Field(
        default=None,
        description="Nach Nachname filtern (Teilübereinstimmung).",
        max_length=100,
    )
    council: str | None = Field(
        default=None,
        description="Nach Rat filtern: 'NR' (Nationalrat) oder 'SR' (Ständerat).",
    )
    party: str | None = Field(
        default=None,
        description="Nach Partei filtern, z.B. 'SP', 'SVP', 'FDP', 'Mitte', 'Grüne'.",
        max_length=20,
    )
    active_only: bool = Field(
        default=True,
        description="Nur aktive Ratsmitglieder zurückgeben.",
    )
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetVotesInput(BaseModel):
    """Eingabe zum Abrufen parlamentarischer Abstimmungen."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: str | None = Field(
        default=None,
        description="Stichwort im Geschäftstitel der Abstimmung (z.B. 'Bildung', 'KI').",
        max_length=200,
    )
    session_id: int | None = Field(
        default=None,
        description="Abstimmungen einer bestimmten Session filtern.",
    )
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetSessionsInput(BaseModel):
    """Eingabe zum Auflisten parlamentarischer Sessionen."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetTranscriptsInput(BaseModel):
    """Eingabe zum Abrufen von Debatten-Transkripten."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: str | None = Field(
        default=None,
        description="Stichwort im Transkripttext (z.B. 'KI', 'Schule').",
        max_length=200,
    )
    speaker_name: str | None = Field(
        default=None,
        description="Nach Nachname des Redners filtern.",
        max_length=100,
    )
    session_id: int | None = Field(
        default=None,
        description="Transkripte einer bestimmten Session filtern.",
    )
    council: str | None = Field(
        default=None,
        description="Nach Rat filtern: 'NR' oder 'SR'.",
    )
    limit: int = Field(default=15, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ─────────────────────────── Tools ─────────────────────────────────────────────


@mcp.tool(
    name="parlament_search_business",
    annotations={
        "title": "Parlamentarische Vorstösse suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_search_business(params: SearchBusinessInput) -> str:
    """Parlamentarische Vorstösse suchen (Motionen, Interpellationen, Postulate usw.).

    Durchsucht Curia Vista Geschäftsdaten von ws.parlament.ch. Geeignet zum
    Finden hängiger Vorstösse zu KI in der Bildung, Digitalisierungsinitiativen
    oder beliebigen Politikthemen.

    Anker-Abfrage: 'Welche Vorstösse zu KI in der Schule sind hängig?'
    → keyword='KI', keyword2='Schule', status='Eingereicht'
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
        filters.append(f"SubmissionDate gt datetime'{params.submitted_after}T00:00:00'")

    try:
        results = await _odata_get(
            "Business",
            filters=filters,
            orderby="SubmissionDate desc",
            top=params.limit,
            skip=params.offset,
        )
    except Exception as e:
        return _handle_error(e)

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

    # Markdown-Ausgabe
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
        "title": "Vorstoss-Details abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_get_business(params: GetBusinessInput) -> str:
    """Vollständige Details eines parlamentarischen Vorstosses nach Curia Vista ID abrufen.

    Nach einer Suche verwenden, um vollständige Informationen inkl. Ausgangslage,
    Vorstosstext und Antwort des Bundesrats zu erhalten.
    """
    try:
        url = f"{BASE_URL}/Business(ID={params.business_id},Language='{params.language.value}')"
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(url, params={"$format": "json"})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return _handle_error(e)

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
        "title": "Ratsmitglieder suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_search_members(params: SearchMembersInput) -> str:
    """National- und Ständeräte suchen.

    Nützlich um alle Zürcher Ratsmitglieder ('ZH') oder Mitglieder einer
    bestimmten Partei zu finden. Synergie: mit parlament_search_business
    kombinieren, um Urheber von Vorstössen zu identifizieren.
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
    except Exception as e:
        return _handle_error(e)

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
        "title": "Parlamentarische Abstimmungen abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_get_votes(params: GetVotesInput) -> str:
    """Parlamentarische Abstimmungen (im Rat) mit Ja/Nein-Bedeutung abrufen.

    Zeigt, wie der Rat über bestimmte Themen wie KI-Regulierung,
    Bildungsfinanzierung oder Digitalisierungsprojekte abgestimmt hat.
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
    except Exception as e:
        return _handle_error(e)

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
        "title": "Parlamentarische Sessionen auflisten",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_get_sessions(params: GetSessionsInput) -> str:
    """Aktuelle parlamentarische Sessionen mit Daten auflisten.

    Session-IDs aus dieser Liste zum Filtern von Abstimmungen oder
    Transkripten verwenden.
    """
    try:
        results = await _odata_get(
            "Session",
            orderby="ID desc",
            top=params.limit,
            skip=params.offset,
        )
    except Exception as e:
        return _handle_error(e)

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
        "title": "Debatten-Transkripte abrufen (Amtliches Bulletin)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parlament_get_transcripts(params: GetTranscriptsInput) -> str:
    """Auszüge aus parlamentarischen Debatten-Transkripten (Amtliches Bulletin) abrufen.

    Finden, was bestimmte Ratsmitglieder zu KI, Digitalisierung in der Schule
    oder anderen Themen gesagt haben. Synergie mit fedlex-mcp: vom Gesetzestext
    zur parlamentarischen Debatte.
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
    except Exception as e:
        return _handle_error(e)

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


# ─────────────────────────── Einstiegspunkt ────────────────────────────────────
if __name__ == "__main__":
    if "--http" in sys.argv:
        port = 8080
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
