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

Perfect for the **KI-Fachgruppe Stadtverwaltung Zürich**: find pending motions
on AI in education, digitisation initiatives, or any policy topic – instantly.

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
MCP_TRANSPORT=sse PORT=8080 python -m parlament_mcp.server
# SSE endpoint: http://your-host:8080/sse
```

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

## Known Limitations

- OData `substringof()` filter is case-sensitive for some fields
- Transcript text search can be slow for very broad queries (use `limit` to control)
- Session names may be `null` in the API for very recent sessions – use session ID
- Language filter is mandatory; currently only `DE` is fully tested (`FR`, `IT` available)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT [malkreide](https://github.com/malkreide)
