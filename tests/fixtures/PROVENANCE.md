# Herkunft der Fixtures

Aufgezeichnet am **2026-08-15** mit `PYTHONPATH=src python scripts/record_fixtures.py`.

Eine Antwort je **Abfrage**, nicht je Endpunkt: alles laeuft ueber denselben
OData-Endpunkt `ws.parlament.ch/odata.svc` und unterscheidet sich nur im
`$filter`. Eine Datei wuerde die Portfolio-Regel erfuellen und nichts belegen.

Der **Schluessel** unten ist, woran der Test eine Anfrage wiedererkennt: die
volle URL samt Query-String.

Die Antworten stammen aus dem geteilten Client von `server._get_client()`
(gleicher User-Agent, gleiches Timeout wie im Betrieb), abgegriffen ueber einen
httpx-Response-Hook. Ausgeloest hat sie jeweils das Werkzeug selbst — so belegt
die Aufzeichnung auch, dass das Werkzeug genau diese Anfrage schickt.

Das ist hier keine Formsache. Diese Quelle antwortet auf falsch verstandene
Parameter nicht mit einem Fehler, sondern mit plausiblen Daten: `/persons/`
verwirft bei `sort_by=lastname` still den `body_key`-Filter und meldet in
`meta.total_records` weiter den gefilterten Wert. Ein Mock kann das nicht
sehen — er gibt zurueck, was man ihm vorlegt.

## Auswahl

Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der
Listeneintraege. Kein Feld eines behaltenen Eintrags ist angetastet, und
Zaehlfelder daneben stehen wie geliefert — gerade sie sind hier der Beleg.

Die Fehlerpfade — Timeout, 5xx, leere Trefferliste — bleiben handgeschrieben.
Sie lassen sich nicht auf Zuruf aufzeichnen und sind als Erfindung in Ordnung.

## `get_business_1.json`

- **Werkzeuge:** `parlament_get_business`
- **Schluessel:** `https://ws.parlament.ch/odata.svc/Business(ID=20263723,Language='DE')?%24format=json`
- **Auswahl:** ungekuerzt
- **Groesse:** 7386 Bytes
- **SHA-256:** `0de1c405efbcde23e9864831069e7f81e9feddba6c9f88d5e246a23d3fcc2c89`

## `get_sessions_1.json`

- **Werkzeuge:** `parlament_get_sessions`
- **Schluessel:** `https://ws.parlament.ch/odata.svc/Session?%24format=json&%24top=3&%24filter=%28Language+eq+%27DE%27%29&%24orderby=ID+desc`
- **Auswahl:** ungekuerzt
- **Groesse:** 3978 Bytes
- **SHA-256:** `4cd980bf2405ff8d286f249d69207b61a0217f89b7518337bf04d9461ee2bda1`

## `get_transcript_1.json`

- **Werkzeuge:** `parlament_get_transcript`
- **Schluessel:** `https://ws.parlament.ch/odata.svc/Transcript(ID=378407L,Language='DE')?%24format=json`
- **Notiz:** Ungekuerzt: der Server paginiert *in* diesem Text.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 4646 Bytes
- **SHA-256:** `c8471c68b711bc4cdd824dfdbc1271cd2813cd87df6aa810bee0dec097ec24da`

## `get_votes_1.json`

- **Werkzeuge:** `parlament_get_votes`
- **Schluessel:** `https://ws.parlament.ch/odata.svc/Vote?%24format=json&%24top=3&%24filter=%28Language+eq+%27DE%27%29+and+%28substringof%28%27Klima%27%2CBusinessTitle%29%29&%24orderby=ID+desc`
- **Auswahl:** ungekuerzt
- **Groesse:** 5107 Bytes
- **SHA-256:** `aab38e13117c79e7a30b9a35b10f784c5ab605dfb7846708628fe7a375aa51de`

## `search_business_1.json`

- **Werkzeuge:** `parlament_search_business`
- **Schluessel:** `https://ws.parlament.ch/odata.svc/Business?%24format=json&%24top=3&%24filter=%28Language+eq+%27DE%27%29+and+%28substringof%28%27Klima%27%2CTitle%29%29&%24orderby=SubmissionDate+desc`
- **Auswahl:** ungekuerzt
- **Groesse:** 20462 Bytes
- **SHA-256:** `871457712c4db3987a1abb23daee58afce60204a43b4c838b0e2383237c554f3`

## `search_members_1.json`

- **Werkzeuge:** `parlament_search_members`
- **Schluessel:** `https://ws.parlament.ch/odata.svc/MemberCouncil?%24format=json&%24top=3&%24filter=%28Language+eq+%27DE%27%29+and+%28Active+eq+true%29+and+%28CantonAbbreviation+eq+%27BE%27%29&%24orderby=LastName+asc`
- **Auswahl:** ungekuerzt
- **Groesse:** 11778 Bytes
- **SHA-256:** `ccdb42e794854f59051eb0f2b1a375cc39e8e870a692beea7b7dc28f81f82f23`

## `search_transcripts_1.json`

- **Werkzeuge:** `parlament_search_transcripts`
- **Schluessel:** `https://ws.parlament.ch/odata.svc/Transcript?%24format=json&%24filter=%28Language+eq+%27DE%27%29+and+%28Type+eq+1%29+and+%28substringof%28%27Klima%27%2CText%29%29&%24orderby=MeetingDate+desc&%24top=3`
- **Auswahl:** ungekuerzt
- **Groesse:** 15222 Bytes
- **SHA-256:** `c2d6656cafbd63e676ea424c5401801aae11fd81988072a6f6ff84bc1cdd672f`
