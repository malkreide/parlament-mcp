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

**ruff:** gepinnt ist nur der Root-Job — `ruff==0.16.1` (`.github/workflows/ci.yml`).
Eine `.pre-commit-config.yaml` gibt es nicht, es existiert also kein lokales Gate
zum Abgleichen. Offener Befund: der Job `test-openparldata` installiert kein
gepinntes ruff und läuft gegen `ruff>=0.4.0` aus dem dev-Extra, also gegen die
jeweils neueste Version — dort kann CI ohne Codeänderung rot werden. Lokal
trotzdem mit `0.16.1` arbeiten.

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
PYTHONPATH=src pytest tests/
ruff check src/ tests/
```

Kein `ruff format --check` — Formatierung ist dort ungeprüft.

**Live-Tests:** `.github/workflows/live-test.yml` hat einen Cron-Trigger
(`0 4 * * *`) plus `workflow_dispatch` und fährt `pytest tests/ -m live`.
DRIFT-005 ist für den Bundes-Server damit erfüllt. Nicht für
`openparldata-mcp`: dort gibt es weder `live`-Marker noch geplanten Lauf, die
externe API wird also nie geplant angefragt — offener Befund.
