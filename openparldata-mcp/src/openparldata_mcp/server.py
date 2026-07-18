#!/usr/bin/env python3
"""openparldata-mcp – Schweizer Kantons- und Gemeindeparlamente (subnational).

AI-nativer Zugang zur **subnationalen** politischen Ebene der Schweiz über die
OpenParlData.ch-API: 26 Kantone und ~70 Gemeindeparlamente. Vorstösse,
Dokumente inkl. PDF-Volltext, Personen, Interessenbindungen, Abstimmungen und
Sitzungen.

Abgrenzung (nicht verhandelbar): Dieser Server deckt AUSSCHLIESSLICH die
subnationale Ebene ab. Die Bundesebene (``body_key="CHE"``) wird von allen Tools
aktiv abgewiesen und auf ``parlament-mcp`` (Curia Vista) bzw. für
Interessenbindungen auf ``lobbywatch-mcp`` verwiesen.

Architektur: ARCH A (Live-API-only). Kein API-Schlüssel. Lizenz der Daten:
CC BY 4.0 – "Source: OpenParlData.ch".
"""

from __future__ import annotations

import asyncio
import functools
import time
from contextlib import asynccontextmanager
from typing import Any, Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from openparldata_mcp import bodies as body_cache
from openparldata_mcp.client import (
    aclose,
    api_get,
    get_client,
    last_success_epoch,
    unwrap,
)
from openparldata_mcp.config import (
    BASE_URL,
    DATA_ATTRIBUTION,
    DATA_LICENSE,
    DATA_SOURCE,
    FEDERAL_INTERESTS_REDIRECT,
    MAX_LIMIT,
    PROTOCOL_VERSION,
    Settings,
    VOTES_MAX_LIMIT,
    warn_on_dangerous_binding,
)
from openparldata_mcp.localize import localize
from openparldata_mcp.logging_setup import configure_logging, get_logger

configure_logging()
_logger = get_logger("openparldata_mcp")


# ─────────────────────────── Lifespan ──────────────────────────────────────────
@asynccontextmanager
async def _lifespan(_server: FastMCP):
    """Body-Cache vorwärmen und HTTP-Pool sauber abbauen."""
    try:
        try:
            await body_cache.ensure_loaded()
        except Exception as exc:  # Vorwärmen ist best-effort; lazy Load bleibt möglich
            _logger.warning("body_cache_prewarm_failed", error=type(exc).__name__)
        yield
    finally:
        await aclose()


mcp = FastMCP("openparldata_mcp", lifespan=_lifespan)


# ─────────────────────────── Instrumentierung ──────────────────────────────────
def _instrument(name: str):
    """Pro Tool-Call strukturiertes Logging + Übersetzung unerwarteter Fehler.

    ``ToolError`` (bereits sprechend) wird durchgereicht; alles andere wird
    maskiert, damit kein Stacktrace an den Client leakt.
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(params, ctx: Context | None = None):
            log = _logger.bind(tool=name)
            log.info("tool_invoked")
            try:
                result = await fn(params, ctx)
            except ToolError:
                log.warning("tool_failed")
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("tool_error", error=type(exc).__name__)
                raise ToolError(f"Unerwarteter Fehler ({type(exc).__name__}).") from exc
            log.info("tool_succeeded")
            return result

        return wrapper

    return decorator


# ─────────────────────────── Envelope / Modelle ────────────────────────────────
class Envelope(BaseModel):
    """Konsistenter Envelope mit Herkunft/Lizenz für alle Listen-Tools."""

    source: str = DATA_SOURCE
    license: str = DATA_LICENSE
    attribution: str = DATA_ATTRIBUTION
    provenance: Literal["live_api"] = "live_api"
    count: int = 0
    total_available: int | None = None
    offset: int = 0
    note: str | None = None


class BodyItem(BaseModel):
    body_key: str
    name: str | None = None
    type: str | None = None
    canton_key: str | None = None


class BodiesResponse(Envelope):
    results: list[BodyItem] = Field(default_factory=list)


class AffairSummary(BaseModel):
    id: int | None = None
    body_key: str | None = None
    number: str | None = None
    title: str | None = None
    type_name: str | None = None
    state_name: str | None = None
    begin_date: str | None = None
    end_date: str | None = None
    active: bool | None = None
    url_external: str | None = None


class AffairsResponse(Envelope):
    results: list[AffairSummary] = Field(default_factory=list)


class AffairDetail(BaseModel):
    found: bool = True
    source: str = DATA_SOURCE
    license: str = DATA_LICENSE
    attribution: str = DATA_ATTRIBUTION
    id: int | None = None
    body_key: str | None = None
    number: str | None = None
    title: str | None = None
    title_long: str | None = None
    type_name: str | None = None
    state_name: str | None = None
    begin_date: str | None = None
    end_date: str | None = None
    active: bool | None = None
    url_external: str | None = None
    expanded: dict[str, Any] | None = None


class DocumentItem(BaseModel):
    id: int | None = None
    name: str | None = None
    category: str | None = None
    format: str | None = None
    date: str | None = None
    url: str | None = None
    text: str | None = None
    text_truncated: bool = False
    text_total_chars: int | None = None


class DocumentsResponse(Envelope):
    affair_id: int | None = None
    results: list[DocumentItem] = Field(default_factory=list)


class BodyTopic(BaseModel):
    body_key: str
    name: str | None = None
    type: str | None = None
    match_count: int = 0


class CompareResponse(Envelope):
    search: str
    results: list[BodyTopic] = Field(default_factory=list)


class PersonItem(BaseModel):
    id: int | None = None
    body_key: str | None = None
    fullname: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    party: str | None = None
    parliamentary_group_name: str | None = None
    active: bool | None = None
    electoral_district: str | None = None


class PersonsResponse(Envelope):
    results: list[PersonItem] = Field(default_factory=list)


class PersonDetail(PersonItem):
    found: bool = True
    source: str = DATA_SOURCE
    license: str = DATA_LICENSE
    attribution: str = DATA_ATTRIBUTION
    email: str | None = None
    occupation: str | None = None
    gender: str | None = None
    website_parliament_url: str | None = None
    expanded: dict[str, Any] | None = None


class InterestItem(BaseModel):
    id: int | None = None
    person_id: int | None = None
    organisation: str | None = None
    role_name: str | None = None
    group: str | None = None
    type: str | None = None
    place: str | None = None
    begin_date: str | None = None
    end_date: str | None = None


class InterestsResponse(Envelope):
    # Rohdaten mit Parsing-Artefakten (z.B. Jahreszahl im Organisationsfeld);
    # type/role_name/group häufig leer. Deshalb explizit als ungeprüft markiert.
    data_quality: Literal["unverified_source_data"] = "unverified_source_data"
    results: list[InterestItem] = Field(default_factory=list)


class VotingItem(BaseModel):
    id: int | None = None
    body_key: str | None = None
    title: str | None = None
    date: str | None = None
    affair_id: int | None = None
    affair_title: str | None = None
    decision: str | None = None
    results_yes: int | None = None
    results_no: int | None = None
    results_abstention: int | None = None
    results_absent: int | None = None
    meaning_of_yes: str | None = None
    meaning_of_no: str | None = None
    url_external: str | None = None


class VotingsResponse(Envelope):
    results: list[VotingItem] = Field(default_factory=list)


class VoteItem(BaseModel):
    person_id: int | None = None
    person_fullname: str | None = None
    person_party: str | None = None
    parliamentary_group_name: str | None = None
    vote: str | None = None
    vote_display: str | None = None


class VotingResultsResponse(Envelope):
    voting_id: int
    voting: VotingItem | None = None
    results: list[VoteItem] = Field(default_factory=list)


class MeetingItem(BaseModel):
    id: int | None = None
    body_key: str | None = None
    name: str | None = None
    number: str | None = None
    type: str | None = None
    begin_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    state: str | None = None
    url_external: str | None = None


class MeetingsResponse(Envelope):
    results: list[MeetingItem] = Field(default_factory=list)


class SourceStatus(BaseModel):
    source: str = DATA_SOURCE
    license: str = DATA_LICENSE
    attribution: str = DATA_ATTRIBUTION
    base_url: str = BASE_URL
    reachable: bool
    latency_ms: int | None = None
    last_successful_fetch: str | None = None
    body_cache_loaded: bool = False
    body_cache_age_seconds: int | None = None
    body_count: int | None = None
    note: str | None = None


# ─────────────────────────── Record-Formatter ──────────────────────────────────
def _iso_date(value: Any) -> str | None:
    if not value:
        return None
    return str(value)[:10]


def _fmt_affair(a: dict) -> AffairSummary:
    return AffairSummary(
        id=a.get("id"),
        body_key=a.get("body_key"),
        number=a.get("number"),
        title=localize(a.get("title")),
        type_name=localize(a.get("type_name")),
        state_name=localize(a.get("state_name")),
        begin_date=_iso_date(a.get("begin_date")),
        end_date=_iso_date(a.get("end_date")),
        active=a.get("active"),
        url_external=localize(a.get("url_external")),
    )


def _fmt_person(p: dict) -> PersonItem:
    return PersonItem(
        id=p.get("id"),
        body_key=p.get("body_key"),
        fullname=localize(p.get("fullname")),
        firstname=p.get("firstname"),
        lastname=p.get("lastname"),
        party=localize(p.get("party")),
        parliamentary_group_name=localize(p.get("parliamentary_group_name")),
        active=p.get("active"),
        electoral_district=localize(p.get("electoral_district")),
    )


def _fmt_interest(i: dict) -> InterestItem:
    return InterestItem(
        id=i.get("id"),
        person_id=i.get("person_id"),
        organisation=localize(i.get("name")),
        role_name=localize(i.get("role_name")),
        group=localize(i.get("group")),
        type=localize(i.get("type")),
        place=localize(i.get("place")),
        begin_date=_iso_date(i.get("begin_date")),
        end_date=_iso_date(i.get("end_date")),
    )


def _fmt_voting(v: dict) -> VotingItem:
    return VotingItem(
        id=v.get("id"),
        body_key=v.get("body_key"),
        title=localize(v.get("title")),
        date=_iso_date(v.get("date")),
        affair_id=v.get("affair_id"),
        affair_title=localize(v.get("affair_title")),
        decision=localize(v.get("decision")),
        results_yes=v.get("results_yes"),
        results_no=v.get("results_no"),
        results_abstention=v.get("results_abstention"),
        results_absent=v.get("results_absent"),
        meaning_of_yes=localize(v.get("meaning_of_yes")),
        meaning_of_no=localize(v.get("meaning_of_no")),
        url_external=localize(v.get("url_external")),
    )


def _fmt_vote(v: dict) -> VoteItem:
    return VoteItem(
        person_id=v.get("person_id"),
        person_fullname=localize(v.get("person_fullname")),
        person_party=localize(v.get("person_party")),
        parliamentary_group_name=localize(v.get("person_parliamentary_group_name")),
        vote=v.get("vote"),
        vote_display=localize(v.get("vote_display")),
    )


def _fmt_meeting(m: dict) -> MeetingItem:
    return MeetingItem(
        id=m.get("id"),
        body_key=m.get("body_key"),
        name=localize(m.get("name")),
        number=localize(m.get("number")),
        type=localize(m.get("type")),
        begin_date=_iso_date(m.get("begin_date")),
        end_date=_iso_date(m.get("end_date")),
        location=localize(m.get("location")),
        state=localize(m.get("state")),
        url_external=localize(m.get("url_external")),
    )


# ─────────────────────────── Eingabemodelle ────────────────────────────────────
SearchMode = Literal["partial", "exact", "natural", "boolean"]
BodyType = Literal["canton", "municipality"]
_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class ListBodiesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    search: str | None = Field(
        default=None,
        description="Freitext-Filter auf Name/Key der Körperschaft, z.B. 'Zürich', 'Winter'.",
        max_length=100,
    )
    body_type: BodyType | None = Field(
        default=None,
        description="Auf 'canton' (26 Kantone) oder 'municipality' (~70 Gemeindeparlamente) einschränken.",
    )


class SearchAffairsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    body_key: str = Field(
        ...,
        description="Körperschaft (Pflicht), z.B. '261' (Stadt Zürich), 'ZH' (Kanton Zürich), '230' (Winterthur).",
        min_length=1,
        max_length=10,
    )
    search: str | None = Field(
        default=None,
        description="Suchbegriff, z.B. 'Tagesschule', 'Velostrasse', 'Klima'.",
        max_length=300,
    )
    search_mode: SearchMode = Field(
        default="partial",
        description="'partial' (Teilstring, Default), 'exact', 'natural' (Volltext), 'boolean' (& | ! Operatoren).",
    )
    search_scope: str = Field(
        default="metadata",
        description="Suchbereich: 'metadata' (Default), 'docs', 'texts' (PDF-Volltext), 'all' oder Kombination 'metadata,docs'.",
        max_length=60,
    )
    date_from: str | None = Field(
        default=None, description="Von-Datum (JJJJ-MM-TT), z.B. '2024-01-01'.", pattern=_DATE_PATTERN
    )
    date_to: str | None = Field(
        default=None, description="Bis-Datum (JJJJ-MM-TT).", pattern=_DATE_PATTERN
    )
    sort_by: str = Field(
        default="-begin_date",
        description="Sortierfelder (Komma-getrennt, '-' = absteigend). Default: '-begin_date' (neueste zuerst).",
        max_length=100,
    )
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT, strict=True)
    offset: int = Field(default=0, ge=0, strict=True)


class GetAffairInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    affair_id: int = Field(..., description="Numerische Affair-ID (aus oparl_search_affairs).", gt=0, strict=True)
    expand: str | None = Field(
        default=None,
        description="Relationen expandieren (Komma-getrennt), z.B. 'votings', 'persons', 'docs'.",
        max_length=200,
    )


class GetAffairDocumentsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    affair_id: int = Field(..., description="Numerische Affair-ID (aus oparl_search_affairs).", gt=0, strict=True)
    include_text: bool = Field(
        default=True,
        description="PDF-Volltext (Feld 'text') mitliefern – das wertvollste Feld dieses Servers.",
    )
    max_chars: int = Field(
        default=8000,
        description="Maximale Zeichen pro Dokument-Volltext. Bei Überlänge wird explizit trunkiert.",
        ge=200,
        le=200_000,
        strict=True,
    )


class CompareBodiesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    search: str = Field(
        ..., description="Thema, das über Körperschaften hinweg verglichen wird, z.B. 'Tagesschule'.",
        min_length=1, max_length=300,
    )
    body_type: BodyType | None = Field(
        default="municipality",
        description="Vergleichsgruppe: 'municipality' (Gemeinden, Default) oder 'canton'.",
    )
    date_from: str | None = Field(
        default=None, description="Nur Vorstösse ab diesem Datum zählen (JJJJ-MM-TT).", pattern=_DATE_PATTERN
    )
    top: int = Field(
        default=15, description="Wie viele Körperschaften (nach Trefferzahl) zurückgeben.", ge=1, le=97, strict=True
    )


class SearchPersonsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    body_key: str = Field(
        ..., description="Körperschaft (Pflicht), z.B. '261' (Stadt Zürich).", min_length=1, max_length=10
    )
    party: str | None = Field(default=None, description="Partei-Filter (Teilstring), z.B. 'SP', 'GLP'.", max_length=60)
    active: bool | None = Field(default=None, description="Nur aktive Mandatsträger·innen (True) bzw. ehemalige (False).")
    search: str | None = Field(default=None, description="Namenssuche (Teilstring), z.B. 'Müller'.", max_length=100)
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT, strict=True)
    offset: int = Field(default=0, ge=0, strict=True)


class GetPersonInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    person_id: int = Field(..., description="Numerische Personen-ID (aus oparl_search_persons).", gt=0, strict=True)
    expand: str | None = Field(
        default=None,
        description="Relationen expandieren (Komma-getrennt), z.B. 'interests', 'memberships', 'affairs'.",
        max_length=200,
    )


class GetPersonInterestsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: int = Field(..., description="Numerische Personen-ID (aus oparl_search_persons).", gt=0, strict=True)


class SearchInterestsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    body_key: str = Field(
        ..., description="Körperschaft (Pflicht), z.B. 'ZH' (Kanton Zürich).", min_length=1, max_length=10
    )
    search: str | None = Field(
        default=None, description="Organisation/Stichwort, z.B. 'Krankenkasse', 'Verband'.", max_length=200
    )
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT, strict=True)
    offset: int = Field(default=0, ge=0, strict=True)


class GetVotingsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    affair_id: int | None = Field(
        default=None, description="Abstimmungen zu einem Geschäft (bevorzugt).", gt=0, strict=True
    )
    body_key: str | None = Field(
        default=None, description="Alternativ: alle Abstimmungen einer Körperschaft, z.B. '261'.", max_length=10
    )
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT, strict=True)
    offset: int = Field(default=0, ge=0, strict=True)


class GetVotingResultsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voting_id: int = Field(
        ...,
        description="Pflicht: numerische Abstimmungs-ID (aus oparl_get_votings). Einzelstimmen gibt es nur pro Abstimmung.",
        gt=0,
        strict=True,
    )
    limit: int = Field(
        default=200,
        description=f"Maximale Anzahl Einzelstimmen (hart auf {VOTES_MAX_LIMIT} gedeckelt).",
        ge=1,
        le=VOTES_MAX_LIMIT,
        strict=True,
    )
    offset: int = Field(default=0, ge=0, strict=True)


class SearchMeetingsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    body_key: str = Field(
        ..., description="Körperschaft (Pflicht), z.B. '261' (Stadt Zürich).", min_length=1, max_length=10
    )
    date_from: str | None = Field(default=None, description="Von-Datum (JJJJ-MM-TT).", pattern=_DATE_PATTERN)
    date_to: str | None = Field(default=None, description="Bis-Datum (JJJJ-MM-TT).", pattern=_DATE_PATTERN)
    limit: int = Field(default=20, ge=1, le=MAX_LIMIT, strict=True)
    offset: int = Field(default=0, ge=0, strict=True)


class SourceStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def _fmt_epoch(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


# ─────────────────────────── Tools ─────────────────────────────────────────────
@mcp.tool(
    name="oparl_list_bodies",
    annotations={"title": "Körperschaften auflisten", **_ANNOTATIONS},
)
@_instrument("oparl_list_bodies")
async def oparl_list_bodies(params: ListBodiesInput, ctx: Context | None = None) -> BodiesResponse:
    """Kantone und Gemeindeparlamente auflisten und deren body_key ermitteln.

    Erster Schritt jeder Recherche: liefert die gültigen ``body_key``-Werte für
    alle anderen Tools. Deckt 26 Kantone und ~70 Gemeindeparlamente ab; die
    Bundesebene ist nicht enthalten.

    <example>search="Zürich" liefert u.a. '261' (Stadt Zürich, city), 'ZH'
    (Kanton Zürich, canton) und '230' (Winterthur, city).</example>
    """
    items = await body_cache.list_bodies(search=params.search, body_type=params.body_type)
    results = [BodyItem(body_key=b.body_key, name=b.name, type=b.type, canton_key=b.canton_key) for b in items]
    note = None if results else "Keine Körperschaft passt zum Filter. Ohne 'search' werden alle gelistet."
    return BodiesResponse(count=len(results), total_available=len(results), results=results, note=note)


@mcp.tool(
    name="oparl_search_affairs",
    annotations={"title": "Vorstösse/Geschäfte suchen", **_ANNOTATIONS},
)
@_instrument("oparl_search_affairs")
async def oparl_search_affairs(params: SearchAffairsInput, ctx: Context | None = None) -> AffairsResponse:
    """Parlamentarische Geschäfte/Vorstösse einer Körperschaft durchsuchen.

    <use_case>Politische Recherche auf Kantons-/Gemeindeebene: hängige oder
    erledigte Vorstösse zu einem Thema finden.</use_case>

    <important_notes>``search_scope='texts'`` durchsucht den PDF-Volltext (nicht
    nur Titel/Metadaten). Ergebnisse standardmässig neueste zuerst
    (``sort_by='-begin_date'``).</important_notes>

    <example>body_key="261", search="Tagesschule", date_from="2024-01-01" →
    Vorstösse zu Tagesschulen im Gemeinderat der Stadt Zürich seit 2024.</example>
    """
    body = await body_cache.resolve_body(params.body_key)
    query: dict[str, Any] = {
        "body_key": body.body_key,
        "search": params.search,
        "search_mode": params.search_mode,
        "search_scope": params.search_scope,
        "date_from": params.date_from,
        "date_to": params.date_to,
        "sort_by": params.sort_by,
        "limit": params.limit,
        "offset": params.offset,
    }
    payload = await api_get("/affairs/", query)
    rows, meta = unwrap(payload)
    results = [_fmt_affair(a) for a in rows]
    note = None if results else f"Keine Geschäfte in '{body.name}' für die Suchkriterien gefunden."
    return AffairsResponse(
        count=len(results),
        total_available=meta.get("total_records"),
        offset=params.offset,
        results=results,
        note=note,
    )


@mcp.tool(
    name="oparl_get_affair",
    annotations={"title": "Geschäft-Details abrufen", **_ANNOTATIONS},
)
@_instrument("oparl_get_affair")
async def oparl_get_affair(params: GetAffairInput, ctx: Context | None = None) -> AffairDetail:
    """Vollständige Details eines Geschäfts nach ID abrufen.

    <use_case>Nach einer Suche verwenden, um Langtitel, Status und – via
    ``expand`` – zugehörige Abstimmungen oder Personen zu erhalten.</use_case>

    <example>affair_id=334542, expand="votings" für ein Geschäft der Stadt
    Zürich samt Abstimmungen.</example>
    """
    payload = await api_get(f"/affairs/{params.affair_id}", {"expand": params.expand})
    rows, _meta = unwrap(payload)
    if not rows:
        return AffairDetail(found=False, id=params.affair_id)
    a = rows[0]
    expanded = {
        k: a[k]
        for k in (params.expand or "").split(",")
        if k.strip() and isinstance(a.get(k.strip()), (list, dict))
    } or None
    return AffairDetail(
        found=True,
        id=a.get("id"),
        body_key=a.get("body_key"),
        number=a.get("number"),
        title=localize(a.get("title")),
        title_long=localize(a.get("title_long")),
        type_name=localize(a.get("type_name")),
        state_name=localize(a.get("state_name")),
        begin_date=_iso_date(a.get("begin_date")),
        end_date=_iso_date(a.get("end_date")),
        active=a.get("active"),
        url_external=localize(a.get("url_external")),
        expanded=expanded,
    )


@mcp.tool(
    name="oparl_get_affair_documents",
    annotations={"title": "Dokumente + PDF-Volltext abrufen", **_ANNOTATIONS},
)
@_instrument("oparl_get_affair_documents")
async def oparl_get_affair_documents(
    params: GetAffairDocumentsInput, ctx: Context | None = None
) -> DocumentsResponse:
    """Dokumente eines Geschäfts inkl. extrahiertem PDF-Volltext abrufen.

    Das Feld ``text`` enthält den extrahierten Volltext – das wertvollste Feld
    dieses Servers. Bei Überlänge wird NICHT stillschweigend gekürzt, sondern
    explizit mit ``text_truncated=true`` und ``text_total_chars`` markiert.

    <example>affair_id=334542, include_text=true → Weisungstext zu einem
    Tagesschul-Umbau der Stadt Zürich im Volltext.</example>
    """
    payload = await api_get(f"/affairs/{params.affair_id}/docs", {"limit": 100})
    rows, meta = unwrap(payload)
    results: list[DocumentItem] = []
    for d in rows:
        text = d.get("text") if params.include_text else None
        truncated = False
        total_chars = None
        if isinstance(text, str):
            total_chars = len(text)
            if total_chars > params.max_chars:
                text = text[: params.max_chars]
                truncated = True
        results.append(
            DocumentItem(
                id=d.get("id"),
                name=localize(d.get("name")),
                category=localize(d.get("category")) or localize(d.get("category_harmonized")),
                format=localize(d.get("format")),
                date=_iso_date(d.get("date")),
                url=localize(d.get("url")) or localize(d.get("url_oparl")),
                text=text,
                text_truncated=truncated,
                text_total_chars=total_chars,
            )
        )
    note = None if results else "Für dieses Geschäft sind keine Dokumente hinterlegt."
    return DocumentsResponse(
        affair_id=params.affair_id,
        count=len(results),
        total_available=meta.get("total_records"),
        results=results,
        note=note,
    )


@mcp.tool(
    name="oparl_compare_bodies",
    annotations={"title": "Themenpräsenz über Körperschaften vergleichen", **_ANNOTATIONS},
)
@_instrument("oparl_compare_bodies")
async def oparl_compare_bodies(params: CompareBodiesInput, ctx: Context | None = None) -> CompareResponse:
    """Ein Thema über viele Körperschaften hinweg vergleichen (Themenpräsenz).

    Zählt pro Körperschaft, wie viele Geschäfte zum Suchbegriff existieren, und
    gibt eine nach Trefferzahl sortierte Rangliste zurück – ideal, um zu sehen,
    wo ein Thema politisch aktiv ist.

    <example>search="Tagesschule", body_type="municipality" → In welchen
    Schweizer Städten (neben Zürich) sind Tagesschulen ebenfalls Thema?</example>
    """
    targets = await body_cache.list_bodies(body_type=params.body_type)
    semaphore = asyncio.Semaphore(8)

    async def _count(b: body_cache.Body) -> BodyTopic:
        async with semaphore:
            payload = await api_get(
                "/affairs/",
                {"body_key": b.body_key, "search": params.search, "date_from": params.date_from, "limit": 1},
            )
            _rows, meta = unwrap(payload)
            return BodyTopic(
                body_key=b.body_key,
                name=b.name,
                type=b.type,
                match_count=int(meta.get("total_records") or 0),
            )

    counts = await asyncio.gather(*[_count(b) for b in targets], return_exceptions=True)
    topics = [c for c in counts if isinstance(c, BodyTopic)]
    topics.sort(key=lambda t: t.match_count, reverse=True)
    topics = topics[: params.top]
    return CompareResponse(
        search=params.search,
        count=len(topics),
        total_available=len(targets),
        results=topics,
        note=f"Verglichen über {len(targets)} Körperschaften vom Typ '{params.body_type}'.",
    )


@mcp.tool(
    name="oparl_search_persons",
    annotations={"title": "Personen/Mandatsträger suchen", **_ANNOTATIONS},
)
@_instrument("oparl_search_persons")
async def oparl_search_persons(params: SearchPersonsInput, ctx: Context | None = None) -> PersonsResponse:
    """Mandatsträger·innen einer Körperschaft suchen.

    <example>body_key="261", party="GLP", active=true → aktive GLP-Mitglieder im
    Gemeinderat der Stadt Zürich.</example>
    """
    body = await body_cache.resolve_body(params.body_key)
    query: dict[str, Any] = {
        "body_key": body.body_key,
        "party": params.party,
        "search": params.search,
        "limit": params.limit,
        "offset": params.offset,
        "sort_by": "lastname",
    }
    if params.active is not None:
        query["active"] = "true" if params.active else "false"
    payload = await api_get("/persons/", query)
    rows, meta = unwrap(payload)
    results = [_fmt_person(p) for p in rows]
    note = None if results else f"Keine Personen in '{body.name}' für die Filter gefunden."
    return PersonsResponse(
        count=len(results),
        total_available=meta.get("total_records"),
        offset=params.offset,
        results=results,
        note=note,
    )


@mcp.tool(
    name="oparl_get_person",
    annotations={"title": "Person-Details abrufen", **_ANNOTATIONS},
)
@_instrument("oparl_get_person")
async def oparl_get_person(params: GetPersonInput, ctx: Context | None = None) -> PersonDetail:
    """Vollständiges Profil einer Person nach ID abrufen.

    <example>person_id=17429, expand="interests" für ein Mitglied des Kantons-
    rats Zürich samt Interessenbindungen.</example>
    """
    payload = await api_get(f"/persons/{params.person_id}", {"expand": params.expand})
    rows, _meta = unwrap(payload)
    if not rows:
        return PersonDetail(found=False, id=params.person_id)
    p = rows[0]
    base = _fmt_person(p)
    expanded = {
        k: p[k]
        for k in (params.expand or "").split(",")
        if k.strip() and isinstance(p.get(k.strip()), (list, dict))
    } or None
    return PersonDetail(
        found=True,
        **base.model_dump(),
        email=p.get("email"),
        occupation=localize(p.get("occupation")),
        gender=p.get("gender"),
        website_parliament_url=localize(p.get("website_parliament_url")),
        expanded=expanded,
    )


@mcp.tool(
    name="oparl_get_person_interests",
    annotations={"title": "Interessenbindungen einer Person abrufen", **_ANNOTATIONS},
)
@_instrument("oparl_get_person_interests")
async def oparl_get_person_interests(
    params: GetPersonInterestsInput, ctx: Context | None = None
) -> InterestsResponse:
    """Interessenbindungen einer bestimmten Person abrufen.

    Achtung Datenqualität: Rohdaten mit Parsing-Artefakten; ``type``,
    ``role_name`` und ``group`` sind häufig leer. Antwort trägt daher
    ``data_quality="unverified_source_data"``.

    <example>person_id=17429 → deklarierte Bindungen eines Zürcher Kantonsrats-
    mitglieds.</example>
    """
    payload = await api_get(f"/persons/{params.person_id}/interests", {"limit": 100})
    rows, meta = unwrap(payload)
    results = [_fmt_interest(i) for i in rows]
    note = None if results else "Für diese Person sind keine Interessenbindungen deklariert (oder erfasst)."
    return InterestsResponse(
        count=len(results),
        total_available=meta.get("total_records"),
        results=results,
        note=note,
    )


@mcp.tool(
    name="oparl_search_interests",
    annotations={"title": "Interessenbindungen durchsuchen (Organisation → Personen)", **_ANNOTATIONS},
)
@_instrument("oparl_search_interests")
async def oparl_search_interests(params: SearchInterestsInput, ctx: Context | None = None) -> InterestsResponse:
    """Interessenbindungen einer Körperschaft durchsuchen (Organisation → Personen).

    Für die Bundesebene (``body_key='CHE'``) ist stattdessen ``lobbywatch-mcp``
    die geeignete Quelle (redaktionell geprüft, mit Branchen-Taxonomie).

    Achtung Datenqualität: Rohdaten mit Parsing-Artefakten (realer ZH-Datensatz
    enthält z.B. Jahreszahlen im Organisationsfeld). Antwort trägt
    ``data_quality="unverified_source_data"``.

    <example>body_key="ZH", search="Krankenkasse" → wer im Kanton Zürich eine
    Bindung zu einer Krankenkasse deklariert hat.</example>
    """
    body = await body_cache.resolve_body(params.body_key, federal_hint=FEDERAL_INTERESTS_REDIRECT)
    payload = await api_get(
        "/interests/",
        {"body_key": body.body_key, "search": params.search, "limit": params.limit, "offset": params.offset},
    )
    rows, meta = unwrap(payload)
    results = [_fmt_interest(i) for i in rows]
    note = None if results else f"Keine Interessenbindungen in '{body.name}' für die Suche gefunden."
    return InterestsResponse(
        count=len(results),
        total_available=meta.get("total_records"),
        offset=params.offset,
        results=results,
        note=note,
    )


@mcp.tool(
    name="oparl_get_votings",
    annotations={"title": "Abstimmungen abrufen", **_ANNOTATIONS},
)
@_instrument("oparl_get_votings")
async def oparl_get_votings(params: GetVotingsInput, ctx: Context | None = None) -> VotingsResponse:
    """Abstimmungen zu einem Geschäft oder einer Körperschaft abrufen.

    Liefert je Abstimmung die Ergebnisse (Ja/Nein/Enthaltung/Abwesend), den
    Entscheid sowie – wichtig zur Interpretation – die Bedeutung von Ja/Nein.
    Einzelstimmen liefert ``oparl_get_voting_results`` (benötigt ``voting_id``).

    <example>body_key="261" für Abstimmungen im Gemeinderat der Stadt Zürich,
    oder affair_id=334542 für die Abstimmungen zu einem konkreten Geschäft.</example>
    """
    if not params.affair_id and not params.body_key:
        raise ToolError("Bitte entweder affair_id oder body_key angeben.")
    query: dict[str, Any] = {"limit": params.limit, "offset": params.offset, "sort_by": "-date"}
    if params.affair_id:
        query["affair_id"] = params.affair_id
    if params.body_key:
        body = await body_cache.resolve_body(params.body_key)
        query["body_key"] = body.body_key
    payload = await api_get("/votings/", query)
    rows, meta = unwrap(payload)
    results = [_fmt_voting(v) for v in rows]
    note = None if results else "Keine Abstimmungen für die Kriterien gefunden."
    return VotingsResponse(
        count=len(results),
        total_available=meta.get("total_records"),
        offset=params.offset,
        results=results,
        note=note,
    )


@mcp.tool(
    name="oparl_get_voting_results",
    annotations={"title": "Einzelstimmen einer Abstimmung abrufen", **_ANNOTATIONS},
)
@_instrument("oparl_get_voting_results")
async def oparl_get_voting_results(
    params: GetVotingResultsInput, ctx: Context | None = None
) -> VotingResultsResponse:
    """Individuelle Stimmen (Namensabstimmung) zu EINER Abstimmung abrufen.

    Skalierungs-Guardrail: Die Gesamttabelle enthält >47 Mio. Einzelstimmen –
    deshalb ist ``voting_id`` Pflicht und ``limit`` hart auf 500 gedeckelt.

    <example>voting_id=105130 → wie die einzelnen Mitglieder der Stadt Zürich
    abgestimmt haben (mit Fraktion und Partei).</example>
    """
    voting_obj: VotingItem | None = None
    try:
        vp = await api_get(f"/votings/{params.voting_id}", None)
        vrows, _m = unwrap(vp)
        if vrows:
            voting_obj = _fmt_voting(vrows[0])
    except ToolError:
        voting_obj = None  # Kontext ist optional; Einzelstimmen bleiben massgeblich

    payload = await api_get(
        "/votes/",
        {"voting_id": params.voting_id, "limit": params.limit, "offset": params.offset},
    )
    rows, meta = unwrap(payload)
    results = [_fmt_vote(v) for v in rows]
    note = None if results else f"Keine Einzelstimmen zu voting_id={params.voting_id} gefunden."
    return VotingResultsResponse(
        voting_id=params.voting_id,
        voting=voting_obj,
        count=len(results),
        total_available=meta.get("total_records"),
        offset=params.offset,
        results=results,
        note=note,
    )


@mcp.tool(
    name="oparl_search_meetings",
    annotations={"title": "Sitzungen suchen", **_ANNOTATIONS},
)
@_instrument("oparl_search_meetings")
async def oparl_search_meetings(params: SearchMeetingsInput, ctx: Context | None = None) -> MeetingsResponse:
    """Sitzungen einer Körperschaft in einem Zeitraum finden.

    <example>body_key="261", date_from="2024-01-01", date_to="2024-12-31" →
    Sitzungen des Gemeinderats der Stadt Zürich im Jahr 2024.</example>
    """
    body = await body_cache.resolve_body(params.body_key)
    payload = await api_get(
        "/meetings/",
        {
            "body_key": body.body_key,
            "date_from": params.date_from,
            "date_to": params.date_to,
            "sort_by": "-begin_date",
            "limit": params.limit,
            "offset": params.offset,
        },
    )
    rows, meta = unwrap(payload)
    results = [_fmt_meeting(m) for m in rows]
    note = None if results else f"Keine Sitzungen in '{body.name}' für den Zeitraum gefunden."
    return MeetingsResponse(
        count=len(results),
        total_available=meta.get("total_records"),
        offset=params.offset,
        results=results,
        note=note,
    )


@mcp.tool(
    name="oparl_source_status",
    annotations={"title": "Quellen-Status prüfen", **_ANNOTATIONS},
)
@_instrument("oparl_source_status")
async def oparl_source_status(params: SourceStatusInput, ctx: Context | None = None) -> SourceStatus:
    """Erreichbarkeit der OpenParlData-API und Zustand des Body-Cache prüfen.

    Liefert Latenz, Zeitpunkt des letzten erfolgreichen Abrufs sowie Alter und
    Umfang des Body-Cache – nützlich zur Diagnose vor grösseren Recherchen.
    """
    reachable = False
    latency_ms: int | None = None
    body_count: int | None = None
    note: str | None = None
    start = time.monotonic()
    try:
        client = get_client()
        resp = await client.get(f"{BASE_URL}/bodies/", params={"indexed": "true", "limit": 1})
        resp.raise_for_status()
        reachable = True
        latency_ms = int((time.monotonic() - start) * 1000)
        meta = (resp.json() or {}).get("meta") or {}
        body_count = meta.get("total_records")
    except Exception as exc:  # noqa: BLE001 — Status-Tool meldet Fehler als Feld
        note = f"API nicht erreichbar: {type(exc).__name__}"

    age = body_cache.cache_age_seconds()
    return SourceStatus(
        reachable=reachable,
        latency_ms=latency_ms,
        last_successful_fetch=_fmt_epoch(last_success_epoch()),
        body_cache_loaded=age is not None,
        body_cache_age_seconds=int(age) if age is not None else None,
        body_count=body_count,
        note=note,
    )


# ─────────────────────────── HTTP-App (SSE / Streamable-HTTP) ───────────────────
def create_http_app():
    """Starlette-ASGI-App für Streamable HTTP mit CORS.

    ``Mcp-Session-Id`` wird via CORS exponiert (sonst können Browser-Clients die
    Session nicht lesen). Origins via ``MCP_ALLOWED_ORIGINS`` (CSV).
    """
    import os

    from starlette.middleware.cors import CORSMiddleware

    origins = [o.strip() for o in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Mcp-Session-Id", "Authorization"],
        expose_headers=["Mcp-Session-Id"],
        allow_credentials=bool(origins),
    )
    return app


# ─────────────────────────── Einstiegspunkt ────────────────────────────────────
def _resolve_settings() -> Settings:
    """Settings laden und CLI-Aliasse (--http/--port) + Plattform-PORT verrechnen."""
    import os
    import sys

    settings = Settings()
    if "--http" in sys.argv and "MCP_TRANSPORT" not in os.environ:
        settings.transport = "streamable-http"
    if settings.transport == "http":
        settings.transport = "streamable-http"
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            settings.port = int(sys.argv[i + 1])
    if "MCP_PORT" not in os.environ and os.environ.get("PORT"):
        settings.port = int(os.environ["PORT"])
    return settings


def main() -> None:
    settings = _resolve_settings()
    configure_logging(level=settings.log_level, json_logs=settings.json_logs)
    _logger.info("server_start", transport=settings.transport, protocol_version=PROTOCOL_VERSION)

    if settings.transport == "stdio":
        mcp.run(transport="stdio")
    elif settings.transport in ("sse", "streamable-http"):
        warn_on_dangerous_binding(settings.host)
        # Host/Port MÜSSEN vor mcp.run() über die Settings gesetzt werden –
        # FastMCP.run() akzeptiert sie nicht als kwargs.
        mcp.settings.host = settings.host
        mcp.settings.port = settings.port
        mcp.run(transport=settings.transport)
    else:
        raise SystemExit(
            f"Unbekannter MCP_TRANSPORT: {settings.transport!r} (erlaubt: stdio, sse, streamable-http)"
        )


if __name__ == "__main__":
    main()
