#!/usr/bin/env python3
"""Zeichnet je eine echte Antwort pro Abfrage auf.

Warum nicht von Hand geschrieben: eine handgeschriebene Erfolgs-Antwort stimmt
mit dem ueberein, was ihr Autor annahm, und kann die Quelle deshalb nicht
widerlegen. Genau diese Klasse Fehler ist hier belegt und steht im `CLAUDE.md`
des Wurzelprojekts: `/persons/` verwirft bei `sort_by=lastname` still den
`body_key`-Filter und meldet in `meta.total_records` weiter den korrekt
gefilterten Wert — die Antwort sieht richtig aus und ist es nicht. Ein Mock
kann das nicht sehen; er gibt zurueck, was man ihm vorlegt.

Aufgezeichnet wird darum an demselben Ort, an dem der Server die Antwort
entgegennimmt — ueber einen httpx-Response-Hook auf dem geteilten Client aus
`client.get_client()`. Damit tragen Aufzeichnung und Betrieb denselben
User-Agent und dasselbe Timeout.

Ein Host, aber viele Abfrageformen: alles laeuft ueber
`api.openparldata.ch/v1` und unterscheidet sich im Pfad und in den
Query-Parametern. Die volle URL gehoert deshalb in den Schluessel.

Zugeordnet wird beim Abspielen nach der Anfrage und nicht nach der Reihenfolge:
`oparl_compare_bodies` fragt mehrere Koerperschaften in einem Aufruf ab.

## Aufruf

    PYTHONPATH=src python scripts/record_fixtures.py

Schreibt nach `tests/fixtures/` und erzeugt `tests/fixtures/PROVENANCE.md` neu.
Dateien, die kein Plan-Eintrag mehr erzeugt, werden geloescht — sonst waechst
der Ordner und der Nachweis bleibt zurueck.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from openparldata_mcp import bodies as body_cache
from openparldata_mcp import client as api_client
from openparldata_mcp import server

FIXTURES = WURZEL / "tests" / "fixtures"

VERSUCHE = 4

# Wie viele Eintraege einer Trefferliste bleiben. Die Form einer Zeile belegen
# drei genauso gut wie hundert; die Zahl steht je Datei im Nachweis.
ZEILEN = 3

# Die Koerperschaft, gegen die aufgezeichnet wird: Stadt Zuerich. Eine mit
# Betrieb — ein Gemeindeparlament ohne Geschaefte im Zeitfenster liefert leere
# Listen, und die belegen keine Zeilenform.
KOERPERSCHAFT = "261"


@dataclass(frozen=True)
class Aufruf:
    """Ein Werkzeugaufruf, der Anfragen ausloesen soll."""

    name: str
    werkzeug: str
    klasse: str
    eingabe: dict[str, Any]
    # Kuerzen ist nur dort harmlos, wo der Server die Liste ganz liest. Filtert
    # oder zaehlt er *in* ihr, schneidet ein Schnitt womoeglich genau die Zeile
    # weg, die er sucht.
    kuerzen: bool = True
    notiz: str = ""


# Eingaben mit `0` oder leerem Wert setzt `main()` zur Laufzeit aus dem Ergebnis
# der jeweiligen Suche. Eine fest eingetragene ID waere in ein paar Wochen ein
# toter Verweis, und die Aufzeichnung schwiege darueber.
PLAN: list[Aufruf] = [
    Aufruf(
        "list_bodies",
        "oparl_list_bodies",
        "ListBodiesInput",
        {"search": "Zürich"},
        # Der Server sucht *in* dieser Liste nach der passenden Koerperschaft.
        kuerzen=False,
        notiz="Ungekuerzt: der Server sucht die Koerperschaft *in* dieser Liste.",
    ),
    Aufruf(
        "search_affairs",
        "oparl_search_affairs",
        "SearchAffairsInput",
        {"body_key": KOERPERSCHAFT, "search": "Klima", "limit": 3},
    ),
    Aufruf("get_affair", "oparl_get_affair", "GetAffairInput", {"affair_id": 0}),
    Aufruf(
        "affair_documents",
        "oparl_get_affair_documents",
        "GetAffairDocumentsInput",
        {"affair_id": 0},
    ),
    Aufruf(
        "compare_bodies",
        "oparl_compare_bodies",
        "CompareBodiesInput",
        {"search": "Klima"},
        kuerzen=False,
        notiz="Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.",
    ),
    Aufruf(
        "search_persons",
        "oparl_search_persons",
        "SearchPersonsInput",
        {"body_key": KOERPERSCHAFT, "limit": 3},
    ),
    Aufruf("get_person", "oparl_get_person", "GetPersonInput", {"person_id": 0}),
    Aufruf(
        "person_interests",
        "oparl_get_person_interests",
        "GetPersonInterestsInput",
        {"person_id": 0},
    ),
    Aufruf(
        "search_interests",
        "oparl_search_interests",
        "SearchInterestsInput",
        {"body_key": KOERPERSCHAFT, "limit": 3},
    ),
    Aufruf(
        "get_votings",
        "oparl_get_votings",
        "GetVotingsInput",
        {"body_key": KOERPERSCHAFT, "limit": 3},
    ),
    Aufruf(
        "voting_results",
        "oparl_get_voting_results",
        "GetVotingResultsInput",
        {"voting_id": 0},
        # Der Server zaehlt Ja/Nein/Enthaltung *in* dieser Liste. Gekuerzt
        # stimmte kein Ergebnis mehr.
        kuerzen=False,
        notiz="Ungekuerzt: der Server zaehlt die Stimmen *in* dieser Liste.",
    ),
    Aufruf(
        "search_meetings",
        "oparl_search_meetings",
        "SearchMeetingsInput",
        {"body_key": KOERPERSCHAFT, "limit": 3},
    ),
    Aufruf("source_status", "oparl_source_status", "SourceStatusInput", {}),
]


def schluessel_fuer(request: httpx.Request) -> str:
    """Woran eine Anfrage beim Abspielen wiedererkannt wird.

    Die volle URL samt Query-String. Ohne ihn waeren die Abfragen kaum zu
    unterscheiden: alle gehen an denselben Host, und der `body_key` steht als
    Parameter.
    """
    return str(request.url)


def _endung(text: str) -> str:
    """`.json`, wenn die Antwort JSON ist — sonst `.txt`."""
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return ".txt"
    return ".json"


@dataclass
class Antwort:
    """Eine gesehene Antwort samt der Anfrage, die sie ausgeloest hat."""

    schluessel: str
    text: str
    werkzeuge: list[str] = field(default_factory=list)
    darf_kuerzen: bool = True
    notiz: str = ""
    dateiname: str = ""
    original_bytes: int = 0
    gekuerzt_von: int = 0
    behalten: int = 0
    sha256: str = ""
    bytes: int = 0


def _hook_fuer(gesehen: list[Antwort]) -> Callable[[httpx.Response], Awaitable[None]]:
    """Baut den Response-Hook fuer einen Versuch.

    Eigene Funktion, damit die Liste als Argument gebunden ist und nicht als
    Schleifenvariable aus dem umgebenden Namensraum (ruff B023).
    """

    async def hook(response: httpx.Response) -> None:
        await response.aread()
        if response.status_code >= 400:
            # Eine Fehlerantwort als Fixture abzulegen hiesse, sie als das
            # auszugeben, was die Quelle normalerweise sagt.
            print(
                f"– nicht aufgezeichnet (HTTP {response.status_code}): {response.request.url}",
                file=sys.stderr,
            )
            return
        gesehen.append(Antwort(schluessel=schluessel_fuer(response.request), text=response.text))

    return hook


async def _fahre(a: Aufruf, client: httpx.AsyncClient) -> list[Antwort]:
    """Ruft ein Werkzeug und gibt die dabei gesehenen Antworten zurueck."""
    fn = getattr(server, a.werkzeug)
    modell = getattr(server, a.klasse)(**a.eingabe)
    letzter: Exception | None = None

    for versuch in range(VERSUCHE):
        if versuch:
            await asyncio.sleep(2**versuch)
        # Der Body-Cache haelt 24 h. Ohne Reset schickt `oparl_list_bodies`
        # beim zweiten Aufruf keine Anfrage mehr, und die Aufzeichnung fehlte
        # genau fuer das Werkzeug, das sie am noetigsten hat.
        body_cache._cache.bodies = {}
        body_cache._cache.loaded_at = None
        gesehen: list[Antwort] = []
        hook = _hook_fuer(gesehen)
        client.event_hooks.setdefault("response", []).append(hook)
        try:
            await fn(modell)
        except Exception as e:  # noqa: BLE001 — jeder Fehler ist hier ein Retry-Grund
            letzter = e
            continue
        finally:
            client.event_hooks["response"].remove(hook)

        if not gesehen:
            letzter = RuntimeError(f"{a.werkzeug} hat keine Anfrage abgeschickt")
            continue
        for antwort in gesehen:
            antwort.werkzeuge.append(a.werkzeug)
            antwort.darf_kuerzen = a.kuerzen
            antwort.notiz = a.notiz
        return gesehen

    raise RuntimeError(f"{a.name} nach {VERSUCHE} Versuchen nicht aufgezeichnet: {letzter}")


def _kuerze(daten: Any) -> tuple[int, int, Any]:
    """Kuerzt jede Liste im Baum auf `ZEILEN`; gibt (vorher, nachher, Daten).

    Nur die Zahl der Eintraege, nie ein Feld. `meta.total_records` daneben
    bleibt stehen: die Quelle meint damit die Gesamtzahl und nicht die Zahl der
    gelieferten Zeilen — und genau dieses Feld ist hier der Beleg dafuer, dass
    ein stillschweigend verworfener Filter sichtbar wird.
    """
    vorher = nachher = 0

    def geh(knoten: Any) -> Any:
        nonlocal vorher, nachher
        if isinstance(knoten, dict):
            return {k: geh(v) for k, v in knoten.items()}
        if isinstance(knoten, list):
            vorher += len(knoten)
            gekuerzt = knoten[:ZEILEN]
            nachher += len(gekuerzt)
            return [geh(v) for v in gekuerzt]
        return knoten

    # Erst laufen lassen, dann die Zaehler lesen. `return vorher, nachher,
    # geh(daten)` wertet von links nach rechts aus und lieferte deshalb immer
    # (0, 0) — der Nachweis schriebe «ungekuerzt» ueber jede gekuerzte Datei.
    ergebnis = geh(daten)
    return vorher, nachher, ergebnis


async def _laufzeit_ids() -> dict[str, dict[str, Any]]:
    """Holt die IDs, die die Detail-Abrufe brauchen, aus den Suchen daneben.

    Fest eingetragene IDs waeren in ein paar Wochen tote Verweise — und schlimmer:
    wer eine Aufzeichnung sucht, die zu einer eingetragenen ID passt, waehlt am
    Ende die Antwort nach dem aus, was er sehen will.
    """
    affairs = await server.oparl_search_affairs(
        server.SearchAffairsInput(body_key=KOERPERSCHAFT, search="Klima", limit=1)
    )
    if not affairs.results:
        raise RuntimeError("die Geschaeftssuche liefert keinen Treffer fuer den Detail-Abruf")
    affair_id = int(affairs.results[0].id)

    persons = await server.oparl_search_persons(
        server.SearchPersonsInput(body_key=KOERPERSCHAFT, limit=1)
    )
    if not persons.results:
        raise RuntimeError("die Personensuche liefert keinen Treffer fuer den Detail-Abruf")
    person_id = int(persons.results[0].id)

    votings = await server.oparl_get_votings(
        server.GetVotingsInput(body_key=KOERPERSCHAFT, limit=1)
    )
    if not votings.results:
        raise RuntimeError("die Abstimmungssuche liefert keinen Treffer fuer den Detail-Abruf")
    voting_id = int(votings.results[0].id)

    return {
        "get_affair": {"affair_id": affair_id},
        "affair_documents": {"affair_id": affair_id},
        "get_person": {"person_id": person_id},
        "person_interests": {"person_id": person_id},
        "voting_results": {"voting_id": voting_id},
    }


async def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    heute = datetime.now(UTC).date().isoformat()
    nach_schluessel: dict[str, Antwort] = {}
    zaehler: dict[str, int] = {}

    client = api_client.get_client()
    try:
        zur_laufzeit = await _laufzeit_ids()
        print(f"Laufzeit-IDs: {zur_laufzeit}", file=sys.stderr)
        aufrufe = [
            Aufruf(
                a.name,
                a.werkzeug,
                a.klasse,
                {**a.eingabe, **zur_laufzeit.get(a.name, {})},
                a.kuerzen,
                a.notiz,
            )
            for a in PLAN
        ]
        for a in aufrufe:
            print(f"… {a.werkzeug} ({a.name})", file=sys.stderr)
            for antwort in await _fahre(a, client):
                if antwort.schluessel in nach_schluessel:
                    vorhanden = nach_schluessel[antwort.schluessel]
                    if a.werkzeug not in vorhanden.werkzeuge:
                        vorhanden.werkzeuge.append(a.werkzeug)
                    continue
                zaehler[a.name] = zaehler.get(a.name, 0) + 1
                antwort.dateiname = f"{a.name}_{zaehler[a.name]}{_endung(antwort.text)}"
                nach_schluessel[antwort.schluessel] = antwort
    finally:
        await api_client.aclose()

    for antwort in nach_schluessel.values():
        antwort.original_bytes = len(antwort.text.encode("utf-8"))
        try:
            daten = json.loads(antwort.text)
        except json.JSONDecodeError:
            (FIXTURES / antwort.dateiname).write_text(antwort.text, encoding="utf-8")
            roh = (FIXTURES / antwort.dateiname).read_bytes()
            antwort.sha256 = hashlib.sha256(roh).hexdigest()
            antwort.bytes = len(roh)
            continue
        if antwort.darf_kuerzen:
            antwort.gekuerzt_von, antwort.behalten, daten = _kuerze(daten)
        # Neu eingerueckt geschrieben: eine Zeile JSON waere kleiner, aber im
        # Diff nicht lesbar, und ein Fixture will gelesen werden.
        (FIXTURES / antwort.dateiname).write_text(
            json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        roh = (FIXTURES / antwort.dateiname).read_bytes()
        antwort.sha256 = hashlib.sha256(roh).hexdigest()
        antwort.bytes = len(roh)

    antworten = sorted(nach_schluessel.values(), key=lambda x: x.dateiname)
    _schreibe_provenance(antworten, heute)

    # Aufraeumen: was kein Plan-Eintrag mehr erzeugt, hat auch keinen Nachweis.
    geschrieben = {a.dateiname for a in antworten} | {"PROVENANCE.md"}
    for pfad in sorted(FIXTURES.iterdir()):
        if pfad.name not in geschrieben:
            print(f"– entferne veraltet: {pfad.name}", file=sys.stderr)
            pfad.unlink()

    print(f"{len(antworten)} Aufzeichnungen in {FIXTURES}", file=sys.stderr)
    return 0


def _schreibe_provenance(antworten: list[Antwort], heute: str) -> None:
    zeilen = [
        "# Herkunft der Fixtures",
        "",
        f"Aufgezeichnet am **{heute}** mit `PYTHONPATH=src python scripts/record_fixtures.py`.",
        "",
        "Eine Antwort je **Abfrage**, nicht je Endpunkt: alles laeuft ueber",
        "`api.openparldata.ch/v1` und unterscheidet sich im Pfad und in den",
        "Query-Parametern. Eine Datei wuerde die Portfolio-Regel erfuellen und fast",
        "nichts belegen.",
        "",
        "Der **Schluessel** unten ist, woran der Test eine Anfrage wiedererkennt: die",
        "volle URL samt Query-String. Zugeordnet wird nach der Anfrage und nicht nach",
        "der Reihenfolge — `oparl_compare_bodies` fragt mehrere Koerperschaften in",
        "einem Aufruf ab.",
        "",
        "Die Antworten stammen aus dem geteilten Client von `client.get_client()`",
        "(gleicher User-Agent, gleiches Timeout wie im Betrieb), abgegriffen ueber einen",
        "httpx-Response-Hook. Ausgeloest hat sie jeweils das Werkzeug selbst — so belegt",
        "die Aufzeichnung auch, dass das Werkzeug genau diese Anfrage schickt.",
        "",
        "Das ist hier keine Formsache. Diese Quelle antwortet auf falsch verstandene",
        "Parameter nicht mit einem Fehler, sondern mit plausiblen Daten: `/persons/`",
        "verwirft bei `sort_by=lastname` still den `body_key`-Filter und meldet in",
        "`meta.total_records` weiter den korrekt gefilterten Wert. Ein Mock kann das",
        "nicht sehen — er gibt zurueck, was man ihm vorlegt.",
        "",
        "Die IDs der Detail-Abrufe stammen aus den Suchen daneben und stehen nirgends",
        "als Zahl im Code. Sonst muesste die Aufzeichnung zur eingetragenen ID passen —",
        "und der naechstliegende Weg dahin waere, sie danach auszuwaehlen.",
        "",
        "## Auswahl",
        "",
        "Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der",
        "Listeneintraege. Kein Feld eines behaltenen Eintrags ist angetastet, und",
        "`meta.total_records` daneben steht wie geliefert — gerade dieses Feld ist hier",
        "der Beleg.",
        "",
        "Wo der Server *in* einer Liste sucht oder zaehlt, wird nicht gekuerzt: ein",
        "Schnitt erfaende dort ein anderes Ergebnis.",
        "",
        "Die Fehlerpfade — Timeout, 5xx, leere Trefferliste — bleiben handgeschrieben.",
        "Sie lassen sich nicht auf Zuruf aufzeichnen und sind als Erfindung in Ordnung.",
        "",
    ]
    for a in antworten:
        zeilen += [
            f"## `{a.dateiname}`",
            "",
            f"- **Werkzeuge:** {', '.join(f'`{w}`' for w in sorted(a.werkzeuge))}",
            f"- **Schluessel:** `{a.schluessel}`",
        ]
        if a.notiz:
            zeilen.append(f"- **Notiz:** {a.notiz}")
        if a.gekuerzt_von > a.behalten:
            zeilen.append(
                f"- **Auswahl:** {a.behalten} von {a.gekuerzt_von} Listeneintraegen — "
                f"jede Liste im Baum auf die ersten {ZEILEN} gekuerzt, "
                f"aus {a.original_bytes} Bytes Rohantwort"
            )
        elif not a.darf_kuerzen:
            zeilen.append(
                "- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser "
                "Antwort, ein Schnitt erfaende ein anderes Ergebnis"
            )
        else:
            zeilen.append("- **Auswahl:** ungekuerzt")
        zeilen += [
            f"- **Groesse:** {a.bytes} Bytes",
            f"- **SHA-256:** `{a.sha256}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(zeilen), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
