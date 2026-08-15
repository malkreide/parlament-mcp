#!/usr/bin/env python3
"""Zeichnet je eine echte Antwort pro Abfrage auf.

Warum nicht von Hand geschrieben: eine handgeschriebene Erfolgs-Antwort stimmt
mit dem ueberein, was ihr Autor annahm, und kann die Quelle deshalb nicht
widerlegen. Genau diese Klasse Fehler ist bei dieser Quelle belegt: `/persons/`
verwirft bei `sort_by=lastname` still den `body_key`-Filter und meldet in
`meta.total_records` weiter den gefilterten Wert — die Antwort sieht richtig
aus und ist es nicht. Ein Mock kann das nicht sehen; er gibt zurueck, was man
ihm vorlegt.

Aufgezeichnet wird darum an demselben Ort, an dem der Server die Antwort
entgegennimmt — ueber einen httpx-Response-Hook auf dem geteilten Client aus
`server._get_client()`. Damit tragen Aufzeichnung und Betrieb denselben
User-Agent und dasselbe Timeout.

Ein Host, aber viele Abfrageformen: alles laeuft ueber denselben
OData-Endpunkt `ws.parlament.ch/odata.svc` und unterscheidet sich nur im
`$filter`. Die Portfolio-Regel «eine Antwort je externem Endpunkt» waere mit
einer Datei erfuellt und truege nichts. Der Query-String gehoert deshalb in den
Schluessel.

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

from parlament_mcp import server, transcripts  # noqa: E402

FIXTURES = WURZEL / "tests" / "fixtures"

VERSUCHE = 4

# Wie viele Eintraege einer Trefferliste bleiben. Die Form einer Zeile belegen
# drei genauso gut wie hundert; die Zahl steht je Datei im Nachweis.
ZEILEN = 3


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
    # Wo das Modul des Werkzeugs liegt. Die Transkript-Werkzeuge stehen in
    # `transcripts`, der Rest in `server`.
    modul: str = "server"


# Die Eingaben sind bewusst klein gehalten (`limit=3` statt der Standardwerte):
# die Form einer Antwort belegen drei Zeilen so gut wie zwanzig, und der Ordner
# bleibt lesbar.
#
# Zwei Eingaben stehen hier mit `0` und werden von `main()` zur Laufzeit
# gesetzt: die IDs fuer `parlament_get_business` und `parlament_get_transcript`
# kommen aus der jeweiligen Suche. Eine fest eingetragene ID waere in ein paar
# Wochen ein toter Verweis, und die Aufzeichnung schwiege darueber.
PLAN: list[Aufruf] = [
    Aufruf(
        "search_business",
        "parlament_search_business",
        "SearchBusinessInput",
        {"keyword": "Klima", "limit": 3},
    ),
    Aufruf(
        "get_business",
        "parlament_get_business",
        "GetBusinessInput",
        {"business_id": 0},
    ),
    Aufruf(
        "search_members",
        "parlament_search_members",
        "SearchMembersInput",
        {"canton": "BE", "limit": 3},
    ),
    Aufruf(
        "get_votes",
        "parlament_get_votes",
        "GetVotesInput",
        {"keyword": "Klima", "limit": 3},
    ),
    Aufruf("get_sessions", "parlament_get_sessions", "GetSessionsInput", {"limit": 3}),
    Aufruf(
        "search_transcripts",
        "parlament_search_transcripts",
        "SearchTranscriptsInput",
        {"keyword": "Klima", "limit": 3},
        modul="transcripts",
    ),
    Aufruf(
        "get_transcript",
        "parlament_get_transcript",
        "GetTranscriptInput",
        {"transcript_id": 0},
        # Ein Transkript ist ein Text, keine Trefferliste — der Server liest
        # ihn ganz und gibt ihn seitenweise aus.
        kuerzen=False,
        notiz="Ungekuerzt: der Server paginiert *in* diesem Text.",
        modul="transcripts",
    ),
]


def schluessel_fuer(request: httpx.Request) -> str:
    """Woran eine Anfrage beim Abspielen wiedererkannt wird.

    Die volle URL samt Query-String. Ohne ihn waeren die Abfragen
    ununterscheidbar: alle gehen an denselben OData-Endpunkt und tragen ihre
    Bedeutung allein im `$filter`.
    """
    return str(request.url)


def _endung(text: str) -> str:
    """`.json`, wenn die Antwort JSON ist — sonst `.xml`.

    OData antwortet je nach `$format` mit Atom-XML. Ein Loader, der ueberall
    JSON erwartet, faellt dort ueber die erste Zeile; die Endung sagt es vorher.
    """
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return ".xml"
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


def _werkzeug(a: Aufruf) -> tuple[Any, Any]:
    """Funktion und Eingabeklasse eines Aufrufs — aus `server` oder `transcripts`."""
    modul = server if a.modul == "server" else transcripts
    return getattr(server, a.werkzeug), getattr(modul, a.klasse)


async def _fahre(a: Aufruf, client: httpx.AsyncClient) -> list[Antwort]:
    """Ruft ein Werkzeug und gibt die dabei gesehenen Antworten zurueck."""
    fn, klasse = _werkzeug(a)
    modell = klasse(**a.eingabe)
    letzter: Exception | None = None

    for versuch in range(VERSUCHE):
        if versuch:
            await asyncio.sleep(2**versuch)
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

    Nur die Zahl der Eintraege, nie ein Feld. Zaehlfelder daneben bleiben
    stehen: die Quelle meint damit die Gesamtzahl und nicht die Zahl der
    gelieferten Zeilen, und genau die liest der Server aus.
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


async def _erste_business_id(client: httpx.AsyncClient) -> int:
    """Nimmt die ID des ersten Treffers einer Geschaeftssuche."""
    treffer = await server.parlament_search_business(
        server.SearchBusinessInput(keyword="Klima", limit=1)
    )
    if not treffer.results:
        raise RuntimeError("die Geschaeftssuche liefert keinen Treffer fuer den Detail-Abruf")
    return int(treffer.results[0].id)


async def _erste_transkript_id(client: httpx.AsyncClient) -> int:
    """Nimmt die ID des ersten Treffers einer Transkriptsuche."""
    treffer = await server.parlament_search_transcripts(
        transcripts.SearchTranscriptsInput(keyword="Klima", limit=1)
    )
    if not treffer.results:
        raise RuntimeError("die Transkriptsuche liefert keinen Treffer fuer den Detail-Abruf")
    return int(treffer.results[0].transcript_id)


async def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    heute = datetime.now(UTC).date().isoformat()
    nach_schluessel: dict[str, Antwort] = {}
    zaehler: dict[str, int] = {}

    client = server._get_client()
    try:
        business_id = await _erste_business_id(client)
        transkript_id = await _erste_transkript_id(client)
        print(f"Geschaeft {business_id}, Transkript {transkript_id}", file=sys.stderr)
        zur_laufzeit = {
            "get_business": {"business_id": business_id},
            "get_transcript": {"transcript_id": transkript_id},
        }
        aufrufe = [
            Aufruf(
                a.name,
                a.werkzeug,
                a.klasse,
                {**a.eingabe, **zur_laufzeit.get(a.name, {})},
                a.kuerzen,
                a.notiz,
                a.modul,
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
        if server._http_client is not None:
            await server._http_client.aclose()
            server._http_client = None

    for antwort in nach_schluessel.values():
        antwort.original_bytes = len(antwort.text.encode("utf-8"))
        try:
            daten = json.loads(antwort.text)
        except json.JSONDecodeError:
            # Nicht jede Antwort ist JSON — OData kann Atom-XML liefern.
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
        "Eine Antwort je **Abfrage**, nicht je Endpunkt: alles laeuft ueber denselben",
        "OData-Endpunkt `ws.parlament.ch/odata.svc` und unterscheidet sich nur im",
        "`$filter`. Eine Datei wuerde die Portfolio-Regel erfuellen und nichts belegen.",
        "",
        "Der **Schluessel** unten ist, woran der Test eine Anfrage wiedererkennt: die",
        "volle URL samt Query-String.",
        "",
        "Die Antworten stammen aus dem geteilten Client von `server._get_client()`",
        "(gleicher User-Agent, gleiches Timeout wie im Betrieb), abgegriffen ueber einen",
        "httpx-Response-Hook. Ausgeloest hat sie jeweils das Werkzeug selbst — so belegt",
        "die Aufzeichnung auch, dass das Werkzeug genau diese Anfrage schickt.",
        "",
        "Das ist hier keine Formsache. Diese Quelle antwortet auf falsch verstandene",
        "Parameter nicht mit einem Fehler, sondern mit plausiblen Daten: `/persons/`",
        "verwirft bei `sort_by=lastname` still den `body_key`-Filter und meldet in",
        "`meta.total_records` weiter den gefilterten Wert. Ein Mock kann das nicht",
        "sehen — er gibt zurueck, was man ihm vorlegt.",
        "",
        "## Auswahl",
        "",
        "Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der",
        "Listeneintraege. Kein Feld eines behaltenen Eintrags ist angetastet, und",
        "Zaehlfelder daneben stehen wie geliefert — gerade sie sind hier der Beleg.",
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
                "- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, "
                "ein Schnitt erfaende ein anderes Ergebnis"
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
