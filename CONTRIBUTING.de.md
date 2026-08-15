# Mitwirken an parlament-mcp

[🇬🇧 English Version](CONTRIBUTING.md)

Vielen Dank für Ihr Interesse an einem Beitrag! Dieser Server ist Teil des
[Swiss Public Data MCP Portfolio](https://github.com/malkreide).

## Erste Schritte

```bash
git clone https://github.com/malkreide/parlament-mcp
cd parlament-mcp
pip install -e ".[dev]"
```

## Tests ausführen

```bash
# Unit- + gemockte Integrationstests (ohne Netzwerk)
pytest tests/ -m "not live" -v

# Live-API-Tests (Internet erforderlich)
pytest tests/ -m live -v
```

## Code-Stil

```bash
python -m ruff check src/ tests/
python -m ruff format src/ tests/
```

## Ein neues Tool hinzufügen

1. Definieren Sie ein Pydantic-v2-`BaseModel` für die Eingaben in `server.py`
2. Implementieren Sie das Tool mit `@mcp.tool(name=..., annotations={...})`
3. Geben Sie immer `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` an
4. Ergänzen Sie Unit-Tests (gemockt) und einen `@pytest.mark.live`-Integrationstest
5. Dokumentieren Sie das neue Tool in `README.md` **und** `README.de.md`

## Portfolio-Konventionen

- **No-Auth-First**: Phase-1-Tools müssen ohne API-Schlüssel funktionieren
- **Sprachfilter**: Immer `Language eq 'DE'` als Default-OData-Filter setzen
- **Fehlerbehandlung**: Menschenlesbare deutsche Fehlertexte zurückgeben, niemals Exceptions an den Host werfen
- **Pagination**: Alle List-Tools müssen `limit` und `offset` unterstützen
- **Antwortformate**: Sowohl `markdown` (Default) als auch `json` unterstützen

## Probleme melden

Bitte eröffnen Sie ein GitHub-Issue mit:
- Dem verwendeten Tool-Namen und den Parametern
- Der tatsächlichen vs. erwarteten Ausgabe
- Dem relevanten API-Endpoint (falls bekannt)

## Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** täglich um 04:00 UTC, dazu jederzeit von Hand über *Actions → Live API tests → Run
workflow*. Siehe [`.github/workflows/live-test.yml`](.github/workflows/live-test.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Label `upstream` und dem stabilen Titel «Live-Tests gegen ws.parlament.ch (Curia Vista) rot (<Datum>)». Ein zweiter roter Lauf erkennt das offene Issue am Titelanfang und hängt sich an denselben Thread, statt ein zweites aufzumachen. Wird die Suite wieder grün, schliesst sich das Issue selbst.

**Drei Antworten, nicht zwei.** `scripts/classify_live_run.py` liest das JUnit-XML statt des
Exit-Codes und unterscheidet: `clear` (gelaufen, grün), `finding` (gelaufen,
etwas gefallen) und `unknown` (nicht gelaufen — Installation gescheitert, null
Tests eingesammelt, alle übersprungen). Ein `unknown` schliesst nie ein Issue:
Zuzumachen hiesse zu behaupten, der Vergleich sei gelaufen.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über ws.parlament.ch (Curia Vista) widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.
