"""Tests für die Amtliches-Bulletin-Transkript-Schicht (parlament_mcp.transcripts).

Alle HTTP-Aufrufe werden mit respx gemockt; Fixtures sind aus echten, gekürzten
API-Antworten von ws.parlament.ch gebaut (Live-Probe 2026-07-19). Live-Tests
sind mit @pytest.mark.live markiert und in CI ausgeschlossen.
"""

from __future__ import annotations

import re

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from parlament_mcp import transcripts as tx
from parlament_mcp.transcripts import (
    GetTranscriptInput,
    SearchTranscriptsInput,
    build_citation,
    clean_markup,
    get_transcript,
    parse_meeting_date,
    search_transcripts,
)

_ROUTE = rf"{re.escape(tx.ODATA_BASE)}/Transcript.*"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=5.0)


# ─────────────────────────── Fixtures (echte, gekürzte API-Records) ─────────────
# DE-gesprochenes Votum (Type=1), gekürzt.
REC_DE = {
    "ID": "378304",
    "Language": "DE",
    "Type": 1,
    "IdSubject": "64008",
    "SpeakerFullName": "Arslan Sibel",
    "SpeakerFunction": "Mit-F",
    "CantonAbbreviation": "BS",
    "ParlGroupAbbreviation": "G",
    "MeetingCouncilAbbreviation": "N",
    "MeetingDate": "20240313",
    "IdSession": "5202",
    "LanguageOfText": "DE",
    "VoteBusinessTitle": "Folter als eigener Straftatbestand",
    "VoteBusinessNumber": 20200504,
    "Text": "<pd_text><p>Die Schweiz ratifizierte die UNO-Antifolterkonvention "
    "bereits vor vielen Jahren. Das Strafrecht wurde so angepasst, dass Folter "
    "als Völkerrechtsverbrechen erfasst wird. Ich möchte betonen, dass gerade "
    "in der Volksschule die Auseinandersetzung mit Menschenrechten früh beginnen "
    "muss, damit die kommenden Generationen die Bedeutung des Folterverbots "
    "verstehen und verteidigen. Deshalb unterstütze ich diese Initiative.</p></pd_text>",
}

# FR-gesprochenes Votum – erscheint unter der DE-Edition (LanguageOfText='FR').
REC_FR = {
    "ID": "378277",
    "Language": "DE",
    "Type": 1,
    "IdSubject": "64008",
    "SpeakerFullName": "Dandrès Christian",
    "SpeakerFunction": "Mit-M",
    "CantonAbbreviation": "GE",
    "ParlGroupAbbreviation": "S",
    "MeetingCouncilAbbreviation": "N",
    "MeetingDate": "20240313",
    "IdSession": "5202",
    "LanguageOfText": "FR",
    "VoteBusinessTitle": "Folter als eigener Straftatbestand",
    "VoteBusinessNumber": 20200504,
    "Text": "<pd_text><p>L'initiative de notre ancien collègue Flach vise à "
    "reprendre en droit interne l'infraction de torture.</p></pd_text>",
}


# ─────────────────────────── Unit-Tests (kein Netzwerk) ─────────────────────────
def test_clean_markup_strips_tags_and_markers():
    raw = "<pd_text><p>Für den Antrag[GZ]</p>\n<p>[NAM][GZ]132 Stimmen</p></pd_text>"
    out = clean_markup(raw)
    assert "<" not in out and ">" not in out
    assert "[GZ]" not in out and "[NAM]" not in out
    assert "Für den Antrag" in out and "132 Stimmen" in out


def test_parse_meeting_date_formats():
    assert parse_meeting_date("20240313") == "2024-03-13"
    assert parse_meeting_date("2024-03-13T09:00:00") == "2024-03-13"
    assert parse_meeting_date(None) == ""


def test_build_citation_has_ab_prefix_without_page():
    cit = build_citation(date_iso="2024-03-13", council_abbr="N", speaker="Munz Martina")
    assert cit == "AB 2024 N, 2024-03-13, Munz Martina"


# ─────────────────────────── Pflicht-Testfall 1: Zitation ──────────────────────
@respx.mock
async def test_search_returns_hits_with_citation():
    respx.route(method="GET", url__regex=_ROUTE).mock(
        return_value=httpx.Response(200, json={"d": [REC_DE]})
    )
    async with _client() as c:
        res = await search_transcripts(c, SearchTranscriptsInput(keyword="Volksschule", session_id=5202))
    assert res.count == 1
    hit = res.results[0]
    assert hit.citation == "AB 2024 N, 2024-03-13, Arslan Sibel"
    assert hit.source_url and "SubjectId=64008" in hit.source_url
    assert hit.council == "Nationalrat"
    assert hit.is_excerpt is True
    assert hit.total_length_chars > 0
    assert res.source.startswith("Curia Vista") and res.license == "CC BY 4.0"


# ─────────────────────────── Pflicht-Testfall 2: Volltext-Abruf ────────────────
@respx.mock
async def test_get_transcript_full_text():
    respx.route(method="GET", url__regex=_ROUTE).mock(
        return_value=httpx.Response(200, json={"d": REC_DE})
    )
    async with _client() as c:
        res = await get_transcript(c, GetTranscriptInput(transcript_id=378304))
    assert res.found is True
    assert res.transcript_id == 378304
    assert "Antifolterkonvention" in res.text
    assert res.is_excerpt is False  # passt vollständig in max_chars
    assert res.citation.startswith("AB 2024 N")
    assert res.source_url and "SubjectId=64008" in res.source_url


# ─────────────────────────── Pflicht-Testfall 3: Kürzung ───────────────────────
@respx.mock
async def test_get_transcript_truncation_flag_and_hint():
    long_rec = dict(REC_DE, Text="<p>" + "A" * 8000 + "</p>")
    respx.route(method="GET", url__regex=_ROUTE).mock(
        return_value=httpx.Response(200, json={"d": long_rec})
    )
    async with _client() as c:
        res = await get_transcript(c, GetTranscriptInput(transcript_id=378304, max_chars=1000))
    assert res.is_excerpt is True
    assert len(res.text) == 1000
    assert res.total_length_chars >= 8000
    assert res.next_offset == 1000
    assert res.note and "offset=1000" in res.note  # expliziter Hinweis, kein stilles Kürzen


# ─────────────────────────── Pflicht-Testfall 4: FR-Votum ──────────────────────
@respx.mock
async def test_french_speech_found_and_marked_fr():
    respx.route(method="GET", url__regex=_ROUTE).mock(
        return_value=httpx.Response(200, json={"d": [REC_FR]})
    )
    async with _client() as c:
        res = await search_transcripts(c, SearchTranscriptsInput(session_id=5202))
    assert res.count == 1
    hit = res.results[0]
    assert hit.language == "fr"  # tatsächliche Redesprache, nicht Edition
    assert "torture" in hit.snippet  # französischer Original-Wortlaut sichtbar


# ─────────────────────────── Pflicht-Testfall 5: Historische Lücke ─────────────
async def test_pre_digital_range_raises_explanatory_error():
    async with _client() as c:
        with pytest.raises(ToolError) as exc:
            await search_transcripts(
                c, SearchTranscriptsInput(keyword="Bildung", date_from="1950-01-01", date_to="1970-01-01")
            )
    assert "1999" in str(exc.value)  # erklärender Fehler, nicht leeres Resultat


# ─────────────────────────── Pflicht-Testfall 6: Keine Sprach-Duplikate ────────
@respx.mock
async def test_edition_filter_prevents_language_duplicates():
    """Der Request muss die Edition (Language eq 'DE') und Type eq 1 filtern –
    das dedupliziert die drei Editionen und liefert nur echte Wortmeldungen."""
    route = respx.route(method="GET", url__regex=_ROUTE).mock(
        return_value=httpx.Response(200, json={"d": [REC_DE]})
    )
    async with _client() as c:
        await search_transcripts(c, SearchTranscriptsInput(keyword="Volksschule", session_id=5202))
    sent = route.calls.last.request
    flt = httpx.QueryParams(sent.url.query).get("$filter", "")
    assert "Language eq 'DE'" in flt
    assert "Type eq 1" in flt


# ─────────────────────────── Empty & Envelope ──────────────────────────────────
@respx.mock
async def test_empty_search_returns_suggestions():
    respx.route(method="GET", url__regex=_ROUTE).mock(
        return_value=httpx.Response(200, json={"d": []})
    )
    async with _client() as c:
        res = await search_transcripts(c, SearchTranscriptsInput(keyword="xyz_none", session_id=5202))
    assert res.match_type == "none" and res.count == 0
    assert res.suggestions  # ARCH-003


# ─────────────────────────── Resilienz: Retry & Fehler ─────────────────────────
@respx.mock
async def test_retry_on_503_then_success(monkeypatch):
    monkeypatch.setattr(tx, "_BACKOFF_BASE", 0)  # keine echten Wartezeiten im Test
    respx.route(method="GET", url__regex=_ROUTE).mock(
        side_effect=[
            httpx.Response(503, text="Service Unavailable"),
            httpx.Response(200, json={"d": [REC_DE]}),
        ]
    )
    async with _client() as c:
        res = await search_transcripts(c, SearchTranscriptsInput(session_id=5202))
    assert res.count == 1


@respx.mock
async def test_404_not_retried_and_raises():
    respx.route(method="GET", url__regex=_ROUTE).mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    async with _client() as c:
        with pytest.raises(httpx.HTTPStatusError):
            await get_transcript(c, GetTranscriptInput(transcript_id=1))


@respx.mock
async def test_get_transcript_missing_returns_not_found():
    respx.route(method="GET", url__regex=_ROUTE).mock(
        return_value=httpx.Response(200, json={"d": {}})
    )
    async with _client() as c:
        res = await get_transcript(c, GetTranscriptInput(transcript_id=999999999))
    assert res.found is False
    assert res.note


# ─────────────────────────── Live-Tests (echte API, CI-ausgeschlossen) ─────────
@pytest.mark.live
async def test_live_anchor_query():
    """Live: Anker-Demo – Volksschule in der Frühjahrssession 2024 (Session 5202)."""
    async with _client() as c:
        res = await search_transcripts(
            c, SearchTranscriptsInput(session_id=5202, keyword="Volksschule", limit=3)
        )
    assert res.match_type in ("fuzzy", "none")
    for hit in res.results:
        assert hit.citation.startswith("AB ")
        assert hit.source_url and "SubjectId=" in hit.source_url


@pytest.mark.live
async def test_live_french_votum_present():
    """Live: Ein FR-gesprochenes Votum erscheint unter der DE-Edition."""
    async with _client() as c:
        res = await search_transcripts(
            c, SearchTranscriptsInput(session_id=5202, limit=30)
        )
    langs = {h.language for h in res.results}
    assert res.count > 0
    assert langs.issubset({"de", "fr", "it", None})
