# CLAUDE.md

## Teil 1 — Konventionen (portfolio-weit)

### Vor der Arbeit

Klon-Aktualität prüfen: `git fetch origin main && git rev-list --count HEAD..origin/main`
Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

## Teil 2 — dieses Repo

Zwei Projekte, zwei Gate-Sätze: Bundes-Server (Root, `src/parlament_mcp`) und
`openparldata-mcp/` (eigene `pyproject.toml`, eigener CI-Job).

**ruff:** `ruff==0.16.1`, in beiden CI-Jobs gepinnt (`.github/workflows/ci.yml`).
Eine `.pre-commit-config.yaml` gibt es nicht, es existiert also kein lokales Gate
zum Abgleichen — die Version von Hand setzen. Achtung: ein per `uv tool`
installiertes ruff unter `~/.local/bin` beschattet ein frisch per pip
installiertes. `ruff --version` vor jedem Lauf prüfen, sonst meldet ein
`python -m ruff` einen anderen Befund als die CI.

**Gates, wörtlich aus der CI (Root, Python 3.11/3.12/3.13):**

```bash
PYTHONPATH=src pytest tests/ -m "not live"
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python scripts/check_version_sync.py
python -m parlament_mcp.tool_hashes --check   # security.yml, SEC-022
```

**Gates für `openparldata-mcp/` (aus dem Unterordner):**

```bash
PYTHONPATH=src pytest tests/ -m "not live"
ruff check src/ tests/
ruff format --check src/ tests/
```

**Live-Tests:** `.github/workflows/live-test.yml` läuft per Cron (`0 4 * * *`)
plus `workflow_dispatch`, mit einem Job je Server. DRIFT-005 ist für beide
erfüllt.

**Fixtures: aufgezeichnet.** `tests/fixtures/` hält eine echte Antwort je
Werkzeug (Bundes-Server); Herkunft, Schlüssel, Auswahlregel und SHA-256 stehen
je Datei in `tests/fixtures/PROVENANCE.md` — Portfolio-Konvention, gleich wie in
`swisstopo-mcp` und `swiss-environment-mcp`. Neu aufzeichnen mit
`PYTHONPATH=src python scripts/record_fixtures.py`, geladen wird über
`tests/fixture_data.py`. Fehlerpfade bleiben handgeschrieben.

Eine Aufzeichnung je **Abfrage**, nicht je Endpunkt: alles läuft über denselben
OData-Endpunkt und unterscheidet sich allein im `$filter`. Der Query-String
gehört deshalb in den Schlüssel.

Die IDs der beiden Detail-Abrufe (`parlament_get_business`,
`parlament_get_transcript`) stehen nirgends als Zahl — der Recorder holt sie aus
der jeweiligen Suche, die Tests lesen sie aus dem Schlüssel im Nachweis zurück.
Eine eingetragene ID wäre in ein paar Wochen ein toter Verweis.

Zur Form: OData legt seine Treffer **direkt unter `d`** ab, als Liste. Ein Stub
mit `{"d": {"results": [...]}}` sieht ähnlich aus und ist eine andere Form; der
Server liest `data.get("d", [])` und iterierte darüber die Schlüssel des
Objekts. `openparldata-mcp/` hat noch keine aufgezeichneten Fixtures.

**Datentreue der Quellen.** Beide APIs antworten auf falsch verstandene
Parameter nicht mit einem Fehler, sondern mit plausiblen Daten. Belegt:
`/persons/` verwirft bei `sort_by=lastname` still den `body_key`-Filter, während
`meta.total_records` weiter den korrekt gefilterten Wert meldet — die Antwort
sieht richtig aus und ist es nicht. Andere Sortierschlüssel (`fullname`,
`firstname`) werden kommentarlos ignoriert. Ein neuer Query-Parameter gilt
deshalb erst als verstanden, wenn er gegen die echte Quelle geprüft wurde, mit
einer Gegenprobe ohne ihn. Mocks können diese Klasse Fehler nicht sehen: sie
geben zurück, was man ihnen vorlegt.
