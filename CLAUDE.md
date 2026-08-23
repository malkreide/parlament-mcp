# CLAUDE.md

## Teil 1 — Konventionen (portfolio-weit)

### Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

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

### Wenn Codex gar nicht erst hinsieht

Die Zeile oben unterstellt, dass es einen Befund geben *kann*. Das ist nicht
immer so, und man sieht es dem PR nicht an.

Am 21.8.2026 war das Code-Review-Kontingent zwischen 08:41 und 09:48
aufgebraucht — davor echte Reviews, danach in 30 Repos nur noch:

```
You have reached your Codex usage limits for code reviews.
```

Bis mindestens zum 22.8. um 08:30, also 23 Stunden später, blieb es dabei. In
der Zwischenzeit sind 32 PRs mit formal erfülltem Häkchen gemergt worden, ohne
dass jemand hineingesehen hat.

Vier Gründe, warum Codex schweigt, und nur einer davon ist harmlos:

- **Kein Befund** — dann reagiert er mit 👍 und schreibt nichts.
- **Der PR ist ein Draft** — darauf läuft Codex nicht an.
- **Das Kontingent ist weg** — dann schreibt er die Meldung oben.
- **Für das Repo ist keine Codex-Umgebung eingerichtet** — dann schreibt er
  stattdessen «To use Codex here, create an environment for this repo», und
  daran ändert kein Wartefenster etwas.

«Kein Kommentar» heisst also nicht «geprüft und sauber». Unterscheiden lässt es
sich an der Form: Ein echter Review ist ein Review-Objekt («💡 Codex Review»,
mit Commit-Angabe), die Limit-Meldung ein gewöhnlicher Issue-Kommentar. Das
sind zwei verschiedene Abfragen — `get_reviews` gegen `get_comments`; wer nur
eine davon nimmt, übersieht die andere Hälfte. Genau so ist die Limit-Meldung
zuerst durchgerutscht.

Portfolio-weit nachsehen:

```
search_pull_requests: user:malkreide commenter:chatgpt-codex-connector[bot] updated:>=<Datum>
```

Findet nur, wo er *kommentiert* hat. Repos ohne PR-Aktivität tauchen nicht auf
— das ist kein Beleg, dass dort geprüft wurde.

Eine Absage taugt umgekehrt nicht als Beleg fürs Gegenteil, denn die vier
Fälle kommen in einer Reihenfolge: Ist das Kontingent leer, meldet Codex das
— ob überhaupt eine Umgebung besteht, prüft er dann womöglich gar nicht. In
`swiss-public-data-mcp` kam am 22.8. die Limit-Meldung und am 23.8., nach
Rückkehr des Kontingents, die Umgebungs-Meldung; erst als der erste Engpass
weg war, wurde der zweite sichtbar. Eine Limit-Meldung belegt also, dass die
App reagiert, nicht dass sie hier arbeiten könnte.

Belastbar ist nur ein Review-Objekt, und dafür gibt es eine eigene Abfrage:

```
search_pull_requests: user:malkreide type:pr reviewed-by:chatgpt-codex-connector[bot]
```

Am 23.8.2026 über die 41 Server-Repos: 25 mit mindestens einem echten Review,
16 nur mit Absagen. «Belegt» heisst dabei «damals», nicht «heute» — ein Review
vom 16.8. sagt über den aktuellen Stand nichts.

Zweiter Weg, den Prüfer zu verlieren, ganz ohne Kontingentproblem: zu schnell
mergen. Am 21./22.8. lagen zwischen «ready for review» und Merge mehrfach drei
bis fünf Sekunden. Codex wird beim Umschalten von Draft auf ready ausgelöst und
braucht danach Zeit; wer sofort mergt, hat das Häkchen gesetzt und den Review
nicht abgewartet.

Das Kontingent hängt am Konto, nicht am Repo, und Code-Reviews haben einen
eigenen Topf — nur GitHub-getriggerte Reviews zählen hinein. ChatGPT-Pläne
fahren ein rollendes Fünf-Stunden-Fenster plus Wochenlimits; welches greift,
steht im Codex-Dashboard. Zeigt das freies Kontingent, während Reviews weiter
scheitern, ist das ein bekannter Fehler bei mehreren verbundenen Konten — dann
den GitHub-Connector in den Codex-Einstellungen trennen und neu verbinden.

### Wenn zwei Agenten dasselbe tun

Vor dem Anlegen eines Branches mit vorgegebenem Namen prüfen, ob es ihn schon
gibt:

```bash
git ls-remote --heads origin claude/<name> | wc -l
```

Steht dort `1`, arbeitet jemand anderes daran — mit Schreibrecht auf denselben
Ref.

Ein PR mit leerem Diff wird geschlossen, nicht gemergt. Der Test ist
`get_files` auf dem PR: kommt `[]` zurück, ändert er nichts. Ein grüner Check
sagt dazu nichts — die CI prüft den Head, nicht die Differenz zur Basis.

Am 21.8.2026 liefen zwei Sessions dieselbe Aufgabe über 45 Repos, auf den
Branches `claude/codex-review-audit-templates-9sn6mx` und
`claude/codex-review-audit-7ioh56`. Wo die eine zuerst nach `main` kam, wurde
`main` in den Branch der anderen gemergt und der add/add-Konflikt zugunsten
von `main` aufgelöst. Übrig blieben 14 PRs, die durch sämtliche Gates grün
liefen und nichts enthielten; sie wurden gemergt und hinterliessen leere
Merge-Commits. Mit den zwei Folge-PRs, die aus demselben Grund gegenstandslos
waren, waren 16 der 59 PRs jenes Tages reine Reibung.

Dieselbe Klasse wie der handgeschriebene Stub, der denselben Feldnamen annahm
wie der Code: Nichts ist rot, weil nichts geprüft wird, worauf es ankommt.

## Teil 2 — dieses Repo

Zwei Projekte, zwei Gate-Sätze: Bundes-Server (Root, `src/parlament_mcp`) und
`openparldata-mcp/` (eigene `pyproject.toml`, eigener CI-Job).

**ruff:** `ruff==0.16.3`, exakt gepinnt im `[dev]`-Extra — je einmal in
`pyproject.toml` und in `openparldata-mcp/pyproject.toml`, für jedes Projekt
sein eigenes Gate. Ein Install des Extras reicht also, von Hand nachsetzen ist
nicht mehr nötig. Keine zweite Version in die Workflows schreiben: ein solcher
Schritt läuft nach dem Install und überstimmt den Pin still — er stand in beiden
CI-Jobs (`test_werkzeug_versionen.py` hält beides fest). Eine
`.pre-commit-config.yaml` gibt es nicht. Achtung bleibt: ein per `uv tool`
installiertes ruff unter `~/.local/bin` beschattet ein frisch per pip
installiertes. `ruff --version` vor jedem Lauf prüfen, sonst meldet ein
`python -m ruff` einen anderen Befund als die CI.

Vor dem Lauf `ruff --version` prüfen: ein älteres ruff früher im `PATH`
schlägt den Pin, ohne dass der Install etwas meldet.

**Gates, wörtlich aus der CI (Root, Python 3.11/3.12/3.13):**

```bash
PYTHONPATH=src pytest tests/ -m "not live"
python scripts/check_ruff_pin.py
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python scripts/check_version_sync.py
python -m parlament_mcp.tool_hashes --check   # security.yml, SEC-022
```

**Gates für `openparldata-mcp/` (aus dem Unterordner):**

```bash
PYTHONPATH=src pytest tests/ -m "not live"
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
```

**Die zwei Gate-Sätze sind nicht gleich stark.** Der Root-Server hat ein
Versions-Sync, `openparldata-mcp/` nicht: dessen `scripts/` enthält nur
`record_fixtures.py`, es gibt dort kein `server.json` und keinen zweiten
Guard. Die `0.1.0` in `openparldata-mcp/pyproject.toml` steht allein und wird
von nichts gehalten — beim Anheben also von Hand.

`security.yml` hat **zwei** Jobs, nicht nur den Hash-Check aus der Liste
oben: davor läuft `secret-scan` (gitleaks). Beide auf `push`/`pull_request`
gegen `main`. Lokal stellt keiner der Befehle den gitleaks-Job nach.

Beide Matrizen (`test`, `test-openparldata`) fahren 3.11/3.12/3.13 ohne
`if:`-Ausnahme, aber ohne `fail-fast: false` — eine rote 3.11 bricht die
übrigen ab, bevor sie etwas sagen.

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
Objekts.

`openparldata-mcp/` hat einen eigenen Ordner mit 82 Aufzeichnungen und
denselben Aufbau (`scripts/record_fixtures.py`, `tests/fixture_data.py`,
`tests/fixtures/PROVENANCE.md`). 69 davon gehören zu `oparl_compare_bodies`:
das Werkzeug zählt Treffer je Gemeinde und fragt dafür jede einzeln, mit
`asyncio.gather`. Zugeordnet wird deshalb nach der Anfrage und nie nach der
Reihenfolge. Zwei Fallen dort: der Body-Cache hält 24 h, also muss der Recorder
ihn vor jedem Aufruf leeren — sonst schickt `oparl_list_bodies` beim zweiten Mal
keine Anfrage mehr und fehlt im Ordner. Und `meta.total_records` bleibt beim
Kürzen unangetastet: gerade dieses Feld macht einen stillschweigend verworfenen
Filter sichtbar.

**Datentreue der Quellen.** Beide APIs antworten auf falsch verstandene
Parameter nicht mit einem Fehler, sondern mit plausiblen Daten. Belegt:
`/persons/` verwirft bei `sort_by=lastname` still den `body_key`-Filter, während
`meta.total_records` weiter den korrekt gefilterten Wert meldet — die Antwort
sieht richtig aus und ist es nicht. Andere Sortierschlüssel (`fullname`,
`firstname`) werden kommentarlos ignoriert. Ein neuer Query-Parameter gilt
deshalb erst als verstanden, wenn er gegen die echte Quelle geprüft wurde, mit
einer Gegenprobe ohne ihn. Mocks können diese Klasse Fehler nicht sehen: sie
geben zurück, was man ihnen vorlegt.
