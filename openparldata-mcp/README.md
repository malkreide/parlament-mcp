[🇩🇪 Deutsche Version](README.de.md)

# openparldata-mcp

MCP server for Switzerland's **subnational** parliaments — 26 cantons and ~70
municipal councils — via the [OpenParlData.ch](https://openparldata.ch) API.
Affairs, documents with extracted **PDF full text**, people, declared
interests, votings and meetings, exposed as 13 read-only tools with a
`oparl_` prefix.

> Part of the **Swiss Public Data MCP** portfolio. This server is the
> subnational counterpart to `parlament-mcp` (federal Curia Vista).

## Scope (non-negotiable)

This server covers **exclusively** the subnational level:

- ✅ **26 cantons** (`body_type="canton"`)
- ✅ **~70 municipal parliaments** (`body_type="municipality"`)
- ⛔ **Federal level** (`body_key="CHE"`) is **actively rejected** by every
  tool. For the Confederation, use **`parlament-mcp`** (Curia Vista). For
  federal lobbying/interests, `oparl_search_interests` additionally points to
  **`lobbywatch-mcp`** (editorially curated, with an industry taxonomy).

## Anchor demo query

> **«Which motions on all-day schools (Tagesschulen) were submitted in the
> Zürich city council since 2024, how did the council decide — and in which
> other Swiss cities is the topic politically active as well?»**

Flow:

1. `oparl_list_bodies(search="Zürich")` → resolve keys: `261` = City of Zürich,
   `ZH` = Canton of Zürich, `230` = Winterthur (`CHE` = federal, **blocked**).
2. `oparl_search_affairs(body_key="261", search="Tagesschule", date_from="2024-01-01")`
3. `oparl_get_affair_documents(affair_id=…, include_text=true)` — the extracted
   PDF full text.
4. `oparl_compare_bodies(search="Tagesschule", body_type="municipality")` —
   where else is it on the agenda?

## Tools (13)

| Tool | Purpose |
|---|---|
| `oparl_list_bodies` | List cantons/municipalities, resolve `body_key` |
| `oparl_search_affairs` | Search affairs of a body (metadata / docs / full text) |
| `oparl_get_affair` | Full affair detail (with `expand`) |
| `oparl_get_affair_documents` | Documents + extracted **PDF full text** |
| `oparl_compare_bodies` | Topic presence ranked across bodies |
| `oparl_search_persons` | Mandate holders of a body |
| `oparl_get_person` | Person profile (with `expand`) |
| `oparl_get_person_interests` | Declared interests of a person |
| `oparl_search_interests` | Search interests of a body (organisation → people) |
| `oparl_get_votings` | Votings for an affair or a body |
| `oparl_get_voting_results` | Individual votes of **one** voting (`voting_id` required) |
| `oparl_search_meetings` | Meetings of a body in a date range |
| `oparl_source_status` | API reachability, last fetch, body-cache age |

All tools are `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`.

## Architecture decision

**ARCH A — Live-API-only.** Every endpoint responds reliably in 0.15–2.4 s
(live probe **2026-07-18**). The server queries the live API on each call; there
is no local dump.

The bulk export (`https://files.openparldata.ch/exports/*.ndjson.gz`) is
deliberately deferred to **Phase 2**. It is only required *beyond* the API's
hard `offset > 100000` pagination limit — which in practice matters solely for
the `votes` table (**47,732,862** individual vote records). For everything this
server exposes, the live API is well within that ceiling, so a dump would add
sync/staleness cost without a functional gain today.

### Verified probe findings baked into the code (2026-07-18)

1. **Silent empty.** An invalid `body_key` returns HTTP 200 with an empty array
   instead of an error — *"Die API sagt nie Nein, sie sagt Nichts."* A lazily
   loaded body cache (`/v1/bodies/?indexed=true`, 97 entries, 24 h TTL) validates
   every `body_key` **before** the request and raises a helpful error with fuzzy
   suggestions.
2. **Language fields.** Multilingual fields arrive as `{"de": …, "fr": …}`. With
   `lang_format=flat` + `fields=…` they come back **empty**, so we never use
   `lang_format=flat`; a central `localize()` helper normalises `name`, `title`,
   `type_name`, `state_name`, `url_external` (and more) client-side.
3. **Full text.** `/v1/affairs/{id}/docs` exposes the extracted PDF full text in
   `text` — the most valuable field of this server. It is never silently
   shortened; on overflow it is explicitly truncated with `text_truncated=true`
   and `text_total_chars`.
4. **Scale guardrail.** `oparl_get_voting_results` requires `voting_id` and caps
   `limit` at 500 (API max would be 1000), because the `votes` table holds 47.7 M
   rows.
5. **Interests data quality.** Raw source data with parsing artefacts (a real ZH
   record has `name: {"de": "2007"}` — a year in the organisation field; `type`,
   `role_name`, `group` often empty). Every interests response carries
   `data_quality: "unverified_source_data"`.
6. **Error handling.** 404 → `{"detail": …}`; `offset > 100000` → RFC-7807 body
   with `max_offset`. Both are translated into readable tool errors.

## Install & run

```bash
# from the subdirectory of this repo (uvx-ready)
uvx --from "git+https://github.com/malkreide/parlament-mcp#subdirectory=openparldata-mcp" openparldata-mcp

# or locally
pip install -e ".[dev]"
openparldata-mcp            # stdio (default)
```

### Claude Desktop / MCP client

```json
{
  "mcpServers": {
    "openparldata": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/malkreide/parlament-mcp#subdirectory=openparldata-mcp",
        "openparldata-mcp"
      ]
    }
  }
}
```

### Transport

Default transport is **stdio**. For HTTP set `MCP_TRANSPORT`:

```bash
MCP_TRANSPORT=streamable-http MCP_HOST=127.0.0.1 MCP_PORT=8080 openparldata-mcp
```

`MCP_HOST` defaults to `127.0.0.1`; binding to `0.0.0.0` outside a detected
container logs a NeighborJack warning.

## Data source & license

- Data: [OpenParlData.ch](https://api.openparldata.ch/v1) — **CC BY 4.0**,
  attribution **"Source: OpenParlData.ch"** (emitted in every tool envelope).
- No authentication required.
- Code: **MIT**.

## Roadmap

- **Speeches tool.** Only a few bodies have speech records — CHE (332,859, out of
  scope here) and BS (98,796) plus a handful of others; the City of Zürich has 0.
  Not worth a Phase 1 tool; tracked here as a roadmap item.
- **Phase 2 — bulk export.** NDJSON dump ingestion to serve the `votes` table
  (47.7 M rows) beyond the `offset > 100000` ceiling.
