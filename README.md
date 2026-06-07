[🇩🇪 Deutsche Version](README.de.md)

# 🏛️ parlament-mcp

[![CI](https://github.com/malkreide/parlament-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/parlament-mcp/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/parlament-mcp.svg)](https://badge.fury.io/py/parlament-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Swiss Public Data MCP Portfolio](https://img.shields.io/badge/Portfolio-Swiss%20Public%20Data%20MCP-blue)](https://github.com/malkreide)

> **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)** –
> connecting AI models to Swiss public data sources.

An MCP server that connects AI models to the **Swiss Federal Parliament** via the
[Curia Vista OData API](https://ws.parlament.ch/odata.svc/) (`ws.parlament.ch`).
Access motions, interpellations, votes, members, sessions, and debate transcripts –
with **no API key required** (Phase 1 – No-Auth-First).

---

## 🎯 Anchor Demo Query

> *"Welche Vorstösse zu KI in der Schule sind hängig?"*
> → `parlament_search_business(keyword="KI", keyword2="Schule", status="Eingereicht")`
>
> [→ More use cases by audience →](EXAMPLES.md)

Perfect for the **KI-Fachgruppe Stadtverwaltung Zürich**: find pending motions
on AI in education, digitisation initiatives, or any policy topic – instantly.

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
| `parlament_get_transcripts` | Debate excerpts by keyword or speaker (Amtliches Bulletin) |

---

## 🏗️ Architecture

```
┌──────────────────────────────────┐
│     MCP Host (Claude Desktop /   │
│     Claude API / IDE)            │
└─────────────┬────────────────────┘
              │ MCP Protocol (JSON-RPC 2.0)
              │ Transport: stdio (local) / SSE (cloud)
┌─────────────▼────────────────────┐
│         parlament-mcp            │
│   FastMCP · Python · Pydantic v2 │
└─────────────┬────────────────────┘
              │ HTTPS / OData v3
┌─────────────▼────────────────────┐
│  ws.parlament.ch / odata.svc     │
│  Curia Vista – No Auth Required  │
│                                  │
│  Business · Vote · MemberCouncil │
│  Session · Transcript · ParlGroup│
└──────────────────────────────────┘
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
- **Coverage:** All parliamentary businesses since 1978; votes and transcripts
- **Update cycle:** Real-time (official government data)

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
| `parlament_get_sessions`     | ✅ | — | ✅ | ✅ |
| `parlament_get_transcripts`  | ✅ | — | ✅ | ✅ |

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
| **Rate limits** | Built-in per-query caps: max. 100 results (businesses/members), 50 (votes/transcripts), 10 (sessions) |
| **Timeout** | 20 seconds per API call |
| **Authentication** | No API keys required — Curia Vista is publicly accessible |
| **Data source** | Official Swiss federal government data (Schweizerische Parlamentsdienste) |
| **Terms of Service** | Subject to ToS of [ws.parlament.ch](https://ws.parlament.ch/) — Schweizerische Parlamentsdienste |

---

## Known Limitations

- OData `substringof()` filter is case-sensitive for some fields
- Transcript text search can be slow for very broad queries (use `limit` to control)
- Session names may be `null` in the API for very recent sessions – use session ID
- Language filter is mandatory; currently only `DE` is fully tested (`FR`, `IT` available)

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
