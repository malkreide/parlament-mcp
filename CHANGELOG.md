# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
