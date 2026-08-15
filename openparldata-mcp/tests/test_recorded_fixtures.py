"""Jedes Werkzeug, gefahren aus einer aufgezeichneten Antwort.

Die handgeschriebenen Stubs im Rest der Suite pruefen die *Fehler*-Pfade — ein
Timeout, ein 5xx, eine leere Trefferliste —, die sich nicht auf Zuruf
aufzeichnen lassen und als Erfindung in Ordnung sind. Was sie nicht koennen: die
Form einer Erfolgs-Antwort belegen. Sie stimmen mit dem ueberein, was ihr Autor
annahm.

Bei dieser Quelle ist das keine Formsache. `bodies.py` sagt es im eigenen Kopf:
«Die API sagt nie Nein, sie sagt Nichts» — ein ungueltiger `body_key` liefert
HTTP 200 mit leerem Array. Und `/persons/` verwirft bei `sort_by=lastname` still
den `body_key`-Filter, waehrend `meta.total_records` weiter den gefilterten Wert
meldet. Ein Mock kann diese Klasse Fehler nicht sehen; er gibt zurueck, was man
ihm vorlegt.

Ein Host, aber viele Abfrageformen. Zugeordnet wird beim Abspielen nach der
Anfrage und nicht nach der Reihenfolge: `oparl_compare_bodies` fragt in einem
Aufruf jede Gemeinde einzeln ab — 69 Anfragen. Eine Zuordnung nach Reihenfolge
waere dort im gruenen Fall bloss zufaellig richtig.

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

from openparldata_mcp import server

KOERPERSCHAFT = "261"

# Werkzeug → (Eingabeklasse, Eingabe). Bewusst noch einmal hingeschrieben und
# nicht aus dem Recorder-Plan abgeleitet: die Tests sollen eine eigene Aussage
# machen. Dass beide dieselben Aufrufe fahren, prueft
# `test_der_recorder_faehrt_dieselben_aufrufe`.
#
# Die Detail-Abrufe stehen ohne ID: sie kommt aus dem Nachweis, wie beim
# Aufzeichnen aus der Suche daneben.
WERKZEUGE: dict[str, tuple[str, str, dict[str, Any]]] = {
    "list_bodies": ("oparl_list_bodies", "ListBodiesInput", {"search": "Zürich"}),
    "search_affairs": (
        "oparl_search_affairs",
        "SearchAffairsInput",
        {"body_key": KOERPERSCHAFT, "search": "Klima", "limit": 3},
    ),
    "compare_bodies": ("oparl_compare_bodies", "CompareBodiesInput", {"search": "Klima"}),
    "search_persons": (
        "oparl_search_persons",
        "SearchPersonsInput",
        {"body_key": KOERPERSCHAFT, "limit": 3},
    ),
    "search_interests": (
        "oparl_search_interests",
        "SearchInterestsInput",
        {"body_key": KOERPERSCHAFT, "limit": 3},
    ),
    "get_votings": (
        "oparl_get_votings",
        "GetVotingsInput",
        {"body_key": KOERPERSCHAFT, "limit": 3},
    ),
    "search_meetings": (
        "oparl_search_meetings",
        "SearchMeetingsInput",
        {"body_key": KOERPERSCHAFT, "limit": 3},
    ),
    "source_status": ("oparl_source_status", "SourceStatusInput", {}),
}

# Die Detail-Abrufe: Werkzeug → (Eingabeklasse, Feld, Muster im Schluessel).
DETAIL: dict[str, tuple[str, str, str, str]] = {
    "get_affair": ("oparl_get_affair", "GetAffairInput", "affair_id", r"/affairs/(\d+)"),
    "affair_documents": (
        "oparl_get_affair_documents",
        "GetAffairDocumentsInput",
        "affair_id",
        r"/affairs/(\d+)",
    ),
    "get_person": ("oparl_get_person", "GetPersonInput", "person_id", r"/persons/(\d+)"),
    "person_interests": (
        "oparl_get_person_interests",
        "GetPersonInterestsInput",
        "person_id",
        r"/persons/(\d+)",
    ),
    "voting_results": (
        "oparl_get_voting_results",
        "GetVotingResultsInput",
        "voting_id",
        r"/votings/(\d+)",
    ),
}


@pytest.fixture
def quelle():
    """Beantwortet jede Anfrage aus ihrer eigenen Aufzeichnung und protokolliert mit.

    Nach der *Anfrage* zugeordnet, nicht nach der Reihenfolge: der Vergleich
    ueber Koerperschaften fragt jede einzeln ab. Eine Anfrage ohne Aufzeichnung
    faellt hier laut auf, statt still eine fremde Datei zu bekommen.
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

    Der Recorder holt sie zur Laufzeit aus der Suche daneben. Sie hier noch
    einmal hinzuschreiben hiesse, sie beim naechsten Aufzeichnen zu vergessen —
    und schlimmer: wer eine Aufzeichnung zu einer eingetragenen ID sucht, waehlt
    am Ende die Antwort nach dem aus, was er sehen will.
    """
    for schluessel in schluesselverzeichnis():
        treffer = re.search(muster, schluessel)
        if treffer:
            return int(treffer.group(1))
    raise AssertionError(f"keine Aufzeichnung zu {muster} im Nachweis gefunden")


async def _fahre(name: str) -> Any:
    """Ruft ein Werkzeug mit der Eingabe aus der Tabelle."""
    if name in DETAIL:
        werkzeug, klasse, feld, muster = DETAIL[name]
        modell = getattr(server, klasse)(**{feld: _id_aus_dem_nachweis(muster)})
    else:
        werkzeug, klasse, eingabe = WERKZEUGE[name]
        modell = getattr(server, klasse)(**eingabe)
    return await getattr(server, werkzeug)(modell)


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
    assert im_plan == set(WERKZEUGE) | set(DETAIL), (
        "Recorder und Testtabelle nennen verschiedene Aufrufe"
    )


def test_der_recorder_zaehlt_was_er_kuerzt():
    """Ein Nachweis, der ueber jeder Datei «ungekuerzt» schreibt, belegt nichts.

    `_kuerze` gibt seine Zaehler nach dem Lauf zurueck und nicht als
    `return vorher, nachher, geh(daten)` — Python liest die beiden Zahlen sonst,
    *bevor* `geh` sie hochzaehlt, und meldet immer (0, 0). In vier
    Schwester-Servern stand deshalb «ungekuerzt» ueber jeder gekuerzten Datei.

    Hier ist derzeit keine Datei gekuerzt (die Abrufe holen von vornherein
    wenige Zeilen) — geprueft wird deshalb die Funktion selbst, damit der Fehler
    nicht still zurueckkehrt, sobald jemand ein groesseres `limit` aufzeichnet.
    """
    modul = recorder()
    vorher, nachher, gekuerzt = modul._kuerze({"a": list(range(modul.ZEILEN * 3))})
    assert (vorher, nachher) == (modul.ZEILEN * 3, modul.ZEILEN), (
        f"_kuerze meldet {vorher}→{nachher} statt {modul.ZEILEN * 3}→{modul.ZEILEN}"
    )
    assert len(gekuerzt["a"]) == modul.ZEILEN


@pytest.mark.parametrize("name", sorted(n for n in recorded_names() if n.endswith(".json")))
def test_keine_aufzeichnung_ist_leer(name):
    """Eine leere Antwort sieht aus wie eine gueltige und prueft nichts.

    Genau das ist hier der gefaehrliche Fall: die API antwortet auf einen
    unbekannten `body_key` mit HTTP 200 und leerem Array. Eine solche Antwort
    als Fixture abzulegen hiesse, einen Negativbefund zu behaupten.
    """
    daten = fixture_json(name)
    assert daten not in ([], {}, None), f"{name} ist leer — neu aufzeichnen"


def test_die_schluessel_unterscheiden_sich_im_query_string():
    """Der Grund, warum die volle URL in den Schluessel gehoert.

    Der Vergleich ueber Koerperschaften trifft denselben Pfad mit verschiedenen
    `body_key`s. Ein Dispatcher, der nur den Pfad liest, gaebe allen dieselbe
    Antwort — und der Vergleich zaehlte fuer jede Gemeinde dasselbe.
    """
    schluessel = list(schluesselverzeichnis())
    assert len(set(schluessel)) == len(schluessel), (
        "zwei Aufzeichnungen tragen denselben Schluessel"
    )
    ohne_query = [s.split("?", 1)[0] for s in schluessel]
    assert len(set(ohne_query)) < len(schluessel), (
        "kein Schluesselpaar teilt sich einen Pfad — dann traegt der Query-String nichts"
    )


def test_die_koerperschaften_stehen_ungekuerzt_im_ordner():
    """Der Server sucht die Koerperschaft *in* dieser Liste.

    Gekuerzt faende er die meisten nicht mehr — und meldete «unbekannter
    body_key» fuer eine, die es gibt.
    """
    datei = next(v for v in schluesselverzeichnis().values() if v.startswith("list_bodies_"))
    block = provenance().split(f"## `{datei}`", 1)[1].split("## ", 1)[0]
    assert "ungekuerzt" in block, block
    daten = fixture_json(datei)
    eintraege = daten.get("data", daten) if isinstance(daten, dict) else daten
    assert len(eintraege) > 50, f"nur {len(eintraege)} Koerperschaften — das ist gekuerzt"


# --------------------------------------------------------------------------
# Die Werkzeuge, jedes an seiner eigenen Antwort
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(set(WERKZEUGE) | set(DETAIL)))
async def test_jedes_werkzeug_liest_seine_aufgezeichnete_antwort(quelle, name):
    """Der eigentliche Punkt: jede Abfrage bekommt *ihre* Antwort.

    Alle mit derselben zu bedienen hiesse, die Aufzeichnung gegen eine Abfrage
    zu halten, die sie nicht beantwortet. Der Dispatcher faellt laut, wenn eine
    Anfrage keine Aufzeichnung hat.
    """
    ergebnis = await _fahre(name)
    assert ergebnis is not None, f"{name} liefert nichts"
    assert quelle, f"{name} hat gar keine Anfrage abgeschickt"


@pytest.mark.parametrize(
    "name", sorted(set(WERKZEUGE) - {"source_status", "compare_bodies", "list_bodies"})
)
async def test_die_suchen_geben_die_aufgezeichneten_zeilen_weiter(quelle, name):
    """«Kommt ohne Fehler zurueck» ist als Zusicherung zu duenn.

    Eine Antwort, in der nichts steht, ist auch fehlerfrei — und hier sogar der
    Normalfall bei einem falsch verstandenen Parameter. Geprueft wird deshalb,
    dass die aufgezeichneten Zeilen bis in die Ausgabe durchkommen.
    """
    ergebnis = await _fahre(name)
    assert ergebnis.results, f"{name} liefert eine leere Trefferliste"


async def test_der_vergleich_fragt_jede_koerperschaft_einzeln(quelle):
    """Der Grund fuer die Zuordnung nach Anfrage — und fuer 69 Dateien.

    `oparl_compare_bodies` zaehlt Treffer je Gemeinde und kann das nur, indem es
    jede einzeln fragt. Eine Zuordnung nach Reihenfolge waere hier mit hoher
    Wahrscheinlichkeit falsch, und im gruenen Fall bloss zufaellig richtig.
    """
    await _fahre("compare_bodies")
    keys = [httpx.URL(str(r.url)).params.get("body_key") for r in quelle]
    gefragt = {k for k in keys if k}
    assert len(gefragt) > 20, f"nur {len(gefragt)} Koerperschaften gefragt: {sorted(gefragt)[:5]}"


async def test_der_vergleich_zaehlt_je_koerperschaft_verschieden(quelle):
    """Wuerde der Dispatcher allen dieselbe Datei geben, waere jede Zahl gleich.

    Genau daran faellt eine Zuordnung nach Reihenfolge auf — an nichts sonst:
    ein Vergleich, in dem alle gleich viele Treffer haben, sieht aus wie ein
    Ergebnis.
    """
    ergebnis = await _fahre("compare_bodies")
    zahlen = {z.match_count for z in ergebnis.results}
    assert len(zahlen) > 1, f"jede Koerperschaft meldet dieselbe Zahl: {zahlen}"


async def test_die_koerperschaft_wird_vor_der_anfrage_geprueft(quelle):
    """Ein unbekannter `body_key` muss auffallen, bevor die Quelle schweigt.

    «Die API sagt nie Nein, sie sagt Nichts» steht im Kopf von `bodies.py`: ein
    unbekannter Key liefert HTTP 200 mit leerem Array. Der Server prueft deshalb
    gegen den Body-Cache — und diese Zusicherung haelt fest, dass er es tut.
    """
    with pytest.raises(Exception) as fehler:
        await server.oparl_search_affairs(
            server.SearchAffairsInput(body_key="9999", search="Klima", limit=3)
        )
    assert "9999" in str(fehler.value), str(fehler.value)[:300]


# --------------------------------------------------------------------------
# Die Gegenrichtung
# --------------------------------------------------------------------------
@respx.mock
async def test_eine_leere_trefferliste_bleibt_eine_leere_trefferliste():
    """Eine leere Liste ist eine Aussage der Quelle: dazu gibt es nichts.

    Das darf nicht als Fehler herauskommen — sonst kann das Modell einen echten
    Negativtreffer nicht von einem Ausfall unterscheiden.
    """
    koerperschaften = fixture_text(
        next(v for v in schluesselverzeichnis().values() if v.startswith("list_bodies_"))
    )

    def antwort(request: httpx.Request) -> httpx.Response:
        if "/bodies/" in str(request.url):
            return httpx.Response(200, text=koerperschaften)
        return httpx.Response(200, json={"data": [], "meta": {"total_records": 0}})

    respx.route().mock(side_effect=antwort)
    ergebnis = await server.oparl_search_affairs(
        server.SearchAffairsInput(body_key=KOERPERSCHAFT, search="Klima", limit=3)
    )
    assert ergebnis.results == []


@respx.mock
async def test_ein_abbruch_bleibt_ein_fehler():
    """Und die andere Haelfte: ein Ausfall darf nicht als leeres Ergebnis erscheinen."""
    respx.route().mock(side_effect=httpx.ConnectError("weg"))
    with pytest.raises(Exception) as fehler:
        await server.oparl_search_affairs(
            server.SearchAffairsInput(body_key=KOERPERSCHAFT, search="Klima", limit=3)
        )
    assert str(fehler.value), "der Ausfall kommt ohne Begruendung zurueck"
