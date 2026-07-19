[🇬🇧 English Version](README.md)

# 🏛️ parlament-mcp

[![CI](https://github.com/malkreide/parlament-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/parlament-mcp/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/parlament-mcp.svg)](https://badge.fury.io/py/parlament-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Swiss Public Data MCP Portfolio](https://img.shields.io/badge/Portfolio-Swiss%20Public%20Data%20MCP-blue)](https://github.com/malkreide)

> **Teil des [Swiss Public Data MCP Portfolio](https://github.com/malkreide)** –
> KI-Modelle mit Schweizer Öffentlichkeitsdaten verbinden.

> **Hinweis:** Dieser Server deckt die **Bundesebene** ab (Curia Vista). Das
> Repo hostet zusätzlich ein eigenständiges Subprojekt unter
> [`openparldata-mcp/`](openparldata-mcp/README.md) — das **subnationale**
> Pendant für die 26 Kantone und ~70 Gemeindeparlamente
> ([OpenParlData.ch](https://openparldata.ch)). Die beiden sind unabhängige Server.

Ein MCP-Server, der KI-Modelle mit dem **Schweizer Bundesrat und Bundesversammlung** verbindet –
über die [Curia Vista OData-API](https://ws.parlament.ch/odata.svc/) (`ws.parlament.ch`).
Zugriff auf Vorstösse, Abstimmungen, Ratsmitglieder, Sessionen und die
**wörtlichen Debatten-Transkripte** des Amtlichen Bulletins –
**ohne API-Schlüssel** (Phase 1 – No-Auth-First).

---

## 🎯 Anker-Demo-Abfragen

**Metadaten-Ebene:**

> *«Welche Vorstösse zu KI in der Schule sind hängig?»*
> → `parlament_search_business(keyword="KI", keyword2="Schule", status="Eingereicht")`

**Wörtliche Transkripte (Amtliches Bulletin):**

> *«Was hat Nationalrätin Munz in der Frühjahrssession 2024 zur Volksschule
> gesagt? Gib mir den Wortlaut mit korrekter AB-Zitation.»*
> → `parlament_search_transcripts(speaker_name="Munz", session_id=5202, keyword="Volksschule")`
> → danach `parlament_get_transcript(transcript_id=…)` für den vollen Wortlaut.
>
> Liefert kurze, **zitierfähige** Auszüge (`AB 2024 N, 2024-03-13, Munz Martina`)
> mit stabiler Quell-URL; der Volltext wird nur auf Anforderung geladen, nie im
> Stapel.
>
> [→ Weitere Anwendungsbeispiele nach Zielgruppe →](EXAMPLES.md)

Ideal für die **KI-Fachgruppe Stadtverwaltung Zürich**: Offene Vorstösse zu KI in der Bildung
finden – oder wörtlich belegen, was im Rat tatsächlich gesagt wurde.

<p align="center">
  <img src="assets/demo.svg" alt="Demo: Claude fragt hängige KI-Vorstösse via MCP Tool Call ab" width="720">
</p>

---

## 🔧 Tools

| Tool | Beschreibung |
|---|---|
| `parlament_search_business` | Vorstösse nach Stichwort, Typ, Status, Rat, Datum suchen |
| `parlament_get_business` | Vollständige Details eines Vorstosses (Texte, BR-Antwort) |
| `parlament_search_members` | Ratsmitglieder nach Kanton (z.B. ZH), Partei, Rat finden |
| `parlament_get_votes` | Parlamentarische Abstimmungen mit Ja/Nein-Bedeutung |
| `parlament_get_sessions` | Aktuelle Sessionen mit IDs für Folgeabfragen |
| `parlament_search_transcripts` | Debatten durchsuchen → **zitierfähige Auszüge** mit AB-Zitation + Quell-URL (Redner-/Session-/Geschäfts-/Datumsfilter) |
| `parlament_get_transcript` | **Wörtlichen Volltext** eines einzelnen Votums nach ID abrufen (gedeckelt, paginiert, `is_excerpt`-Kennzeichnung) |

---

## 🏗️ Architektur

```
┌──────────────────────────────────┐
│     MCP-Host (Claude Desktop /    │
│     Claude API / IDE)             │
└─────────────┬─────────────────────┘
              │ MCP-Protokoll (JSON-RPC 2.0)
              │ Transport: stdio (lokal) / SSE (Cloud)
┌─────────────▼─────────────────────┐
│          parlament-mcp            │
│   FastMCP · Python · Pydantic v2  │
│                                   │
│  ┌── Metadaten-Schicht (server.py)┐
│  │  search_business · get_business │
│  │  search_members · get_votes     │
│  │  get_sessions                   │
│  └─────────────────────────────────┘
│  ┌── Transkript-Schicht ──────────┐  ← eigenes Modul (transcripts.py)
│  │  search_transcripts (Auszüge)  │    · Language='DE' dedupliziert Editionen
│  │  get_transcript (Wortlaut)     │    · Type=1 = nur echte Wortmeldungen
│  └─────────────────────────────────┘    · Retry + 45s-Read-Timeout
└─────────────┬─────────────────────┘
              │ HTTPS / OData v3
┌─────────────▼─────────────────────┐
│  ws.parlament.ch / odata.svc      │
│  Curia Vista – Kein Auth nötig    │
│                                   │
│  Business · Vote · MemberCouncil  │   Metadaten-Pfad
│  Session ─< Meeting ─< Subject ─< Transcript   Transkript-Pfad
└───────────────────────────────────┘
```

---

## 🚀 Installation

### Claude Desktop (stdio)

Ergänze `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "parlament": {
      "command": "uvx",
      "args": ["parlament-mcp"]
    }
  }
}
```

Claude Desktop neu starten – fertig.

### Lokale Entwicklung

```bash
git clone https://github.com/malkreide/parlament-mcp
cd parlament-mcp
pip install -e .
python -m parlament_mcp.server
```

### Cloud / Railway (SSE)

```bash
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 PORT=8080 python -m parlament_mcp.server
# SSE-Endpunkt: http://dein-host:8080/sse
```

### Netzwerk-Bindung

Standardmässig bindet der Server an `127.0.0.1` (nur localhost). Setze
`MCP_HOST=0.0.0.0` **nur** im Container-/Cloud-Kontext (Docker, Railway,
Render, Kubernetes). Niemals lokal auf `0.0.0.0` binden – das exponiert den
Server im lokalen Netzwerk (NeighborJack-Risiko); ausserhalb eines erkannten
Containers gibt der Server eine Warnung aus.

Der Transport wird über `MCP_TRANSPORT` gewählt (`stdio` als Default, oder
`sse` / `streamable-http`); `--http` bleibt als Alias für `streamable-http`.

### Authentifizierung (optional)

Der HTTP-Transport ist standardmässig offen (öffentliche read-only Daten). Für
einen Bearer-Token-Zwang über die CORS/Auth-App-Factory `MCP_BEARER_TOKENS`
setzen:

```bash
MCP_BEARER_TOKENS="alice:tok_abc,bob:tok_def" MCP_ALLOWED_ORIGINS="https://claude.ai" \
  uvicorn parlament_mcp.server:create_http_app --factory --host 0.0.0.0 --port 8080
```

Jeder Request braucht dann `Authorization: Bearer <token>`; die Identität kommt
aus dem validierten Token, nicht aus einem Session-Header (siehe
[`docs/security.md`](docs/security.md)).

### Docker

```bash
docker compose up --build          # bindet nur 127.0.0.1:8080
# oder das gehärtete Image direkt bauen (non-root, read-only FS):
docker build -t parlament-mcp .
```

Kubernetes-Manifeste (gehärteter `securityContext`, Resource-Limits, Egress-
`NetworkPolicy`, `Mcp-Session-Id`-Sticky-Routing) liegen unter
[`deploy/k8s/`](deploy/k8s/); ein HAProxy-Stick-Table-Beispiel in
[`deploy/haproxy.cfg`](deploy/haproxy.cfg).

---

## 💡 Beispielabfragen

**KI und Schule – offene Vorstösse:**
```
parlament_search_business(keyword="Künstliche Intelligenz", keyword2="Bildung", status="Eingereicht")
```

**Alle Zürcher Ratsmitglieder:**
```
parlament_search_members(canton="ZH", active_only=True)
```

**Wie hat der Rat über Bildungsdigitalisierung abgestimmt?**
```
parlament_get_votes(keyword="Digitalisierung")
```

**Was hat Nationalrätin Munz in der Frühjahrssession 2024 zur Volksschule gesagt?**
```
parlament_search_transcripts(speaker_name="Munz", session_id=5202, keyword="Volksschule")
# danach für den vollen Wortlaut:
parlament_get_transcript(transcript_id=336348)
```

---

## 🔗 Synergien im Portfolio

| Partner-Server | Kombination |
|---|---|
| [`openparldata-mcp`](openparldata-mcp/README.de.md) | **Bund ↔ subnational** — dieselbe Frage über Kantone & Gemeinden |
| [`fedlex-mcp`](https://github.com/malkreide/fedlex-mcp) | Gesetzestext ↔ parlamentarische Debatte, die ihn geschaffen hat |
| [`zurich-opendata-mcp`](https://github.com/malkreide/zurich-opendata-mcp) | Städtische Daten ↔ kantonale/nationale Vorstösse |
| [`swiss-statistics-mcp`](https://github.com/malkreide/swiss-statistics-mcp) | Statistiken ↔ Vorstösse, die sich darauf beziehen |

**Power-Query-Beispiel:**
```
«Zeig mir alle Zürcher Vorstösse zu KI in der Bildung
 und verlinke die relevanten Bundesgesetze aus fedlex-mcp.»
```

---

## 📊 Datenquelle

- **API:** [ws.parlament.ch/odata.svc](https://ws.parlament.ch/odata.svc/)
- **Authentifizierung:** Keine (Phase 1 – No-Auth-First)
- **Protokoll:** OData v3 / JSON
- **Abdeckung:** Alle Parlamentsgeschäfte seit 1978; Abstimmungen seit ~2000.
  **Strukturierte wörtliche Transkripte (Amtliches Bulletin) ab 1999-12-06**
  (frühere Jahrgänge 1891–1999 nur als Archiv-Scans — siehe Bekannte
  Einschränkungen).
- **Aktualisierung:** Echtzeit (offizieller Datendienst des Bundes)

### Urheberrecht — wörtliche Zitation ist erlaubt

Amtliche Verhandlungen von Schweizer Behörden sind nach **Art. 5 Abs. 1 lit. a
URG** vom Urheberrechtsschutz **ausgenommen**. Der wörtliche Wortlaut der
Rats­debatten im Amtlichen Bulletin darf deshalb frei wiedergegeben und zitiert
werden — genau das liefern die Transkript-Tools: den Wortlaut selbst, nie eine
Zusammenfassung als Ersatz dafür.

---

## 📜 Datenquellen & Lizenzen

| Quelle | Lizenz | Attribution |
|---|---|---|
| Curia Vista (ws.parlament.ch) | CC BY 4.0 | © Schweizer Parlament, CC BY 4.0 |

Jede Tool-Antwort ist ein typisiertes strukturiertes Objekt (FastMCP exponiert
das Output-Schema) mit `source`, `license`, `provenance`, `match_type` und
`count` plus typisierten `results`. Die Daten werden unverändert weitergegeben.

## 🧭 Phase

Dieser Server ist in **Phase 1 — Read-only Wrapper** (alle Tools
`readOnlyHint: true`, kein Write). Das Phasenmodell steht in
[`docs/roadmap.md`](docs/roadmap.md).

## 🔖 MCP-Protokoll-Version

Getestet/gepinnt gegen MCP-Spec **`2025-06-18`** (`PROTOCOL_VERSION` in
`src/parlament_mcp/config.py`). SDK-Updates kommen monatlich via Dependabot;
Spec-Bumps werden im [`CHANGELOG.md`](CHANGELOG.md) festgehalten.

## 🧱 MCP-Primitive

Phase 1 nutzt **nur Tools** — Begründung und Phase-2-Resources-Plan in
[`docs/adr/ADR-003-mcp-primitives.md`](docs/adr/ADR-003-mcp-primitives.md).

## 🏷️ Tool-Annotations

Alle Tools deklarieren explizite, verhaltenskonsistente Annotations:

| Tool | readOnly | destructive | idempotent | openWorld |
|---|:--:|:--:|:--:|:--:|
| `parlament_search_business`  | ✅ | — | ✅ | ✅ |
| `parlament_get_business`     | ✅ | — | ✅ | ✅ |
| `parlament_search_members`   | ✅ | — | ✅ | ✅ |
| `parlament_get_votes`        | ✅ | — | ✅ | ✅ |
| `parlament_get_sessions`       | ✅ | — | ✅ | ✅ |
| `parlament_search_transcripts` | ✅ | — | ✅ | ✅ |
| `parlament_get_transcript`     | ✅ | — | ✅ | ✅ |

## 📈 Observability

Strukturierte JSON-Logs gehen auf **stderr** (stdout bleibt dem stdio-Protokoll
vorbehalten). OpenTelemetry-Tracing umschliesst jeden Tool-Call und
instrumentiert ausgehendes HTTP automatisch; mit gesetztem
`OTEL_EXPORTER_OTLP_ENDPOINT` (Extra `otel-export`) werden Spans exportiert.
Vollständige Security-Posture (Lethal-Trifecta-Bewertung, Egress-Allow-List,
Gateway-Härtung) in [`docs/security.md`](docs/security.md).

---

## 🛡️ Safety & Limits

| Aspekt | Details |
|--------|---------|
| **Zugriff** | Nur lesend (`readOnlyHint: true`) — der Server kann keine Daten ändern oder löschen |
| **Personendaten** | Parlamentsgeschäfte sind öffentliche Amtshandlungen (BGÖ). Es werden keine privaten Daten abgerufen oder gespeichert. |
| **Rate Limits** | Eingebaute Obergrenzen pro Abfrage: max. 100 Treffer (Geschäfte/Mitglieder), 50 (Abstimmungen), 30 (Transkript-Suche), 10 (Sessionen). Transkript-Volltext ist pro Aufruf gedeckelt und paginiert — eine ganze Session wird nie versehentlich geladen. |
| **Timeout** | 20 Sekunden pro Metadaten-Aufruf; 45 Sekunden für Transkript-Reads (Volltextsuche ist schwerer) |
| **Authentifizierung** | Keine API-Keys nötig — Curia Vista ist öffentlich zugänglich |
| **Datenquelle** | Offizieller Datendienst des Bundes (Schweizerische Parlamentsdienste) |
| **Nutzungsbedingungen** | Es gelten die ToS von [ws.parlament.ch](https://ws.parlament.ch/) — Schweizerische Parlamentsdienste |

---

## Bekannte Einschränkungen

**Allgemein**
- OData `substringof()`-Filter unterscheidet bei manchen Feldern Gross-/Kleinschreibung.
- Session-Namen können für sehr aktuelle Sessionen `null` sein – stattdessen Session-ID nutzen.

**Transkripte (Amtliches Bulletin)** — live verifiziert am 2026-07-19:
- **Zeitliche Abdeckung: erst ab 1999-12-06.** Die strukturierte `Transcript`-Entität
  reicht bis Dezember 1999 zurück. Debatten von **1891–1999 existieren nur als
  gescannte Archivdokumente** (Bundesarchiv / Amtsdruckschriften) und sind hier
  **nicht angebunden** (kein OCR im Scope). Eine Abfrage, deren gesamtes
  Datumsfenster vor der Abdeckung liegt, liefert einen erklärenden Fehler statt
  eines leeren Resultats.
- **Keine Seitenzahl in der Quelle.** Die API führt kein Seiten-/Spaltenfeld, darum
  ist die klassische Form `AB <Jahr> N <Seite>` nicht konstruierbar. Wir bilden
  eine stabile, überprüfbare Ersatzreferenz — `AB <Jahr> <N|S>, <Datum>, <Sprecher>`
  — plus die massgebliche `source_url` (`SubjectId`) und die `transcript_id`. Ein
  ehrlich dokumentierter Kompromiss, keine Auslassung.
- **Sprachverhalten (wichtig).** `Language` bezeichnet die *Edition*, nicht die
  Redesprache. Die Tools filtern `Language eq 'DE'` **einzig zur Deduplizierung**
  der drei byte-identischen Editionen (DE/FR/IT) auf eine Kopie. Jede Wortmeldung
  erscheint im **Original-Wortlaut**; ein französisches oder italienisches Votum
  wird **nicht** ausgeblendet — seine tatsächliche Sprache steht im Feld `language`
  (`de`/`fr`/`it`). Die Antwort weist dies über `language_note` aus.
- **Kürzung ist explizit, nie still.** Die Suche liefert kurze Auszüge (`snippet`,
  ~320 Zeichen) mit `is_excerpt`, `total_length_chars` und einem Hinweis zum
  Volltext-Bezug. `parlament_get_transcript` deckelt bei `max_chars`; bei Kürzung
  wird `is_excerpt=True` gesetzt und ein `next_offset` zum Weiterblättern geliefert.
- **Nur Wortlaut, nie zusammengefasst.** Der Wortlaut *ist* das Produkt; die Tools
  ersetzen ihn nie durch eine Zusammenfassung.
- **Latenz:** Ein freies `keyword` kombiniert mit `speaker_name` ist der langsamste
  Pfad (~40 s). Mit `session_id`, `business_number` oder einem Datumsfenster
  kombiniert bleiben Reads bei ~1–2 s.

---

## 🧪 Tests

```bash
pip install -e ".[dev]"

# Unit- + gemockte Integrationstests (kein Netz), wie in der CI:
PYTHONPATH=src pytest tests/ -m "not live"

# Inklusive Live-Tests gegen die echte ws.parlament.ch-API:
PYTHONPATH=src pytest tests/ -m live
```

HTTP wird mit `respx` gemockt; netzabhängige Tests sind mit `@pytest.mark.live`
markiert und via `-m "not live"` aus der CI ausgeschlossen. Tool-Definitionen sind
in `tool-hashes.json` gepinnt (`python -m parlament_mcp.tool_hashes --check`).

---

## Mitwirken

Siehe [CONTRIBUTING.de.md](CONTRIBUTING.de.md).

---

## Sicherheit

Siehe [SECURITY.de.md](SECURITY.de.md) für die Sicherheitsrichtlinie und
Sicherheitslage (Schwachstellenmeldung, Lethal-Trifecta-Bewertung, akzeptierte
Risiken).

---

## Lizenz

MIT © [Hayal Oezkan](https://github.com/malkreide) — siehe [LICENSE](LICENSE)
