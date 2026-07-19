[🇬🇧 English Version](README.md)

# openparldata-mcp

MCP-Server für die **subnationale** Ebene der Schweiz — 26 Kantone und ~70
Gemeindeparlamente — über die [OpenParlData.ch](https://openparldata.ch)-API.
Vorstösse, Dokumente inkl. extrahiertem **PDF-Volltext**, Personen,
Interessenbindungen, Abstimmungen und Sitzungen, exponiert als 13 read-only
Tools mit dem Prefix `oparl_`.

> Teil des **Swiss Public Data MCP** Portfolios. Dieser Server ist das
> subnationale Pendant zu `parlament-mcp` (Bundesebene, Curia Vista).

## Abgrenzung (nicht verhandelbar)

Dieser Server deckt **ausschliesslich** die subnationale Ebene ab:

- ✅ **26 Kantone** (`body_type="canton"`)
- ✅ **~70 Gemeindeparlamente** (`body_type="municipality"`)
- ⛔ **Bundesebene** (`body_key="CHE"`) wird von jedem Tool **aktiv abgewiesen**.
  Für den Bund ist **`parlament-mcp`** (Curia Vista) die Quelle. Für
  Interessenbindungen auf Bundesebene verweist `oparl_search_interests`
  zusätzlich auf **`lobbywatch-mcp`** (redaktionell geprüft, mit
  Branchen-Taxonomie).

## Anker-Demo-Abfrage

> **«Welche Vorstösse zu Tagesschulen wurden im Gemeinderat Zürich seit 2024
> eingereicht, wie hat der Rat entschieden — und in welchen anderen Schweizer
> Städten ist das Thema ebenfalls politisch aktiv?»**

Ablauf:

1. `oparl_list_bodies(search="Zürich")` → Keys auflösen: `261` = Stadt Zürich,
   `ZH` = Kanton Zürich, `230` = Winterthur (`CHE` = Bund, **gesperrt**).
2. `oparl_search_affairs(body_key="261", search="Tagesschule", date_from="2024-01-01")`
3. `oparl_get_affair_documents(affair_id=…, include_text=true)` — der extrahierte
   PDF-Volltext.
4. `oparl_compare_bodies(search="Tagesschule", body_type="municipality")` — wo
   sonst steht das Thema auf der Traktandenliste?

## Tools (13)

| Tool | Zweck |
|---|---|
| `oparl_list_bodies` | Kantone/Gemeinden auflisten, `body_key` ermitteln |
| `oparl_search_affairs` | Geschäfte einer Körperschaft durchsuchen (Metadaten / Dokumente / Volltext) |
| `oparl_get_affair` | Vollständiges Geschäft-Detail (mit `expand`) |
| `oparl_get_affair_documents` | Dokumente + extrahierter **PDF-Volltext** |
| `oparl_compare_bodies` | Themenpräsenz über Körperschaften hinweg, sortiert |
| `oparl_search_persons` | Mandatsträger·innen einer Körperschaft |
| `oparl_get_person` | Personenprofil (mit `expand`) |
| `oparl_get_person_interests` | Interessenbindungen einer Person |
| `oparl_search_interests` | Interessenbindungen einer Körperschaft (Organisation → Personen) |
| `oparl_get_votings` | Abstimmungen zu einem Geschäft oder einer Körperschaft |
| `oparl_get_voting_results` | Einzelstimmen **einer** Abstimmung (`voting_id` Pflicht) |
| `oparl_search_meetings` | Sitzungen einer Körperschaft im Zeitraum |
| `oparl_source_status` | API-Erreichbarkeit, letzter Abruf, Alter des Body-Cache |

Alle Tools sind `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`.

## Architektur-Entscheid

**ARCH A — Live-API-only.** Jeder Endpoint antwortet stabil in 0,15–2,4 s
(Live-Probe **2026-07-18**). Der Server fragt bei jedem Aufruf die Live-API ab;
es gibt keinen lokalen Dump.

Der Bulk-Export (`https://files.openparldata.ch/exports/*.ndjson.gz`) ist bewusst
auf **Phase 2** verschoben. Er ist nur *jenseits* der harten
`offset > 100000`-Grenze der API nötig — was praktisch allein die `votes`-Tabelle
betrifft (**47'732'862** Einzelstimmen). Für alles, was dieser Server exponiert,
liegt die Live-API deutlich innerhalb dieser Grenze; ein Dump brächte
Sync-/Aktualitätskosten ohne heutigen funktionalen Gewinn.

### Verifizierte Probe-Befunde im Code (2026-07-18)

1. **Silent Empty.** Ein ungültiger `body_key` liefert HTTP 200 mit leerem Array
   statt eines Fehlers — *«Die API sagt nie Nein, sie sagt Nichts.»* Ein lazy
   geladener Body-Cache (`/v1/bodies/?indexed=true`, 97 Einträge, 24 h TTL)
   validiert jeden `body_key` **vor** dem Request und wirft bei Unbekanntem einen
   sprechenden Fehler mit Fuzzy-Vorschlägen.
2. **Sprachfelder.** Mehrsprachige Felder kommen als `{"de": …, "fr": …}`. Mit
   `lang_format=flat` + `fields=…` kommen sie **leer** zurück; deshalb nutzen wir
   nie `lang_format=flat`, sondern normalisieren zentral mit `localize()`.
3. **Volltext.** `/v1/affairs/{id}/docs` liefert im Feld `text` den extrahierten
   PDF-Volltext — das wertvollste Feld dieses Servers. Er wird nie stillschweigend
   gekürzt; bei Überlänge explizit trunkiert mit `text_truncated=true` und
   `text_total_chars`.
4. **Scale-Guardrail.** `oparl_get_voting_results` verlangt `voting_id` und deckelt
   `limit` auf 500 (API-Maximum wäre 1000), da die `votes`-Tabelle 47,7 Mio. Zeilen
   enthält.
5. **Datenqualität Interests.** Rohdaten mit Parsing-Artefakten (ein realer
   ZH-Datensatz hat `name: {"de": "2007"}` — eine Jahreszahl im Organisationsfeld;
   `type`, `role_name`, `group` oft leer). Jede Interests-Antwort trägt
   `data_quality: "unverified_source_data"`.
6. **Fehlerverhalten.** 404 → `{"detail": …}`; `offset > 100000` → RFC-7807-Body
   mit `max_offset`. Beide werden in verständliche Tool-Fehler übersetzt.

## Installation & Betrieb

```bash
# aus dem Unterordner dieses Repos (uvx-ready)
uvx --from "git+https://github.com/malkreide/parlament-mcp#subdirectory=openparldata-mcp" openparldata-mcp

# oder lokal
pip install -e ".[dev]"
openparldata-mcp            # stdio (Default)
```

### Transport

Default ist **stdio**. Für HTTP `MCP_TRANSPORT` setzen:

```bash
MCP_TRANSPORT=streamable-http MCP_HOST=127.0.0.1 MCP_PORT=8080 openparldata-mcp
```

`MCP_HOST` ist standardmässig `127.0.0.1`; Bindung an `0.0.0.0` ausserhalb eines
erkannten Containers loggt eine NeighborJack-Warnung.

## Datenquelle & Lizenz

- Daten: [OpenParlData.ch](https://api.openparldata.ch/v1) — **CC BY 4.0**,
  Attribution **«Source: OpenParlData.ch»** (in jedem Tool-Envelope ausgegeben).
- Keine Authentifizierung erforderlich.
- Code: **MIT**.

## Roadmap

- **Speeches-Tool.** Nur wenige Körperschaften haben Voten — CHE (332'859, hier
  ausserhalb des Scopes) und BS (98'796) sowie einige weitere; die Stadt Zürich
  hat 0. Kein Phase-1-Tool; hier als Roadmap-Eintrag festgehalten.
- **Phase 2 — Bulk-Export.** NDJSON-Dump-Ingestion, um die `votes`-Tabelle
  (47,7 Mio. Zeilen) jenseits der `offset > 100000`-Grenze zu bedienen.
