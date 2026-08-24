# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Behoben

- **`DELETE` fehlte in `allow_methods` — in beiden Servern dieses Repositorys.**
  Auf streamable-http beendet die Methode eine Session ausdrücklich; der
  Preflight wies sie mit 400 ab. Ein Browser-Client konnte Sessions öffnen, aber
  nie schliessen. Das SDK bedient sie sehr wohl (`_handle_delete_request` in
  `mcp.server.streamable_http`; dessen 405-Antwort wirbt mit
  `Allow: GET, POST, DELETE`).

- **`openparldata-mcp`: die Routing-Header der Spec `2026-07-28` fehlten.**
  `Mcp-Method`, `Mcp-Name` und `Mcp-Protocol-Version` tragen seit dieser
  Revision die Wegwahl einer streamable-http-Anfrage. Ein Browser darf einen
  nicht safelisteten Header gar nicht erst senden, wenn der Server ihn nicht
  nennt — **jede** Cross-Origin-Anfrage starb am Preflight, vor dem ersten
  MCP-Byte. Gemessen vorher: `mcp-method` → 400, `mcp-protocol-version` → 400.

  Der Schwester-Server im selben Repository führte die Header längst; das
  Subprojekt war bei der damaligen Umstellung übersehen worden. `Last-Event-ID`
  kommt mit auf die Liste — er setzt einen abgerissenen SSE-Strom fort.

  Ohne diesen Punkt hätte der `DELETE`-Fix nichts gebracht: Wer nicht einmal
  eine Anfrage durchbringt, kann auch keine Session beenden.

### Hinzugefügt

- **`openparldata-mcp/tests/test_cors.py`.** Das Subprojekt hatte keine
  CORS-Tests — deshalb blieb beides unbemerkt.

### Behoben

- **Browser-Clients scheiterten am Preflight.** Spec `2026-07-28` routet eine
  Streamable-HTTP-Anfrage über `Mcp-Method`, `Mcp-Name` und
  `Mcp-Protocol-Version`; die CORS-Freigabeliste nannte keinen davon, dafür mit
  `Mcp-Session-Id` den Session-Header, der für sich genommen keine Anfrage
  routet. Ein Browser darf einen nicht safelisteten Header nicht senden, wenn
  der Server ihn nicht nennt: die Anfrage starb vor dem ersten MCP-Byte,
  während stdio und Python, für die kein Preflight gilt, weiterliefen.
  `tests/test_cors.py` fährt jeden Header einzeln gegen die zusammengebaute App
  und hält die Liste gegen die Konstanten aus `mcp.shared.inbound`.

- **`server_start` loggte eine drei Revisionen alte Protokoll-Version.**
  `PROTOCOL_VERSION` stand auf `2025-06-18`, waehrend der Server seit dem
  Umstieg auf `mcp` 2.x `2025-11-25` aushandelt. Ein Log, das etwas anderes
  sagt als die Leitung, ist beim Debuggen schlimmer als gar keines. Die
  Konstante wird jetzt aus `LATEST_HANDSHAKE_VERSION` abgeleitet statt ein
  zweites Mal hingeschrieben; ein Test faengt ab, dass daraus wieder ein
  Literal wird. Beide READMEs nannten dieselbe alte Zahl und sind nachgezogen.

### Hinzugefügt

- **Frischehinweise auf `tools/list` und `server/discover`** (SEP-2549, Spec
  `2026-07-28`): `ttlMs` 300000, `cacheScope` `public`. Das SDK setzt sonst
  «sofort veraltet, nie geteilt» und lässt damit jeden Client bei jeder
  Verbindung neu auflisten — für eine Liste, die beim Import feststeht und für
  jeden Aufrufer dieselbe ist. `prompts/list` und `resources/list` bleiben
  ungesetzt: dieser Server registriert weder das eine noch das andere.

- **Die Pruefsummen im Fixture-Nachweis waren Zierde.** `PROVENANCE.md` fuehrt
  je Datei einen SHA-256 — um genau einen Fall zu fangen: eine Aufzeichnung,
  die nach dem Lauf von Hand nachgebessert wurde. Eine korrigierte Antwort ist
  wieder eine erfundene, und von aussen ist ihr das nicht anzusehen.
  Nachgerechnet hat sie kein Test. `test_die_pruefsumme_im_nachweis_stimmt`
  tut es jetzt, ueber die Bytes auf der Platte statt ueber den Loader — genau
  die hat der Recorder gehasht.

- **Aufgezeichnete Fixtures statt handgeschriebener Erfolgs-Antworten.**
  `tests/fixtures/` hält jetzt sieben echte Antworten — eine je Werkzeug —,
  aufgezeichnet mit `scripts/record_fixtures.py` an demselben Ort, an dem der
  Server sie entgegennimmt (httpx-Response-Hook auf dem geteilten Client aus
  `server._get_client()`), also mit demselben User-Agent und Timeout wie im
  Betrieb. Herkunft, Schlüssel, Auswahlregel, Grösse und SHA-256 stehen je Datei
  in `tests/fixtures/PROVENANCE.md`; geladen wird über `tests/fixture_data.py`,
  gefahren in `tests/test_recorded_fixtures.py` (30 neue Tests, 128 statt 98).

  Das ist bei dieser Quelle keine Formsache: sie antwortet auf falsch
  verstandene Parameter nicht mit einem Fehler, sondern mit plausiblen Daten —
  `/persons/` verwirft bei `sort_by=lastname` still den `body_key`-Filter und
  meldet in `meta.total_records` weiter den gefilterten Wert. Ein Mock kann
  diese Klasse Fehler nicht sehen; er gibt zurück, was man ihm vorlegt.

  Eine Aufzeichnung je **Abfrage**, nicht je Endpunkt: alles läuft über
  denselben OData-Endpunkt und unterscheidet sich allein im `$filter`. Zugeordnet
  wird beim Abspielen nach der Anfrage, nicht nach der Reihenfolge.

  Die IDs der beiden Detail-Abrufe stehen nirgends als Zahl: der Recorder holt
  sie aus der jeweiligen Suche, die Tests lesen sie aus dem Schlüssel im
  Nachweis zurück. Eine eingetragene ID wäre in ein paar Wochen ein toter
  Verweis — und die Aufzeichnung schwiege darüber.

  Die handgeschriebenen Stubs bleiben für die Fehlerpfade — Timeout, 5xx, leere
  Trefferliste —, die sich nicht auf Zuruf aufzeichnen lassen.

- **Protokoll-Gate: beide Spec-Aeren gepinnt und geprueft**
  (`tests/test_protocol_version.py`). `mcp` 2.x bedient zwei Aeren ueber
  denselben Server — den `initialize`-Handshake, der bei `2025-11-25`
  deckelt, und den Pro-Request-Envelope, der `2026-07-28` erreicht.
  `LATEST_PROTOCOL_VERSION` ist ein Alias auf die **moderne** Aera; wer nur
  dagegen pinnt, laesst genau die Aera frei wandern, die heutige Clients
  aushandeln. Beide sind jetzt einzeln gepinnt, ein Dependabot-Bump von
  `mcp` kann keine davon still verschieben.

  Ohne gemessenen Teil: dieser Server baut keine ASGI-App, durch die sich ein
  `initialize` schicken liesse. Das Gate haengt deshalb an den SDK-Konstanten —
  die schwaechere Form, im Docstring benannt statt verschwiegen.

  Beide READMEs beschreiben die Aeren; ein Test haelt jede Sprache einzeln
  dagegen — im Portfolio sind EN und DE desselben Repos schon dreimal
  auseinandergelaufen, weil nur eine Fassung nachgezogen wurde.

- **`Mcp-Session-Id` ist weiterhin freigegeben — und das steht jetzt in einem
  Test statt in einem Satz.** Der Docstring von `tests/test_cors.py` nannte den
  Header die Spur einer Mechanik, die `2026-07-28` abgeschafft habe. Das stimmt
  nicht: `mcp` 2.x bedient beide Protokoll-Aeren, die Session gehoert zur
  Handshake-Aera, und der Server gibt den Header nicht ohne Grund auch in
  `expose_headers` frei.

  Nachgemessen statt aus Spec-Text geschlossen: `MCP_SESSION_ID_HEADER` steht
  unveraendert in `mcp/server/streamable_http.py`, und ein echter `initialize`
  durch den zusammengebauten ASGI-Stack bekommt eine Session-ID im
  Antwort-Header zurueck.

  `test_der_session_header_ist_weiterhin_freigegeben` haelt beides fest. Die
  Gegenprobe zeigt, dass es die Luecke wirklich gab: nimmt man den Header aus
  der Freigabeliste, faellt genau dieser eine Test, und die sieben bestehenden
  bleiben gruen.

### Changed

- **Der Backoff-Schlaf wird ueber einen Modul-Alias gepatcht, nicht ueber
  `asyncio.sleep`.** Die Tests nullten die Wartezeit mit
  `monkeypatch.setattr(<modul>.asyncio, "sleep", ...)`. Das liest sich lokal,
  ersetzt `sleep` aber auf dem geteilten Modulobjekt — fuer httpx, respx,
  pytest-asyncio und jeden anderen Importeur im Prozess. Das Modul legt die
  Naht jetzt als `_sleep = asyncio.sleep` offen; gepatcht wird diese.
  `test_der_retry_geht_ueber_den_alias` haelt sie: umgeht der Retry den Alias,
  faellt der Test in Sekundenbruchteilen. Ohne ihn fiel gar nichts — die Suite
  wurde nur ein Vielfaches langsamer, und eine laengere Laufzeit ist kein
  Signal, das jemand liest.

### Added

- **Retry-Politik gegenueber Curia Vista** (ARCH-014): `Retry-After` wird
  gelesen und schlaegt die eigene Backoff-Kurve, der Backoff ist gestreut, und
  ein Gesamtbudget begrenzt den ganzen Aufruf.

  `Retry-After` bei 429 und 503 in beiden Formen (Sekundenzahl und HTTP-Datum,
  RFC 9110 §10.2.3). Wer stattdessen weiter seine Kurve faehrt, ignoriert eine
  ausdrueckliche Angabe der Quelle. Ein unbrauchbarer Header fuehrt zurueck auf
  die Kurve statt zum Absturz.

  Jitter: `_BACKOFF_BASE ** attempt` war deterministisch. Faellt die API aus,
  waehrend mehrere Clients sie abfragen, retryen alle im Gleichtakt, und die
  Last kommt als Welle zurueck — genau wenn die API sich erholt. Neu landen
  exponentielle Wartezeiten in [0.5x, 1.5x]; auf einem `Retry-After` ist die
  Streuung einseitig ([1.0x, 1.25x]), weil frueher als angesagt die Missachtung
  derselben Angabe waere. Dazu ein Deckel von 20 s auf jede Einzelwartezeit.

  Gesamtbudget von 45 s: Vier Versuche a 45 s plus Backoff sind ueber drei
  Minuten, und `_MAX_ATTEMPTS = 4` sagt das nirgends. Der Wert liegt **bewusst
  ueber** dem MCP-Client-Default (`MCP_DEFAULT_TIMEOUT = 30.0`), aus demselben
  Grund, aus dem `TRANSCRIPT_TIMEOUT` bei 45 s steht: Unvorgefilterte
  Volltextsuchen dauern bis ~40 s, und ein Budget unter 30 s wuerde legitime
  Suchen abwuergen. Ein Test haelt diese Abweichung fest, damit sie eine
  dokumentierte Entscheidung bleibt.


## [0.3.5] - 2026-08-02

### Fixed

- **`structlog` carried no upper bound, and the index already serves a major past
  the floor.** The declared range was `structlog>=24.0.0`; PyPI has been serving
  `26.1.0`. The artefact does not change — the resolver's answer to the next
  fresh install does, and that is exactly how `swiss-energy-mcp` 0.3.3 became
  uninstallable when `mcp` 2.0.0 removed the module it imported.

  Now `structlog>=24.0.0,<27`. The bound is measured rather than guessed: this package
  installs and imports against `structlog 26.1.0` today, so the cap admits what
  demonstrably works and stops only the next, unknown major.

A dependency range only reaches users through a new release, hence the
version bump. No code changed.

## [0.3.4] - 2026-07-31

### Hinzugefuegt

- **Der Server nennt jetzt seinen Namen.** Bisher ging gegenueber jedem
  Upstream der httpx-Default hinaus: der Betreiber der Datenquelle sah
  eine Bibliothek, nicht uns, und hatte keinen Weg, uns bei Fehlverhalten
  zu erreichen. Neu traegt jeden der 2 HTTP-Clients
  `parlament-mcp/<version> (+github.com/malkreide/parlament-mcp)`.

  Die Version stammt aus `importlib.metadata` und kann nicht getrennt vom
  Paket driften.

### Fixed

- **Die HTTP-Factory wies unter jedem echten Hostnamen mit 421 ab (SEC-005).**
  `create_http_app()` baute die App mit `mcp.streamable_http_app()` ohne `host`.
  Unter mcp 2.x ist das kein neutraler Default: das SDK leitet daraus seine
  Host-Allow-List ab und aktiviert bei loopback-artigem Wert automatisch
  `127.0.0.1:*`. Da der Default `127.0.0.1` ist, traf das das dokumentierte
  `uvicorn … --factory --host 0.0.0.0`-Deployment.

  Der Kern der Sache: uvicorn ruft eine `--factory` **ohne Argumente** auf. Das
  `--host`-Flag erreicht die App also nie — es konfiguriert nur den Listener.
  Die Factory liest den Bind jetzt aus denselben Settings wie `main()`
  (`MCP_HOST`/`MCP_PORT` bzw. `PORT`). Der Docstring nennt beides ausdrücklich,
  weil die Env-Vars neben den uvicorn-Flags wie Redundanz aussehen und keine
  sind.

  Der Server hat zwei HTTP-Pfade; nur die Factory war betroffen. `main()` ruft
  `mcp.run(transport=…, host=settings.host, …)`, dort sieht das SDK den echten
  Bind.

  Eine echte Allow-List entsteht aus dem neuen `MCP_ALLOWED_HOSTS`; ohne diese
  Variable bleibt der Schutz auf einem Nicht-Loopback-Bind bewusst aus und der
  Aufrufer warnt — eine geratene Liste wäre genau der 421-Fall.

  **Unabhängig von `MCP_BEARER_TOKENS`.** Die Token-Prüfung sagt, *wer* fragt,
  die Host-Prüfung, *unter welchem Namen* der Server angesprochen wird. Ein
  Rebinding-Angriff läuft in einem Browser, der das Token bereits hält; ein Test
  hält fest, dass ein gültiges Bearer-Token einen fremden Host **nicht** rettet.

  14 neue Tests, darunter der tragende Fall „richtiger Hostname, falscher Port".
  Mutationsgetestet: nimmt man den `host`-Kwarg wieder weg, fallen genau die
  zwei Tests, die ihn betreffen.

  Geprüft mit den wörtlichen CI-Kommandos: die 14 neuen Tests grün,
  `ruff check src/ tests/` clean, Versions-Sync OK. Die beiden
  `test_live_*`-Fehler in `tests/test_server.py` bestehen vor und sind
  netzabhängig — mit gestashten Änderungen fallen sie identisch.


### Fixed

- **Capped `mcp` at `<2`.** `mcp` 2.0.0, published 2026-07-28, removed
  `mcp.server.fastmcp` — the module this server imports. With the previous
  unbounded `>=1.28.1` every fresh resolve picked 2.0.0 and failed at import
  with `ModuleNotFoundError`, in CI and for anyone running `pip install` alike.
  Verified in both directions: 2.0.0 fails, `<2` resolves to 1.29.0 and imports
  cleanly. Migrating to the 2.x API (`mcp.server.mcpserver`) stays a separate,
  deliberate piece of work.

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
