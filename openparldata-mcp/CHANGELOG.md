# Changelog

All notable changes to `openparldata-mcp` are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **Migrated to the `mcp` 2.x API.** This supersedes the interim `<2` cap from
  earlier in this same unreleased cycle: the cap bought time by pinning 1.29.0,
  it was never a destination. The constraint is now `>=2.0.0,<3` — the upper
  bound stays, anchored at the other end, because 3.0 may move the API again.

  This was the last server in the portfolio still on 1.x. Being nested inside
  `parlament-mcp` with its own manifest is why it was missed: enumerations of
  the portfolio list top-level repositories.

  The mechanical part is a rename: `mcp.server.fastmcp` → `mcp.server.mcpserver`,
  `FastMCP` → `MCPServer` (`server.py`, `bodies.py`, `client.py` and two test
  modules import `ToolError` from there).

  Two parts are **not** mechanical, and both sit in the HTTP path:

  - `mcp.settings` is read-only in 2.x. Setting host and port through it before
    `run()` — the only way to do it under 1.x, and what this server did — now
    raises `ValueError: "Settings" object has no field "host"`. Under
    `MCP_TRANSPORT=streamable-http` the server would not have started at all.
    `run()` takes the bind as keyword arguments instead.
  - `host` is an app-level argument the SDK derives its DNS-rebinding allow-list
    from, and it defaults to `127.0.0.1`. `create_http_app()` did not pass it,
    so 2.x would have auto-enabled a `127.0.0.1:*` allow-list and answered every
    request under a real hostname with **HTTP 421** — on exactly the
    `MCP_HOST=0.0.0.0` deployment the factory is documented for.

  Tool annotations moved to snake_case field names (`readOnlyHint` →
  `read_only_hint`). camelCase survives as a pydantic alias, so the **wire
  format is unchanged** — verified by serialising both spellings. Only attribute
  reads had to follow, which is why a test caught this and no client would have.

### Added

- **Host/Origin allow-list for the HTTP transport (`MCP_ALLOWED_HOSTS`, CSV).**
  Port-exact, with loopback always retained so container health checks keep
  working. Configured `MCP_ALLOWED_ORIGINS` are folded into the transport's
  origin list, otherwise the server would reject precisely the browser clients
  CORS permits; `*` is not copied across, since origins are compared literally.

  Without the variable, protection stays **off** on a non-loopback bind and the
  caller logs a warning. A guessed allow-list is exactly the 421 described
  above — off and visible beats wrong and silent.

- `tests/test_transport_security.py` (16 tests). The load-bearing one is
  **right hostname, wrong port**: `evil.example.com` alone proves nothing,
  because a fallback loopback policy rejects it too.

  Two tests pin what `create_http_app()` must read from the environment.
  uvicorn calls a `--factory` with *no arguments*, so `--host` configures the
  listener and never reaches the app; `MCP_HOST`/`MCP_PORT` look redundant next
  to the uvicorn flags and are not.


- German README (`README.de.md`) and a language switcher in `README.md`,
  matching the portfolio's bilingual convention and the cross-links from the
  federal `parlament-mcp` root README.

## [0.1.0] — 2026-07-18

Initial release. New server in the Swiss Public Data MCP portfolio covering the
**subnational** level (26 cantons + ~70 municipal parliaments) via the
OpenParlData.ch API. Complements `parlament-mcp` (federal Curia Vista), which
remains untouched.

### Naming

- Package `openparldata_mcp`, distribution `openparldata-mcp` — matching the
  portfolio's `*-mcp` source pattern.

### Added

- 13 read-only tools with the `oparl_` prefix: `oparl_list_bodies`,
  `oparl_search_affairs`, `oparl_get_affair`, `oparl_get_affair_documents`,
  `oparl_compare_bodies`, `oparl_search_persons`, `oparl_get_person`,
  `oparl_get_person_interests`, `oparl_search_interests`, `oparl_get_votings`,
  `oparl_get_voting_results`, `oparl_search_meetings`, `oparl_source_status`.
- **Architecture decision ARCH A (Live-API-only)**, documented in the README
  with the live-probe date (2026-07-18) and the rationale for deferring the bulk
  export to Phase 2.
- Lazily loaded **body cache** (`/v1/bodies/?indexed=true`, 24 h TTL) that
  validates every `body_key` before a request and returns fuzzy suggestions on
  unknown keys — guarding against the API's "silent empty" behaviour.
- Central `localize()` helper for multilingual fields (never uses
  `lang_format=flat`).
- Explicit PDF full-text truncation (`text_truncated`, `text_total_chars`).
- `data_quality: "unverified_source_data"` on all interests responses.
- Scale guardrail on individual votes (`voting_id` required, `limit` ≤ 500).
- Federal-level rejection: `body_key="CHE"` is refused by every tool, pointing to
  `parlament-mcp` (and `lobbywatch-mcp` for interests).
- Dual transport (stdio default, `sse` / `streamable-http` via `MCP_TRANSPORT`),
  egress allow-list, structured stderr logging, `127.0.0.1` default bind.

[Unreleased]: https://github.com/malkreide/openparldata-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/malkreide/openparldata-mcp/releases/tag/v0.1.0
