[🇩🇪 Deutsche Version](README.de.md)

# 🏛️ parlament-mcp

[![CI](https://github.com/malkreide/parlament-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/parlament-mcp/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/parlament-mcp.svg)](https://badge.fury.io/py/parlament-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Swiss Public Data MCP Portfolio](https://img.shields.io/badge/Portfolio-Swiss%20Public%20Data%20MCP-blue)](https://github.com/malkreide)

> **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)** –
> connecting AI models to Swiss public data sources.

> **Note:** This server covers the **federal** level (Curia Vista). This repo
> additionally hosts a self-contained subproject under
> [`openparldata-mcp/`](openparldata-mcp/README.md) — the **subnational**
> counterpart for the 26 cantons and ~70 municipal parliaments
> ([OpenParlData.ch](https://openparldata.ch)). The two are independent servers.

An MCP server that connects AI models to the **Swiss Federal Parliament** via the
[Curia Vista OData API](https://ws.parlament.ch/odata.svc/) (`ws.parlament.ch`).
Access motions, interpellations, votes, members, sessions, and the **verbatim
debate transcripts** of the Amtliches Bulletin – with **no API key required**
(Phase 1 – No-Auth-First).

---

## 🎯 Anchor Demo Queries

**Metadata layer:**

> *"Welche Vorstösse zu KI in der Schule sind hängig?"*
> → `parlament_search_business(keyword="KI", keyword2="Schule", status="Eingereicht")`

**Verbatim transcripts (Amtliches Bulletin):**

> *"What did National Councillor Munz say in the 2024 spring session about the
> Volksschule? Give me the exact wording with a correct AB citation."*
> → `parlament_search_transcripts(speaker_name="Munz", session_id=5202, keyword="Volksschule")`
> → then `parlament_get_transcript(transcript_id=…)` for the full wording.
>
> Returns short, **citable** excerpts (`AB 2024 N, 2024-03-13, Munz Martina`) with
> a stable source URL; the verbatim text is fetched on demand, never in bulk.
>
> [→ More use cases by audience →](EXAMPLES.md)

Perfect for the **KI-Fachgruppe Stadtverwaltung Zürich**: find pending motions
on AI in education, or quote what was actually said in the chamber – instantly.

<p align="center">
  <img src="assets/demo.svg" alt="Demo: Claude queries pending AI motions via MCP tool call" width="720">
</p>

---

## 🔧 Tools

| Tool | Description |
|---|---|
| `parlament_search_business` | Search Vorstösse by keyword, type, status, council, date |
| `parlament_get_business` | Full details of a single business (texts, FC response) |
| `parlament_search_members` | Find councillors by canton (e.g. ZH), party, council |
| `parlament_get_votes` | Parliamentary votes with Ja/Nein meaning |
| `parlament_get_sessions` | List recent sessions with IDs for follow-up queries |
| `parlament_search_transcripts` | Search debate transcripts → **citable excerpts** with AB citation + source URL (speaker / session / business / date filters) |
| `parlament_get_transcript` | Fetch the **verbatim full text** of a single speech by ID (capped, paginated, `is_excerpt` flagged) |

---

## 🏗️ Architecture

```
┌──────────────────────────────────┐
│     MCP Host (Claude Desktop /    │
│     Claude API / IDE)             │
└─────────────┬─────────────────────┘
              │ MCP Protocol (JSON-RPC 2.0)
              │ Transport: stdio (local) / SSE (cloud)
┌─────────────▼─────────────────────┐
│          parlament-mcp            │
│   FastMCP · Python · Pydantic v2  │
│                                   │
│  ┌── metadata layer (server.py) ──┐
│  │  search_business · get_business │
│  │  search_members · get_votes     │
│  │  get_sessions                   │
│  └─────────────────────────────────┘
│  ┌── transcript layer ────────────┐  ← separate module (transcripts.py)
│  │  search_transcripts (excerpts) │    · Language='DE' dedups editions
│  │  get_transcript (verbatim)     │    · Type=1 = real speeches only
│  └─────────────────────────────────┘    · retry + 45s read timeout
└─────────────┬─────────────────────┘
              │ HTTPS / OData v3
┌─────────────▼─────────────────────┐
│  ws.parlament.ch / odata.svc      │
│  Curia Vista – No Auth Required   │
│                                   │
│  Business · Vote · MemberCouncil  │   metadata path
│  Session ─< Meeting ─< Subject ─< Transcript   transcript path
└───────────────────────────────────┘
```

---

## 🚀 Installation

### Claude Desktop (stdio)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### Local development

```bash
git clone https://github.com/malkreide/parlament-mcp
cd parlament-mcp
pip install -e .
python -m parlament_mcp.server
```

### Cloud / Railway (SSE)

```bash
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 PORT=8080 python -m parlament_mcp.server
# SSE endpoint: http://your-host:8080/sse
```

### Network binding

By default the server binds to `127.0.0.1` (localhost only). Set
`MCP_HOST=0.0.0.0` **only** inside a container/cloud context (Docker, Railway,
Render, Kubernetes). Never bind to `0.0.0.0` on a local dev machine – it exposes
the server to your local network (NeighborJack risk); the server logs a warning
if you do so outside a detected container.

Transport is selected via `MCP_TRANSPORT` (`stdio` default, or `sse` /
`streamable-http`); `--http` is kept as an alias for `streamable-http`.

### Authentication (optional)

The HTTP transport is open by default (public read-only data). To require a
bearer token, serve via the CORS/auth app factory and set `MCP_BEARER_TOKENS`:

```bash
MCP_BEARER_TOKENS="alice:tok_abc,bob:tok_def" MCP_ALLOWED_ORIGINS="https://claude.ai" \
  uvicorn parlament_mcp.server:create_http_app --factory --host 0.0.0.0 --port 8080
```

Each request then needs `Authorization: Bearer <token>`; identity comes from the
validated token, not a session header (see [`docs/security.md`](docs/security.md)).

### Docker

```bash
docker compose up --build          # binds 127.0.0.1:8080 only
# or build the hardened image directly (non-root, read-only FS):
docker build -t parlament-mcp .
```

Kubernetes manifests (hardened `securityContext`, resource limits, egress
`NetworkPolicy`, `Mcp-Session-Id` sticky routing) live in [`deploy/k8s/`](deploy/k8s/);
an HAProxy stick-table example is in [`deploy/haproxy.cfg`](deploy/haproxy.cfg).

---

## 🔗 Synergies

| Partner Server | Combination |
|---|---|
| [`openparldata-mcp`](openparldata-mcp/README.md) | **Federal ↔ subnational** — same question across cantons & municipalities |
| [`fedlex-mcp`](https://github.com/malkreide/fedlex-mcp) | Law text ↔ parliamentary debate that created it |
| [`zurich-opendata-mcp`](https://github.com/malkreide/zurich-opendata-mcp) | City policy ↔ cantonal/federal motions |
| [`swiss-statistics-mcp`](https://github.com/malkreide/swiss-statistics-mcp) | Data backing ↔ motions citing statistics |

**Power query example:**
```
"Zeige mir alle Zürcher Motionen zu KI in der Bildung
 und verlinke die relevanten Bundesgesetze aus fedlex-mcp."
```

---

## 📊 Data Source

- **API:** [ws.parlament.ch/odata.svc](https://ws.parlament.ch/odata.svc/)
- **Authentication:** None (Phase 1 – No-Auth-First)
- **Protocol:** OData v3 / JSON
- **Coverage:** All parliamentary businesses since 1978; votes since ~2000.
  **Structured verbatim transcripts (Amtliches Bulletin) from 1999-12-06 onward**
  (earlier years 1891–1999 exist only as archive scans — see Known Limitations).
- **Update cycle:** Real-time (official government data)

### Copyright — verbatim quotation is allowed

Official proceedings of Swiss authorities are **excluded from copyright** under
**Art. 5 para. 1 lit. a URG** (Swiss Copyright Act). The verbatim wording of
parliamentary debates in the Amtliches Bulletin may therefore be reproduced and
quoted freely — which is exactly what the transcript tools return: the wording
itself, never a summary standing in for it.

---

## 📜 Data sources & licenses

| Source | License | Attribution |
|---|---|---|
| Curia Vista (ws.parlament.ch) | CC BY 4.0 | © Schweizer Parlament, CC BY 4.0 |

Every tool returns a typed structured response (FastMCP exposes the output
schema) carrying `source`, `license`, `provenance`, `match_type` and `count`
alongside typed `results`. Data is passed through unmodified.

## 🧭 Phase

This server is in **Phase 1 — Read-only Wrapper** (all tools `readOnlyHint: true`,
no writes). The full phase model and transition criteria are in
[`docs/roadmap.md`](docs/roadmap.md).

## 🔖 MCP Protocol Version

Tested/targeted against MCP spec **`2025-06-18`** (pinned as `PROTOCOL_VERSION`
in `src/parlament_mcp/config.py`). SDK updates are proposed monthly via
Dependabot; spec-version bumps are recorded in [`CHANGELOG.md`](CHANGELOG.md).

## 🧱 MCP primitives

Phase 1 uses **Tools only** — rationale and the Phase-2 Resources plan are in
[`docs/adr/ADR-003-mcp-primitives.md`](docs/adr/ADR-003-mcp-primitives.md).

## 🏷️ Tool annotations

All tools declare explicit annotations consistent with their behaviour:

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

Structured JSON logs go to **stderr** (stdout stays reserved for the stdio
protocol). OpenTelemetry tracing wraps each tool call and auto-instruments
outgoing HTTP; set `OTEL_EXPORTER_OTLP_ENDPOINT` (with the `otel-export` extra)
to ship spans. See [`docs/security.md`](docs/security.md) for the full security
posture (Lethal-Trifecta assessment, egress allow-list, gateway hardening).

---

## 🛡️ Safety & Limits

| Aspect | Details |
|--------|---------|
| **Access** | Read-only (`readOnlyHint: true`) — the server cannot modify or delete any data |
| **Personal data** | Parliamentary businesses are public record by law (BGÖ). No private data is accessed or stored. |
| **Rate limits** | Built-in per-query caps: max. 100 results (businesses/members), 50 (votes), 30 (transcript search), 10 (sessions). Transcript full text is capped per call and paginated — you never pull a whole session by accident. |
| **Timeout** | 20 seconds per metadata call; 45 seconds for transcript reads (verbatim search is heavier) |
| **Authentication** | No API keys required — Curia Vista is publicly accessible |
| **Data source** | Official Swiss federal government data (Schweizerische Parlamentsdienste) |
| **Terms of Service** | Subject to ToS of [ws.parlament.ch](https://ws.parlament.ch/) — Schweizerische Parlamentsdienste |

---

## Known Limitations

**General**
- OData `substringof()` filter is case-sensitive for some fields.
- Session names may be `null` in the API for very recent sessions – use session ID.

**Transcripts (Amtliches Bulletin)** — verified live 2026-07-19:
- **Temporal coverage: from 1999-12-06 only.** The structured `Transcript` entity
  reaches back to Dec 1999. Debates from **1891–1999 exist only as scanned
  archive documents** (Bundesarchiv / Amtsdruckschriften) and are **not
  connected** here (no OCR in scope). A query whose whole date window predates
  coverage returns an explanatory error, not an empty result.
- **No page number in the source.** The API carries no page/column field, so the
  classic `AB <year> N <page>` form cannot be built. We emit a stable, verifiable
  substitute — `AB <year> <N|S>, <date>, <speaker>` — plus the authoritative
  `source_url` (`SubjectId`) and the `transcript_id`. This is a documented,
  honest trade-off, not an omission.
- **Language behaviour (important).** `Language` is the *edition*, not the spoken
  language. The tools filter `Language eq 'DE'` purely to **deduplicate** the three
  byte-identical editions (DE/FR/IT) down to one copy. Every speech is returned in
  its **original wording**; a French or Italian speech is **not** hidden — its real
  language is reported in the `language` field (`de`/`fr`/`it`). The response
  states this via `language_note`.
- **Truncation is explicit, never silent.** Search returns short excerpts
  (`snippet`, ~320 chars) with `is_excerpt`, `total_length_chars` and a hint to
  fetch the full text. `parlament_get_transcript` caps output at `max_chars`; when
  it truncates it sets `is_excerpt=True` and returns a `next_offset` to continue.
- **Verbatim only, never summarised.** The wording *is* the product; the tools
  never substitute a summary for the actual text.
- **Latency:** a free-text `keyword` combined with a `speaker_name` is the slowest
  path (~40 s). Add a `session_id`, `business_number` or date window to keep reads
  around 1–2 s.

---

## 🧪 Testing

```bash
pip install -e ".[dev]"

# Unit + mocked integration tests (no network), as run in CI:
PYTHONPATH=src pytest tests/ -m "not live"

# Include live tests against the real ws.parlament.ch API:
PYTHONPATH=src pytest tests/ -m live
```

HTTP is mocked with `respx`; network-dependent tests are marked
`@pytest.mark.live` and excluded from CI via `-m "not live"`. Tool definitions are
pinned in `tool-hashes.json` (`python -m parlament_mcp.tool_hashes --check`).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Security

See [SECURITY.md](SECURITY.md) for the security policy and posture (vulnerability
reporting, Lethal-Trifecta assessment, accepted risks).

---

## License

MIT © [Hayal Oezkan](https://github.com/malkreide) — see [LICENSE](LICENSE)

<!-- mcp-name: io.github.malkreide/parlament-mcp -->

<!-- BEGIN GENERATED: install -->
## Installation

Run via [`uv`](https://docs.astral.sh/uv/)'s `uvx` — no clone or manual install needed. Add to your MCP client config (`mcpServers` for Claude Desktop, Cursor and Windsurf; use a top-level `servers` key for VS Code in `.vscode/mcp.json`):

```json
{
  "mcpServers": {
    "parlament-mcp": {
      "command": "uvx",
      "args": [
        "parlament-mcp"
      ]
    }
  }
}
```
<!-- END GENERATED: install -->
