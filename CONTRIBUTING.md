# Contributing to parlament-mcp

[🇩🇪 Deutsche Version](CONTRIBUTING.de.md)

Thank you for your interest in contributing! This server is part of the
[Swiss Public Data MCP Portfolio](https://github.com/malkreide).

## Getting Started

```bash
git clone https://github.com/malkreide/parlament-mcp
cd parlament-mcp
pip install -e ".[dev]"
```

## Running Tests

```bash
# Unit + mocked integration tests (no network)
pytest tests/ -m "not live" -v

# Live API tests (requires internet)
pytest tests/ -m live -v
```

## Code Style

```bash
python -m ruff check src/ tests/
python -m ruff format src/ tests/
```

## Adding a New Tool

1. Define a Pydantic v2 `BaseModel` for inputs in `server.py`
2. Implement the tool with `@mcp.tool(name=..., annotations={...})`
3. Always include `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
4. Add unit tests (mocked) and a `@pytest.mark.live` integration test
5. Document the new tool in both `README.md` and `README.de.md`

## Portfolio Conventions

- **No-Auth-First**: Phase 1 tools must work without any API key
- **Language filter**: Always include `Language eq 'DE'` as default OData filter
- **Error handling**: Return human-readable German error strings, never raise exceptions to the host
- **Pagination**: All list tools must support `limit` and `offset` parameters
- **Response formats**: Support both `markdown` (default) and `json`

## Reporting Issues

Please open a GitHub issue with:
- The tool name and parameters used
- The actual vs. expected output
- The relevant API endpoint (if known)

## The live suite: when it runs, and who sees a red result

**Cadence:** daily at 04:00 UTC, plus on demand via *Actions → Live API tests → Run
workflow*. See [`.github/workflows/live-test.yml`](.github/workflows/live-test.yml).

**Who sees it:** A red run opens an issue labelled `upstream` and the stable title “Live-Tests gegen ws.parlament.ch (Curia Vista) rot (<Datum>)”. A second red run recognises the open issue by its title prefix and appends to that same thread rather than opening a second one. Once the suite is green again, the issue closes itself.

**Three answers, not two.** `scripts/classify_live_run.py` reads the JUnit XML rather than
the exit code and separates `clear` (ran, green), `finding` (ran, something
fell) and `unknown` (did not run — install failed, nothing collected,
everything skipped). An `unknown` never closes an issue: closing would claim a
comparison that never happened.

**A red live run does not necessarily mean *our* bug.** It means the contract
with the source has changed, or the source is down. Both belong seen; only the
first belongs fixed. Please read the run before disabling the job — that is how
this check dies, and it is the only one in the repository that can contradict a
wrong assumption about ws.parlament.ch (Curia Vista). Every other test asserts against a fixture, and
the fixture was written from the same assumption as the code.
