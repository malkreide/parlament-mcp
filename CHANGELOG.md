# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Amtliches Bulletin – verbatim debate transcripts.** New separated module
  `parlament_mcp.transcripts` with two tools:
  - `parlament_search_transcripts` — searches the `Transcript` entity and returns
    short, **citable excerpts** (`snippet`, ~320 chars) with an AB citation, a
    stable `source_url` (`SubjectId`), speaker/council/date/`language`, and hard
    caps (default 10, max 30 hits). Filters: `keyword` (full text), `speaker_name`,
    `session_id`, `council`, `business_number`, `date_from`/`date_to`.
  - `parlament_get_transcript` — fetches the **verbatim full text** of a single
    speech by ID, capped at `max_chars` and paginated via `offset`/`next_offset`.
  - Mandatory Pydantic-v2 fields on every result: `citation`, `source_url`,
    `speaker`, `council`, `date`, `language`, `is_excerpt`, `total_length_chars`.
- Transcript tests (`tests/test_transcripts.py`) with `respx` fixtures built from
  real, shortened API responses, plus `@pytest.mark.live` end-to-end checks.
- README (EN/DE): second Anchor Demo Query (verbatim transcripts), transcript
  path in the architecture diagram, Art. 5 URG note (official proceedings are
  copyright-exempt → verbatim quotation allowed), a Testing section, and expanded
  Known Limitations.

### Changed
- **Transcript language handling.** Filtering `Language eq 'DE'` now serves purely
  to deduplicate the three byte-identical editions (DE/FR/IT); the verbatim `Text`
  is always the original wording and the real spoken language is surfaced as
  `language` (`de`/`fr`/`it`). French/Italian speeches are no longer hidden by the
  edition filter — verified live.
- Transcript reads use a dedicated 45 s timeout and retry with exponential backoff
  (metadata tools are unchanged at 20 s, no retry).

### BREAKING
- Removed the speculative `parlament_get_transcripts` tool (it searched `Text`
  without an indexed prefilter — timing out on broad queries — returned vote-result
  and procedural rows as "transcripts", and carried no citation). It is replaced by
  the two tools above. `tool-hashes.json` updated accordingly (7 tools); clients
  should re-approve the tool set.

### Known findings (transcript API, live-probed 2026-07-19)
- The `Transcript` entity carries **no page/column field**, so `AB <year> N <page>`
  cannot be constructed — a stable substitute reference + `SubjectId` URL is used.
- `Language` is the **edition**, not the speech language (`LanguageOfText` is the
  latter). Structured coverage starts **1999-12-06**; 1891–1999 is scans only.
- `$count` over a `Text` `substringof` is ~40 s; retrieving top-N is ~3 s. An
  exact prefilter (`IdSession`/`VoteBusinessNumber`) cuts full-text reads to ~1 s.

## [0.3.0] - 2026-05-30

> Version `0.2.0` was already taken by an earlier PyPI release, so this
> audit-hardening release ships as `0.3.0`.
>
> Targets MCP protocol version `2025-06-18`. Tool definitions are pinned in
> `tool-hashes.json` (CI-verified). **Tool input/output schemas changed in this
> release** (see BREAKING) — `tool-hashes.json` updated accordingly; clients
> should re-approve the tools.

### BREAKING
- Tools now return **typed structured Pydantic responses** instead of strings
  (SDK-002): search/list tools return an envelope (`source`, `license`,
  `provenance`, `match_type`, `count`, typed `results`); `parlament_get_business`
  returns a `BusinessDetail`. The `response_format` parameter was removed
  (output is always structured; no more Markdown/JSON toggle).

### Security
- Optional bearer authentication + cryptographic session binding for the HTTP
  transport (`parlament_mcp.auth`, SEC-009): set `MCP_BEARER_TOKENS` to require
  `Authorization: Bearer` per request; `SessionSigner` issues HMAC-signed,
  user-bound session tokens (TTL + revocation). Off by default (public data).
  `create_http_app()` now wires the bearer middleware alongside CORS.
- Bind to `127.0.0.1` by default; `0.0.0.0` now requires an explicit
  `MCP_HOST` env var and logs a NeighborJack warning outside container
  contexts (audit finding SEC-016).
- Code-layer egress allow-list (`ALLOWED_HOSTS`, frozenset) enforced before
  every outbound request, plus a Kubernetes egress `NetworkPolicy`
  (SEC-021). Network egress documented in `docs/network-egress.md`.
- Strict numeric input validation (`strict=True`, bounds, `min_length`,
  whitelisted patterns) at all tool boundaries (SEC-018).
- Hardened container: multi-stage `Dockerfile` (non-root UID 10001), K8s
  `securityContext` (read-only FS, dropped caps, seccomp) (SEC-007/SCALE-004).
- Tool-definition hash pinning (`tool-hashes.json`) verified in CI against
  rug-pull; gitleaks + Trivy added to a `security.yml` workflow (SEC-022).
- Reusable MCP-gateway building blocks: tool allow-listing and pre-flight
  tool-poisoning detection (`parlament_mcp.gateway`, SEC-014/SEC-015).

### Added
- Structured JSON logging to stderr via structlog (OBS-003/OBS-004).
- OpenTelemetry tracing per tool call with httpx auto-instrumentation
  (OBS-006); OTLP export via the optional `otel-export` extra.
- `Context` injection in all tools (lifecycle logging + progress reports for
  transcript search) (SDK-003).
- Central `Settings` object via pydantic-settings (ARCH-004).
- JSON responses now carry a consistent envelope (`source`, `license`,
  `provenance`, `match_type`, `count`) and empty results return suggestions
  instead of a blank "not found" (CH-004 / SDK-002 / ARCH-003).
- `<use_case>` / `<important_notes>` tags in every tool description (ARCH-002).
- Deployment manifests: `docker-compose.yml`, `railway.toml`, `deploy/k8s/`,
  `deploy/haproxy.cfg` (SCALE-001/002/003/006).
- Docs: `docs/security.md` (Lethal-Trifecta SEC-019, session SEC-009, gateway),
  `docs/roadmap.md` (phase model OPS-003), `docs/network-egress.md`, and ADRs
  (server separation, scaling, MCP primitives ARCH-008).
- `.github/dependabot.yml` for monthly SDK/dependency updates (ARCH-012).

### Changed
- HTTP transport selection is now env-driven (`MCP_TRANSPORT`, `MCP_HOST`,
  `MCP_PORT`/`PORT`); `--http` kept as an alias. Aligns runtime behaviour
  with the documented cloud usage.
- Reuse a single pooled `httpx.AsyncClient` for the server lifetime via a
  FastMCP lifespan instead of creating a client per tool call (audit
  finding SDK-001).
- Execution errors are now surfaced as `isError` tool results (via
  `ToolError`) instead of plain strings, with masked messages (OBS-001/002).
- Console entry point now calls `parlament_mcp.server:main` (settings + logging
  + tracing setup) instead of `mcp.run` directly.

## [0.1.0] - 2026-04-01

### Added
- Initial release
- `parlament_search_business`: search Vorstösse by keyword, type, status, council, date
- `parlament_get_business`: full details of a single business including all text fields
- `parlament_search_members`: find councillors by canton, party, council
- `parlament_get_votes`: parliamentary votes with Ja/Nein meaning
- `parlament_get_sessions`: list recent sessions with IDs
- `parlament_get_transcripts`: debate transcript excerpts by keyword or speaker
- Dual transport: stdio (Claude Desktop) and SSE/Streamable HTTP (cloud)
- Bilingual documentation (English README + German README.de.md)
- CI via GitHub Actions with pytest (unit + mocked integration tests)
- PyPI publishing via OIDC Trusted Publisher
