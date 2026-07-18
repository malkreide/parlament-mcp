"""Tests für den zentralen Sprach-Helper."""

from __future__ import annotations

from openparldata_mcp.localize import localize


def test_prefers_requested_language():
    assert localize({"de": "Schule", "fr": "école"}, lang="de") == "Schule"
    assert localize({"de": "Schule", "fr": "école"}, lang="fr") == "école"


def test_falls_back_through_chain():
    # gewünschte Sprache leer -> nächste befüllte Sprache
    assert localize({"de": "", "fr": "école"}, lang="de") == "école"


def test_falls_back_to_any_value_for_uncovered_language():
    assert localize({"it": "scuola"}, lang="de") == "scuola"


def test_plain_string_passthrough_and_empty_to_none():
    assert localize("Tagesschule") == "Tagesschule"
    assert localize("") is None


def test_none_and_all_empty():
    assert localize(None) is None
    assert localize({"de": "", "fr": ""}) is None


def test_numeric_artifact_is_stringified():
    # Rohdaten-Artefakt: Zahl statt Text im Feld.
    assert localize(2007) == "2007"
