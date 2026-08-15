"""Jedes Werkzeug, gefahren aus einer aufgezeichneten Antwort.

Die handgeschriebenen Stubs im Rest der Suite pruefen die *Fehler*-Pfade — ein
Timeout, ein 5xx, eine leere Trefferliste —, die sich nicht auf Zuruf
aufzeichnen lassen und als Erfindung in Ordnung sind. Was sie nicht koennen: die
Form einer Erfolgs-Antwort belegen. Sie stimmen mit dem ueberein, was ihr Autor
annahm.

Bei dieser Quelle ist das keine Formsache. Sie antwortet auf falsch verstandene
Parameter nicht mit einem Fehler, sondern mit plausiblen Daten: `/persons/`
verwirft bei `sort_by=lastname` still den `body_key`-Filter und meldet in
`meta.total_records` weiter den gefilterten Wert. Ein Mock kann diese Klasse
Fehler nicht sehen — er gibt zurueck, was man ihm vorlegt.

Ein Host, aber viele Abfrageformen: alles laeuft ueber denselben OData-Endpunkt
und unterscheidet sich nur im `$filter`. Der Query-String gehoert deshalb in den
Schluessel; ohne ihn waeren die Abfragen ununterscheidbar und der Dispatcher
gaebe allen dieselbe Antwort.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei stehen in
`tests/fixtures/PROVENANCE.md`; neu aufzeichnen mit
`PYTHONPATH=src python scripts/record_fixtures.py`.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import httpx
import pytest
import respx
from fixture_data import (
    fixture_json,
    fixture_text,
    provenance,
    recorded_names,
    recorder,
    schluessel_fuer,
    schluesselverzeichnis,
)

from parlament_mcp import server, transcripts

# Werkzeug → (Modul der Eingabeklasse, Eingabeklasse, Eingabe). Bewusst noch
# einmal hingeschrieben und nicht aus dem Recorder-Plan abgeleitet: die Tests
# sollen eine eigene Aussage machen. Dass beide dieselben Aufrufe fahren, prueft
# `test_der_recorder_faehrt_dieselben_aufrufe`.
#
# Die beiden Detail-Abrufe stehen ohne ID: sie kommt aus dem Nachweis, wie beim
# Aufzeichnen aus der Suche. Eine feste Zahl waere beim naechsten Aufzeichnen
# ein toter Verweis.
WERKZEUGE: dict[str, tuple[Any, str, dict[str, Any]]] = {
    "search_business": (server, "SearchBusinessInput", {"keyword": "Klima", "limit": 3}),
    "search_members": (server, "SearchMembersInput", {"canton": "BE", "limit": 3}),
    "get_votes": (server, "GetVotesInput", {"keyword": "Klima", "limit": 3}),
    "get_sessions": (server, "GetSessionsInput", {"limit": 3}),
    "search_transcripts": (
        transcripts,
        "SearchTranscriptsInput",
        {"keyword": "Klima", "limit": 3},
    ),
}

# Werkzeug → Funktionsname am Server-Modul.
FUNKTION = {
    "search_business": "parlament_search_business",
    "search_members": "parlament_search_members",
    "get_votes": "parlament_get_votes",
    "get_sessions": "parlament_get_sessions",
    "search_transcripts": "parlament_search_transcripts",
    "get_business": "parlament_get_business",
    "get_transcript": "parlament_get_transcript",
}


@pytest.fixture
def quelle():
    """Beantwortet jede Anfrage aus ihrer eigenen Aufzeichnung und protokolliert mit.

    Nach der *Anfrage* zugeordnet, nicht nach der Reihenfolge — und der
    Query-String gehoert dazu: alle Abfragen gehen an dieselbe Adresse und
    tragen ihre Bedeutung im `$filter`. Eine Anfrage ohne Aufzeichnung faellt
    hier laut auf, statt still eine fremde Datei zu bekommen.
    """
    protokoll: list[httpx.Request] = []
    verzeichnis = schluesselverzeichnis()

    def antwort(request: httpx.Request) -> httpx.Response:
        protokoll.append(request)
        schluessel = schluessel_fuer(request)
        name = verzeichnis.get(schluessel)
        if name is None:
            raise AssertionError(
                f"keine Aufzeichnung fuer diese Anfrage:\n  {schluessel}\n"
                "Neu aufzeichnen mit `PYTHONPATH=src python scripts/record_fixtures.py`."
            )
        return httpx.Response(200, text=fixture_text(name))

    with respx.mock:
        respx.route().mock(side_effect=antwort)
        yield protokoll


def _id_aus_dem_nachweis(muster: str) -> int:
    """Die ID, unter der ein Detail-Abruf aufgezeichnet ist — aus dem Schluessel.

    Der Recorder setzt sie zur Laufzeit aus der jeweiligen Suche. Sie hier noch
    einmal hinzuschreiben hiesse, sie beim naechsten Aufzeichnen zu vergessen.
    """
    for schluessel in schluesselverzeichnis():
        treffer = re.search(muster, schluessel)
        if treffer:
            return int(treffer.group(1))
    raise AssertionError(f"keine Aufzeichnung zu {muster} im Nachweis gefunden")


async def _fahre(name: str) -> Any:
    """Ruft ein Werkzeug mit der Eingabe aus der Tabelle."""
    if name == "get_business":
        modell = server.GetBusinessInput(business_id=_id_aus_dem_nachweis(r"/Business\(ID=(\d+),"))
    elif name == "get_transcript":
        modell = transcripts.GetTranscriptInput(
            transcript_id=_id_aus_dem_nachweis(r"/Transcript\(ID=(\d+)L,")
        )
    else:
        modul, klasse, eingabe = WERKZEUGE[name]
        modell = getattr(modul, klasse)(**eingabe)
    return await getattr(server, FUNKTION[name])(modell)


# --------------------------------------------------------------------------
# Herkunft
# --------------------------------------------------------------------------
def test_provenance_nennt_ein_brauchbares_aufnahmedatum():
    """Eine Aufzeichnung ohne Datum ist eine undatierte Behauptung ueber die Quelle."""
    treffer = re.search(r"Aufgezeichnet am \*\*(\d{4}-\d{2}-\d{2})\*\*", provenance())
    assert treffer, "PROVENANCE.md nennt kein Aufnahmedatum im erwarteten Format"
    wann = dt.date.fromisoformat(treffer.group(1))
    assert wann <= dt.datetime.now(dt.UTC).date(), "Aufnahmedatum liegt in der Zukunft"


def test_jede_fixture_steht_in_der_provenance():
    """Sonst waechst der Ordner und der Nachweis bleibt zurueck."""
    text = provenance()
    fehlend = [n for n in recorded_names() if f"## `{n}`" not in text]
    assert not fehlend, f"ohne Eintrag in PROVENANCE.md: {fehlend}"


def test_jeder_schluessel_zeigt_auf_eine_vorhandene_datei():
    """Der Nachweis traegt hier den Abspielbetrieb — er darf nicht ins Leere zeigen."""
    fehlend = sorted(set(schluesselverzeichnis().values()) - set(recorded_names()))
    assert not fehlend, f"im Nachweis genannt, aber nicht vorhanden: {fehlend}"


def test_keine_aufzeichnung_liegt_unbenutzt_herum():
    """Die Gegenrichtung — eine Datei, die kein Schluessel erreicht, belegt nichts."""
    ueberzaehlig = sorted(set(recorded_names()) - set(schluesselverzeichnis().values()))
    assert not ueberzaehlig, f"von keinem Schluessel erreicht: {ueberzaehlig}"


def test_der_recorder_faehrt_dieselben_aufrufe():
    """Recorder und Tests duerfen nicht auseinanderlaufen.

    Laedt `scripts/record_fixtures.py` als Modul — `main()` wird nicht gerufen,
    es geht keine Anfrage raus. Damit ist zugleich geprueft, dass der Recorder
    ueberhaupt importierbar ist: ihn ruft im Betrieb niemand auf.
    """
    im_plan = {a.name for a in recorder().PLAN}
    assert im_plan == set(FUNKTION), "Recorder und Testtabelle nennen verschiedene Aufrufe"


def test_der_nachweis_meldet_was_gekuerzt_wurde():
    """Ein Nachweis, der ueber jeder Datei «ungekuerzt» schreibt, belegt nichts.

    `_kuerze` gibt seine Zaehler nach dem Lauf zurueck und nicht als
    `return vorher, nachher, geh(daten)` — Python liest die beiden Zahlen sonst,
    *bevor* `geh` sie hochzaehlt, und meldet immer (0, 0). In vier
    Schwester-Servern stand deshalb «ungekuerzt» ueber jeder gekuerzten Datei.
    """
    modul = recorder()
    vorher, nachher, gekuerzt = modul._kuerze({"a": list(range(modul.ZEILEN * 3))})
    assert (vorher, nachher) == (modul.ZEILEN * 3, modul.ZEILEN), (
        f"_kuerze meldet {vorher}→{nachher} statt {modul.ZEILEN * 3}→{modul.ZEILEN}"
    )
    assert len(gekuerzt["a"]) == modul.ZEILEN


@pytest.mark.parametrize("name", sorted(n for n in recorded_names() if n.endswith(".json")))
def test_keine_aufzeichnung_ist_leer(name):
    """Eine leere Antwort sieht aus wie eine gueltige und prueft nichts."""
    daten = fixture_json(name)
    assert daten not in ([], {}, None), f"{name} ist leer — neu aufzeichnen"
    # OData legt seine Treffer direkt unter `d` ab — als Liste, nicht unter
    # einem `results`-Schluessel. Ein Stub mit `{"d": {"results": [...]}}` sieht
    # aehnlich aus und ist eine andere Form; der Server liest `data.get("d", [])`
    # und iterierte darueber die Schluessel des Objekts.
    ergebnisse = daten.get("d") if isinstance(daten, dict) else None
    if isinstance(ergebnisse, list):
        assert ergebnisse, f"{name} traegt keine Treffer — neu aufzeichnen"


def test_die_schluessel_unterscheiden_sich_im_filter():
    """Der Grund, warum der Query-String in den Schluessel gehoert.

    Alle Aufzeichnungen liegen unter demselben Host; die Suchen unterscheiden
    sich allein im `$filter`. Ein Dispatcher, der nur Schema und Host liest,
    gaebe allen dieselbe Antwort.
    """
    schluessel = list(schluesselverzeichnis())
    assert len(set(schluessel)) == len(schluessel), (
        "zwei Aufzeichnungen tragen denselben Schluessel"
    )
    hosts = {httpx.URL(s).host for s in schluessel}
    assert len(hosts) == 1, f"mehr als ein Host — die Annahme stimmt nicht mehr: {hosts}"
    mit_filter = [s for s in schluessel if "%24filter=" in s]
    assert len(mit_filter) >= 4, f"nur {len(mit_filter)} Abfragen tragen einen Filter"


# --------------------------------------------------------------------------
# Die Werkzeuge, jedes an seiner eigenen Antwort
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(FUNKTION))
async def test_jedes_werkzeug_liest_seine_aufgezeichnete_antwort(quelle, name):
    """Der eigentliche Punkt: jede Abfrage bekommt *ihre* Antwort.

    Alle mit derselben zu bedienen hiesse, die Aufzeichnung gegen eine Abfrage
    zu halten, die sie nicht beantwortet. Der Dispatcher faellt laut, wenn eine
    Anfrage keine Aufzeichnung hat.
    """
    ergebnis = await _fahre(name)
    assert ergebnis is not None, f"{name} liefert nichts"
    assert quelle, f"{name} hat gar keine Anfrage abgeschickt"


@pytest.mark.parametrize("name", sorted(set(WERKZEUGE)))
async def test_die_suchen_geben_die_aufgezeichneten_zeilen_weiter(quelle, name):
    """«Kommt ohne Fehler zurueck» ist als Zusicherung zu duenn.

    Eine Antwort, in der nichts steht, ist auch fehlerfrei. Geprueft wird
    deshalb, dass die aufgezeichneten Zeilen bis in die Ausgabe durchkommen —
    und dass keine davon leer bleibt.
    """
    ergebnis = await _fahre(name)
    assert ergebnis.results, f"{name} liefert eine leere Trefferliste"
    assert ergebnis.count == len(ergebnis.results), (
        f"{name} meldet {ergebnis.count} Treffer bei {len(ergebnis.results)} Zeilen"
    )


async def test_die_geschaeftssuche_liest_titel_und_nummer(quelle):
    """Ein leeres Feld sieht aus wie ein fehlendes und ist ein anderer Befund.

    Genau hier lag der Fund in zwei Schwester-Servern: die Quelle nennt ihr
    Label anders, als der Code annahm, und drei Werkzeuge lieferten leere Titel
    bei gruener Suite.
    """
    ergebnis = await _fahre("search_business")
    for posten in ergebnis.results:
        assert posten.title, f"Geschaeft {posten.id} ohne Titel"
        assert posten.id, f"Geschaeft ohne ID: {posten}"


async def test_das_transkript_steht_ungekuerzt_im_ordner(quelle):
    """Der Server paginiert *in* dem Text — gekuerzt waere jede Seite eine andere."""
    datei = next(v for v in schluesselverzeichnis().values() if v.startswith("get_transcript_"))
    block = provenance().split(f"## `{datei}`", 1)[1].split("## ", 1)[0]
    assert "ungekuerzt" in block, block
    ergebnis = await _fahre("get_transcript")
    assert ergebnis.text, "das Transkript kommt ohne Text zurueck"


# --------------------------------------------------------------------------
# Die Gegenrichtung
# --------------------------------------------------------------------------
@respx.mock
async def test_eine_leere_trefferliste_bleibt_eine_leere_trefferliste():
    """`"d": []` ist eine Aussage der Quelle: dazu gibt es nichts.

    Das darf nicht als Fehler herauskommen — sonst kann das Modell einen echten
    Negativtreffer nicht von einem Ausfall unterscheiden.
    """
    respx.route().mock(return_value=httpx.Response(200, json={"d": []}))
    ergebnis = await server.parlament_search_business(
        server.SearchBusinessInput(keyword="Klima", limit=3)
    )
    assert ergebnis.results == []
    assert ergebnis.count == 0


@respx.mock
async def test_ein_abbruch_bleibt_ein_fehler(monkeypatch):
    """Und die andere Haelfte: ein Ausfall darf nicht als leeres Ergebnis erscheinen."""
    monkeypatch.setattr(server, "RETRY_BACKOFF_BASE", 0, raising=False)
    respx.route().mock(side_effect=httpx.ConnectError("weg"))
    with pytest.raises(Exception) as fehler:
        await server.parlament_search_business(server.SearchBusinessInput(keyword="Klima", limit=3))
    assert "weg" in str(fehler.value) or "rror" in str(fehler.value), str(fehler.value)[:200]
