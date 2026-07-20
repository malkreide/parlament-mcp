"""Amtliches Bulletin – Volltext-Debatten (Transcript-Schicht).

Sauber getrennt von der Metadaten-Schicht in ``server.py``: dieses Modul kapselt
den Zugriff auf das Entity-Set ``Transcript`` der Curia-Vista-OData-API
(``ws.parlament.ch``) – die wörtlichen Wortmeldungen der Rats­debatten.

Designleitplanken (empirisch in der Live-Probe am 2026-07-19 verifiziert):

* **Volumen zuerst.** Eine einzelne Session enthält ~2800 Wortmeldungen
  (~500'000 Token unkomprimiert). Die Suche liefert deshalb **nur kurze
  Auszüge** (``snippet``) mit Zitation; der Volltext eines *einzelnen* Votums
  wird nur auf explizite Anforderung über :func:`get_transcript` geladen –
  gedeckelt und mit ``is_excerpt``-Kennzeichnung.
* **``Language`` ist die *Edition*, nicht die Redesprache.** Der Filter
  ``Language eq 'DE'`` dedupliziert die drei identischen Editionen (DE/FR/IT)
  auf eine Kopie; der ``Text`` bleibt in jedem Fall der Original-Wortlaut. Die
  tatsächliche Sprache steht in ``LanguageOfText`` und wird als ``language``
  ausgewiesen. Ein französisches Votum wird dadurch **nicht** unsichtbar.
* **Volltextsuche über ``Text`` ist teuer.** Ein exakter Prefilter
  (``IdSession``/``VoteBusinessNumber``) senkt die Latenz von ~40 s auf ~1 s;
  ``$count`` auf ``Text`` wird nie ausgeführt.
* **``Type eq 1`` isoliert echte Wortmeldungen** (2 = Abstimmungsresultat,
  3 = prozedurale Titel/Marker ohne Sprecher).
* **Keine Seitenzahl in der Quelle.** Die API führt kein Seiten-/Spaltenfeld,
  darum ist die klassische Form ``AB <Jahr> N <Seite>`` nicht konstruierbar.
  Wir bilden eine stabile, überprüfbare Ersatzreferenz und verlinken die
  offizielle Debatten-URL (``SubjectId``).
* **Zeitliche Abdeckung ab 1999-12-06.** Ältere Jahrgänge (1891–1999) liegen
  nur als Scans im Bundesarchiv vor und werden hier nicht angebunden.

Urheberrecht: Amtliche Verhandlungen von Behörden sind nach Art. 5 Abs. 1
lit. a URG vom Schutz ausgenommen – die wörtliche Wiedergabe ist zulässig und
erwünscht.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Literal

import httpx
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from parlament_mcp.config import DATA_LICENSE, DATA_SOURCE
from parlament_mcp.security import assert_host_allowed

# ─────────────────────────── Konstanten ────────────────────────────────────────
ODATA_BASE = "https://ws.parlament.ch/odata.svc"

#: Transkript-Reads können auch vorgefiltert bis ~12 s dauern (session-weit) und
#: unvorgefilterte Volltextsuchen bis ~40 s – daher grosszügiger als der
#: Metadaten-Timeout (20 s).
TRANSCRIPT_TIMEOUT = 45.0

#: Basis für den exponentiellen Backoff (Sekunden). In Tests auf 0 setzbar.
_BACKOFF_BASE = 2.0
_MAX_ATTEMPTS = 4

#: Edition, die zur Deduplizierung gefiltert wird. Verbirgt keine Redesprache.
EDITION = "DE"

#: Nur echte Wortmeldungen (nicht Abstimmungszeilen/Prozedur-Titel).
TYPE_SPEECH = 1

#: Erste strukturiert verfügbare Debatte (YYYYMMDD). Davor nur Bundesarchiv-Scans.
DIGITAL_START = "19991206"
DIGITAL_START_ISO = "1999-12-06"

SNIPPET_CHARS = 320
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 30
DEFAULT_FULLTEXT_CHARS = 6000
MAX_FULLTEXT_CHARS = 20000

_COUNCIL_TO_ABBR = {"NR": "N", "SR": "S", "N": "N", "S": "S"}
_ABBR_TO_COUNCIL = {"N": "Nationalrat", "S": "Ständerat"}

_SUBJECT_URL = (
    "https://www.parlament.ch/de/ratsbetrieb/amtliches-bulletin/"
    "amtliches-bulletin-die-verhandlungen?SubjectId={}"
)

_SEARCH_SUGGESTIONS = [
    "Volksschule",
    "Künstliche Intelligenz",
    "Klima",
    "Gesundheit",
    "Digitalisierung",
]

_LANGUAGE_NOTE = (
    "Edition 'DE' gefiltert (dedupliziert drei identische Editionen zu einer "
    "Kopie). Jede Wortmeldung ist im Original-Wortlaut wiedergegeben; die "
    "tatsächlich gesprochene Sprache steht im Feld 'language'. Keine "
    "französisch- oder italienischsprachigen Voten werden dadurch ausgeblendet."
)

_CITATION_NOTE = (
    "Die API führt keine Seitenzahl; die offizielle Fundstelle wird über "
    "'source_url' (SubjectId) und 'transcript_id' eindeutig referenziert."
)


def _q(value: str) -> str:
    """Einfache Anführungszeichen für OData-String-Literale escapen."""
    return value.replace("'", "''")


# ─────────────────────────── Text-Aufbereitung ─────────────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")
_MARKER_RE = re.compile(r"\[[A-Z]{2,4}\]")  # [GZ], [NAM], … – Verbalix-Marker
_WS_RE = re.compile(r"[ \t]*\n[ \t]*")
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")


def clean_markup(raw: str | None) -> str:
    """HTML-/Verbalix-Markup aus dem ``Text``-Feld entfernen, Wortlaut erhalten.

    Entfernt ``<pd_text>``/``<p>``-Tags und Verbalix-Marker (``[GZ]``, ``[NAM]``)
    und normalisiert Whitespace, ohne den eigentlichen Wortlaut zu verändern.
    """
    if not raw:
        return ""
    text = _TAG_RE.sub("\n", raw)
    text = _MARKER_RE.sub(" ", text)
    text = _WS_RE.sub("\n", text)
    text = _MULTISPACE_RE.sub(" ", text)
    # Mehrfache Leerzeilen auf eine reduzieren.
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def parse_meeting_date(raw: str | None) -> str:
    """``MeetingDate`` in ISO ``YYYY-MM-DD`` umwandeln.

    Verarbeitet sowohl das API-Format ``20240313`` als auch ISO-Timestamps
    (``2024-03-13T09:00:00``) tolerant.
    """
    if not raw:
        return ""
    raw = str(raw)
    if len(raw) >= 8 and raw[:8].isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw[:10]


def _to_yyyymmdd(iso: str) -> str:
    """ISO ``YYYY-MM-DD`` in das API-Format ``YYYYMMDD`` (String-vergleichbar)."""
    return iso.replace("-", "")


def build_citation(*, date_iso: str, council_abbr: str | None, speaker: str | None) -> str:
    """Stabile, überprüfbare AB-Ersatzreferenz bilden.

    Ohne Seitenzahl (nicht in der Quelle vorhanden) in der Form
    ``AB <Jahr> <N|S>, <Datum>, <Sprecher>``. Die eindeutige Auflösung erfolgt
    über ``source_url`` und ``transcript_id``.
    """
    year = date_iso[:4] if date_iso else "?"
    letter = (council_abbr or "?").strip() or "?"
    parts = [f"AB {year} {letter}"]
    if date_iso:
        parts.append(date_iso)
    if speaker:
        parts.append(speaker)
    return ", ".join(parts)


def build_source_url(id_subject: str | int | None) -> str | None:
    """Öffentliche, stabile Debatten-URL aus ``IdSubject`` bilden."""
    if id_subject in (None, "", 0, "0"):
        return None
    return _SUBJECT_URL.format(id_subject)


# ─────────────────────────── Ausgabemodelle ────────────────────────────────────
class TranscriptEnvelope(BaseModel):
    """Konsistenter Envelope (parallel zur Metadaten-Schicht, aber entkoppelt)."""

    source: str = DATA_SOURCE
    license: str = DATA_LICENSE
    provenance: Literal["live_api", "cached"] = "live_api"
    match_type: Literal["exact", "fuzzy", "none"] = "exact"
    count: int = 0
    offset: int = 0
    edition: str = EDITION
    language_note: str = _LANGUAGE_NOTE
    citation_note: str = _CITATION_NOTE
    coverage_since: str = DIGITAL_START_ISO
    note: str | None = None
    suggestions: list[str] = Field(default_factory=list)


class TranscriptHit(BaseModel):
    """Ein Treffer der Transkript-Suche – Auszug mit Zitation, nie Volltext."""

    transcript_id: int | None = None
    citation: str
    source_url: str | None = None
    speaker: str | None = None
    function: str | None = None
    canton: str | None = None
    group: str | None = None
    council: str | None = None
    date: str | None = None
    session_id: int | None = None
    language: str | None = None
    business_number: int | None = None
    business_title: str | None = None
    snippet: str = ""
    is_excerpt: bool = True
    total_length_chars: int = 0


class TranscriptSearchResponse(TranscriptEnvelope):
    results: list[TranscriptHit] = Field(default_factory=list)
    full_text_hint: str = (
        "Volltext eines Votums mit parlament_get_transcript(transcript_id=…) laden."
    )


class TranscriptDetail(BaseModel):
    """Volltext eines *einzelnen* Votums – gedeckelt, mit Kürzungs-Kennzeichnung."""

    found: bool = True
    source: str = DATA_SOURCE
    license: str = DATA_LICENSE
    provenance: Literal["live_api", "cached"] = "live_api"
    transcript_id: int | None = None
    citation: str = ""
    source_url: str | None = None
    speaker: str | None = None
    function: str | None = None
    canton: str | None = None
    group: str | None = None
    council: str | None = None
    date: str | None = None
    session_id: int | None = None
    language: str | None = None
    business_number: int | None = None
    business_title: str | None = None
    text: str = ""
    total_length_chars: int = 0
    is_excerpt: bool = False
    offset: int = 0
    next_offset: int | None = None
    note: str | None = None


# ─────────────────────────── Eingabemodelle ────────────────────────────────────
class SearchTranscriptsInput(BaseModel):
    """Eingabe für die Suche in den Debatten-Transkripten (Amtliches Bulletin)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: str | None = Field(
        default=None,
        description="Volltext-Stichwort im Wortlaut (z.B. 'Volksschule', 'KI'). "
        "Für beste Latenz mit session_id, business_number oder Datumsfenster kombinieren.",
        min_length=2,
        max_length=200,
    )
    speaker_name: str | None = Field(
        default=None,
        description="Nachname des Redners bzw. der Rednerin (Teilübereinstimmung).",
        min_length=2,
        max_length=100,
    )
    session_id: int | None = Field(
        default=None,
        description="Session-ID (aus parlament_get_sessions). Schneller exakter Prefilter.",
        gt=0,
        strict=True,
    )
    council: str | None = Field(
        default=None,
        description="Rat: 'NR'/'N' (Nationalrat) oder 'SR'/'S' (Ständerat).",
        max_length=20,
    )
    business_number: int | None = Field(
        default=None,
        description="Geschäftsnummer (VoteBusinessNumber, z.B. 20200504) als exakter Prefilter.",
        gt=0,
        strict=True,
    )
    date_from: str | None = Field(
        default=None,
        description="Von-Datum (ISO JJJJ-MM-TT). Abdeckung ab 1999-12-06.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_to: str | None = Field(
        default=None,
        description="Bis-Datum (ISO JJJJ-MM-TT).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT,
        description=f"Maximale Trefferzahl (1–{MAX_SEARCH_LIMIT}).",
        ge=1,
        le=MAX_SEARCH_LIMIT,
        strict=True,
    )
    offset: int = Field(default=0, description="Offset für Paginierung.", ge=0, strict=True)


class GetTranscriptInput(BaseModel):
    """Eingabe zum Abruf des Volltextes eines einzelnen Votums."""

    model_config = ConfigDict(extra="forbid")

    transcript_id: int = Field(
        ...,
        description="Transkript-ID (aus parlament_search_transcripts).",
        gt=0,
        strict=True,
    )
    offset: int = Field(
        default=0,
        description="Zeichen-Offset in den (bereinigten) Volltext für lange Voten.",
        ge=0,
        strict=True,
    )
    max_chars: int = Field(
        default=DEFAULT_FULLTEXT_CHARS,
        description=f"Maximale Zeichenzahl pro Abruf (1–{MAX_FULLTEXT_CHARS}).",
        ge=1,
        le=MAX_FULLTEXT_CHARS,
        strict=True,
    )


# ─────────────────────────── HTTP mit Retry ────────────────────────────────────
async def _fetch(
    client: httpx.AsyncClient, url: str, params: dict[str, str]
) -> Any:
    """OData-GET mit exponentiellem Backoff (Portfolio-Resilienz-Default).

    Retry bei 5xx/429 und Netzwerkfehlern (3 Wiederholungen, 2s/4s/8s);
    4xx (ausser 429) werden nicht wiederholt.
    """
    assert_host_allowed(url)
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        if attempt:
            await asyncio.sleep(_BACKOFF_BASE ** attempt)
        try:
            resp = await client.get(url, params=params, timeout=TRANSCRIPT_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            last_error = exc
            code = exc.response.status_code
            if 400 <= code < 500 and code != 429:
                raise
        except httpx.RequestError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


# ─────────────────────────── Kernlogik ─────────────────────────────────────────
def _validate_coverage(date_from: str | None, date_to: str | None) -> None:
    """Erklärenden Fehler werfen, wenn das Fenster ganz vor der Abdeckung liegt."""
    upper = date_to or date_from
    if date_to and _to_yyyymmdd(date_to) < DIGITAL_START:
        raise ToolError(
            f"Fehler: Das Amtliche Bulletin liegt strukturiert erst ab "
            f"{DIGITAL_START_ISO} vor (angefragtes Bis-Datum: {date_to}). Ältere "
            "Jahrgänge (1891–1999) existieren nur als Scans im Bundesarchiv "
            "(Amtsdruckschriften) und sind hier nicht angebunden."
        )
    # date_from vor Abdeckung, aber ohne Bis-Datum → Fenster reicht bis heute: erlauben.
    _ = upper


def _empty_search(offset: int, note: str) -> TranscriptSearchResponse:
    return TranscriptSearchResponse(
        match_type="none", count=0, offset=offset, note=note, suggestions=_SEARCH_SUGGESTIONS
    )


def _hit_from_record(rec: dict[str, Any]) -> TranscriptHit:
    date_iso = parse_meeting_date(rec.get("MeetingDate"))
    council_abbr = rec.get("MeetingCouncilAbbreviation")
    speaker = rec.get("SpeakerFullName") or None
    cleaned = clean_markup(rec.get("Text"))
    snippet = cleaned[:SNIPPET_CHARS]
    is_excerpt = len(cleaned) > SNIPPET_CHARS
    if is_excerpt:
        snippet = snippet.rstrip() + " …"
    lot = rec.get("LanguageOfText")
    tid = rec.get("ID")
    return TranscriptHit(
        transcript_id=int(tid) if tid not in (None, "") else None,
        citation=build_citation(date_iso=date_iso, council_abbr=council_abbr, speaker=speaker),
        source_url=build_source_url(rec.get("IdSubject")),
        speaker=speaker,
        function=rec.get("SpeakerFunction") or rec.get("Function"),
        canton=rec.get("CantonAbbreviation"),
        group=rec.get("ParlGroupAbbreviation"),
        council=_ABBR_TO_COUNCIL.get(council_abbr or "", rec.get("CouncilName")),
        date=date_iso or None,
        session_id=int(rec["IdSession"]) if str(rec.get("IdSession") or "").isdigit() else None,
        language=(lot or "").lower() or None,
        business_number=rec.get("VoteBusinessNumber"),
        business_title=(rec.get("VoteBusinessTitle") or "").strip() or None,
        snippet=snippet,
        is_excerpt=is_excerpt,
        total_length_chars=len(cleaned),
    )


async def search_transcripts(
    client: httpx.AsyncClient, params: SearchTranscriptsInput, ctx: Any | None = None
) -> TranscriptSearchResponse:
    """Transkripte suchen und als kurze, zitierfähige Auszüge zurückgeben."""
    _validate_coverage(params.date_from, params.date_to)

    filters = [f"Language eq '{EDITION}'", f"Type eq {TYPE_SPEECH}"]
    if params.session_id:
        filters.append(f"IdSession eq '{params.session_id}'")
    if params.business_number:
        filters.append(f"VoteBusinessNumber eq {params.business_number}")
    if params.council:
        abbr = _COUNCIL_TO_ABBR.get(params.council.upper())
        if abbr:
            filters.append(f"MeetingCouncilAbbreviation eq '{abbr}'")
    if params.speaker_name:
        filters.append(f"substringof('{_q(params.speaker_name)}',SpeakerLastName)")
    if params.keyword:
        filters.append(f"substringof('{_q(params.keyword)}',Text)")
    if params.date_from:
        filters.append(f"MeetingDate ge '{_to_yyyymmdd(params.date_from)}'")
    if params.date_to:
        filters.append(f"MeetingDate le '{_to_yyyymmdd(params.date_to)}'")

    query = {
        "$format": "json",
        "$filter": " and ".join(f"({f})" for f in filters),
        "$orderby": "MeetingDate desc",
        "$top": str(min(params.limit, MAX_SEARCH_LIMIT)),
    }
    if params.offset:
        query["$skip"] = str(params.offset)

    if ctx is not None:
        try:
            await ctx.info("parlament_search_transcripts: Abfrage läuft")
        except Exception:
            pass

    data = await _fetch(client, f"{ODATA_BASE}/Transcript", query)
    records = data.get("d", []) if isinstance(data, dict) else []
    if not records:
        return _empty_search(
            params.offset,
            "Keine Wortmeldungen für die angegebenen Kriterien gefunden.",
        )

    hits = [_hit_from_record(r) for r in records]
    return TranscriptSearchResponse(
        match_type="fuzzy" if params.keyword or params.speaker_name else "exact",
        count=len(hits),
        offset=params.offset,
        results=hits,
    )


async def get_transcript(
    client: httpx.AsyncClient, params: GetTranscriptInput
) -> TranscriptDetail:
    """Volltext eines einzelnen Votums abrufen (gedeckelt, mit Kürzungs-Flag)."""
    url = f"{ODATA_BASE}/Transcript(ID={params.transcript_id}L,Language='{EDITION}')"
    query = {"$format": "json"}
    data = await _fetch(client, url, query)
    rec = data.get("d", data) if isinstance(data, dict) else {}
    if not rec or not rec.get("ID"):
        return TranscriptDetail(
            found=False,
            transcript_id=params.transcript_id,
            note="Kein Transkript mit dieser ID gefunden.",
        )

    cleaned = clean_markup(rec.get("Text"))
    total = len(cleaned)
    window = cleaned[params.offset : params.offset + params.max_chars]
    end = params.offset + len(window)
    is_excerpt = params.offset > 0 or end < total
    next_offset = end if end < total else None

    date_iso = parse_meeting_date(rec.get("MeetingDate"))
    council_abbr = rec.get("MeetingCouncilAbbreviation")
    speaker = rec.get("SpeakerFullName") or None
    lot = rec.get("LanguageOfText")

    note = None
    if is_excerpt:
        shown = f"Zeichen {params.offset}–{end} von {total}"
        if next_offset is not None:
            note = (
                f"Gekürzt ({shown}). Fortsetzung mit "
                f"parlament_get_transcript(transcript_id={params.transcript_id}, "
                f"offset={next_offset})."
            )
        else:
            note = f"Auszug ab Offset ({shown})."

    return TranscriptDetail(
        found=True,
        transcript_id=int(rec["ID"]),
        citation=build_citation(date_iso=date_iso, council_abbr=council_abbr, speaker=speaker),
        source_url=build_source_url(rec.get("IdSubject")),
        speaker=speaker,
        function=rec.get("SpeakerFunction") or rec.get("Function"),
        canton=rec.get("CantonAbbreviation"),
        group=rec.get("ParlGroupAbbreviation"),
        council=_ABBR_TO_COUNCIL.get(council_abbr or "", rec.get("CouncilName")),
        date=date_iso or None,
        session_id=int(rec["IdSession"]) if str(rec.get("IdSession") or "").isdigit() else None,
        language=(lot or "").lower() or None,
        business_number=rec.get("VoteBusinessNumber"),
        business_title=(rec.get("VoteBusinessTitle") or "").strip() or None,
        text=window,
        total_length_chars=total,
        is_excerpt=is_excerpt,
        offset=params.offset,
        next_offset=next_offset,
        note=note,
    )
