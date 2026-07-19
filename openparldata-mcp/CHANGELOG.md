# Changelog

All notable changes to `openparldata-mcp` are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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
