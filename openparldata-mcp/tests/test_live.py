"""Live-Tests gegen die echte OpenParlData-API (DRIFT-005).

Alle Tests hier sind mit ``@pytest.mark.live`` markiert und in CI bei jedem PR
ausgeschlossen; gefahren werden sie nightly von ``.github/workflows/live-test.yml``.

Zweck ist ausdrücklich NICHT, die Geschäftslogik zu prüfen — das tun die
hermetischen respx-Tests. Geprüft wird die eine Klasse von Fehlern, die jene
nicht sehen können: dass die Feldnamen der Quelle noch die sind, gegen die
``server.py`` mappt. Benennt die API ein Feld um, bleiben die Mocks grün und die
Produktion liefert still ``None``. Deshalb wird hier auf *befüllte* Felder
geprüft, nicht bloss auf HTTP 200.

Anker ist durchgehend Stadt Zürich (``body_key="261"``) — die grösste und
vollständigste Körperschaft im Index. IDs werden nie fest verdrahtet, sondern
über eine Suche ermittelt: Einzeldatensätze verschwinden, die Suche nicht.

Endpunkt-Abdeckung (je mindestens ein Test): ``/bodies/``, ``/affairs/``,
``/affairs/{id}``, ``/affairs/{id}/docs``, ``/persons/``, ``/persons/{id}``,
``/interests/``, ``/votings/``, ``/votes/``, ``/meetings/``.

Letzte Verifikation der hier erwarteten Feldnamen gegen die Quelle: 2026-08-14.
"""

from __future__ import annotations

import pytest

from openparldata_mcp import server as s

pytestmark = pytest.mark.live

# Stadt Zürich – Anker für alle körperschaftsbezogenen Abfragen.
ZURICH = "261"


async def _first_affair_id() -> int:
    """Eine aktuell existierende Affair-ID über die Suche ermitteln."""
    found = await s.oparl_search_affairs(s.SearchAffairsInput(body_key=ZURICH, limit=5))
    assert found.results, "Suche liefert keine Geschäfte – Anker ist unbrauchbar geworden."
    affair_id = found.results[0].id
    assert affair_id is not None
    return affair_id


# ─────────────────────────── /bodies/ ──────────────────────────────────────────


async def test_live_bodies_index_resolves():
    """Der Body-Index liefert die bekannten Schlüssel mit befüllten Namen."""
    r = await s.oparl_list_bodies(s.ListBodiesInput())
    keys = {b.body_key for b in r.results}
    assert {"261", "ZH"} <= keys, f"Erwartete Körperschaften fehlen im Index: {sorted(keys)[:20]}"
    zurich = next(b for b in r.results if b.body_key == ZURICH)
    # Bricht, wenn die Quelle 'name' umbenennt oder das Lokalisierungs-Dict wechselt.
    assert zurich.name, "body.name ist leer – Feldname oder Sprach-Dict der Quelle geändert?"
    assert zurich.type, "body.type ist leer – Feldname der Quelle geändert?"


# ─────────────────────────── /affairs/ ─────────────────────────────────────────


async def test_live_search_affairs_fields_populated():
    """Geschäftssuche: Titel und Status kommen befüllt und lokalisiert an."""
    r = await s.oparl_search_affairs(
        s.SearchAffairsInput(body_key=ZURICH, search="Tagesschule", limit=3)
    )
    assert r.results, "Ankersuche 'Tagesschule' in Zürich liefert nichts mehr."
    assert r.total_available and r.total_available > 0
    first = r.results[0]
    assert first.id and first.body_key == ZURICH
    # title kommt als {"de": ...}-Dict und muss zu str lokalisiert werden.
    assert isinstance(first.title, str) and first.title.strip()
    assert first.number, "affair.number ist leer – Feldname der Quelle geändert?"


async def test_live_get_affair_detail():
    """Einzelabruf eines Geschäfts liefert einen befüllten Datensatz."""
    affair_id = await _first_affair_id()
    detail = await s.oparl_get_affair(s.GetAffairInput(affair_id=affair_id))
    assert detail.found is True
    assert detail.id == affair_id
    assert isinstance(detail.title, str) and detail.title.strip()
    assert detail.type_name, "affair.type_name ist leer – Feldname der Quelle geändert?"


async def test_live_affair_documents():
    """Dokumentliste eines Geschäfts ist abrufbar und trägt die Affair-ID."""
    affair_id = await _first_affair_id()
    docs = await s.oparl_get_affair_documents(
        s.GetAffairDocumentsInput(affair_id=affair_id, include_text=False)
    )
    assert docs.affair_id == affair_id
    # Nicht jedes Geschäft hat Dokumente; wenn welche da sind, müssen sie tragen.
    for d in docs.results:
        assert d.name, "document.name ist leer – Feldname der Quelle geändert?"


# ─────────────────────────── /persons/ ─────────────────────────────────────────


async def test_live_search_persons_fields_populated():
    """Personensuche liefert Namen — das Feld, an dem ein Rename sofort auffällt."""
    r = await s.oparl_search_persons(s.SearchPersonsInput(body_key=ZURICH, limit=5))
    assert r.results, "Keine Personen für Stadt Zürich – Anker unbrauchbar geworden."
    assert all(p.fullname for p in r.results), "person.fullname leer – Feldname geändert?"
    assert all(p.body_key == ZURICH for p in r.results)


async def test_live_get_person_detail():
    """Einzelabruf einer Person liefert denselben Namen wie die Liste."""
    listed = await s.oparl_search_persons(s.SearchPersonsInput(body_key=ZURICH, limit=1))
    assert listed.results
    person_id = listed.results[0].id
    assert person_id is not None
    detail = await s.oparl_get_person(s.GetPersonInput(person_id=person_id))
    assert detail.found is True
    assert detail.id == person_id
    assert detail.fullname == listed.results[0].fullname


# ─────────────────────────── /interests/ ───────────────────────────────────────


async def test_live_search_interests():
    """Interessenbindungen sind abrufbar und als ungeprüfte Rohdaten markiert."""
    r = await s.oparl_search_interests(s.SearchInterestsInput(body_key=ZURICH, limit=5))
    assert r.data_quality == "unverified_source_data"
    assert r.results, "Keine Interessenbindungen für Stadt Zürich – Endpunkt geändert?"
    assert any(i.organisation for i in r.results), "interest.organisation durchgehend leer."


# ─────────────────────────── /votings/ + /votes/ ───────────────────────────────


async def test_live_votings_carry_result_counts():
    """Abstimmungen tragen Zählwerte und die Bedeutung von Ja/Nein."""
    r = await s.oparl_get_votings(s.GetVotingsInput(body_key=ZURICH, limit=5))
    assert r.results, "Keine Abstimmungen für Stadt Zürich – Endpunkt geändert?"
    first = r.results[0]
    assert isinstance(first.title, str) and first.title.strip()
    # results_yes ist der Wert, den ein stiller Rename zu None machen würde.
    assert first.results_yes is not None, "voting.results_yes leer – Feldname geändert?"
    assert first.date, "voting.date leer – Feldname geändert?"


async def test_live_voting_results_individual_votes():
    """Einzelstimmen zu einer konkreten Abstimmung sind abrufbar."""
    votings = await s.oparl_get_votings(s.GetVotingsInput(body_key=ZURICH, limit=1))
    assert votings.results
    voting_id = votings.results[0].id
    assert voting_id is not None
    r = await s.oparl_get_voting_results(s.GetVotingResultsInput(voting_id=voting_id))
    assert r.voting_id == voting_id
    # Nicht jede Abstimmung ist eine Namensabstimmung; wenn Stimmen da sind,
    # müssen Person und Stimmwert tragen.
    for v in r.results:
        assert v.person_fullname, "vote.person_fullname leer – Feldname geändert?"
        assert v.vote is not None, "vote.vote leer – Feldname geändert?"


# ─────────────────────────── /meetings/ ────────────────────────────────────────


async def test_live_search_meetings():
    """Sitzungen einer Körperschaft sind abrufbar und datiert."""
    r = await s.oparl_search_meetings(s.SearchMeetingsInput(body_key=ZURICH, limit=5))
    assert r.results, "Keine Sitzungen für Stadt Zürich – Endpunkt geändert?"
    first = r.results[0]
    assert isinstance(first.name, str) and first.name.strip()
    assert first.begin_date, "meeting.begin_date leer – Feldname geändert?"


# ─────────────────────────── Erreichbarkeit ────────────────────────────────────


async def test_live_source_status_reachable():
    """Der Status-Report meldet die Quelle als erreichbar."""
    r = await s.oparl_source_status(s.SourceStatusInput())
    assert r.reachable is True
    assert r.latency_ms is not None and r.latency_ms >= 0
    assert r.base_url.startswith("https://api.openparldata.ch")
