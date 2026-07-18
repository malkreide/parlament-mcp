"""Zentrale Sprach-Normalisierung für die OpenParlData-API.

Mehrsprachige Felder kommen im Default als verschachtelte Objekte zurück, z.B.::

    {"de": "Tagesschule", "fr": "école à journée continue"}

Der Parameter ``lang_format=flat`` klingt praktisch, liefert aber in Kombination
mit ``fields=`` das Feld LEER zurück (verifizierte Probe 2026-07-18). Deshalb
fragen wir IMMER im (nested) Default ab und normalisieren clientseitig mit
``localize`` auf eine einzelne Zeichenkette.
"""

from __future__ import annotations

from typing import Any

DEFAULT_FALLBACK = ("de", "fr", "it", "en", "rm")


def localize(
    value: Any,
    lang: str = "de",
    fallback: tuple[str, ...] = DEFAULT_FALLBACK,
) -> str | None:
    """Ein mehrsprachiges Feld auf eine einzelne Zeichenkette reduzieren.

    - ``dict``: erste nicht-leere Sprache aus ``[lang, *fallback]``; als letzte
      Rettung irgendein nicht-leerer Wert des Dicts.
    - ``str``: unverändert (leerer String → ``None``).
    - alles andere / ``None`` → ``None``.

    Angewendet auf alle Felder vom Typ ``name``, ``title``, ``type_name``,
    ``state_name`` und ``url_external``.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in (lang, *fallback):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        # Nicht abgedeckte Sprache: irgendeinen befüllten Wert nehmen, statt None.
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return None
    # Zahlen o.Ä. defensiv in String wandeln (Rohdaten enthalten Artefakte).
    return str(value)
