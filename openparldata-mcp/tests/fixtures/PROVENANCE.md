# Herkunft der Fixtures

Aufgezeichnet am **2026-08-15** mit `PYTHONPATH=src python scripts/record_fixtures.py`.

Eine Antwort je **Abfrage**, nicht je Endpunkt: alles laeuft ueber
`api.openparldata.ch/v1` und unterscheidet sich im Pfad und in den
Query-Parametern. Eine Datei wuerde die Portfolio-Regel erfuellen und fast
nichts belegen.

Der **Schluessel** unten ist, woran der Test eine Anfrage wiedererkennt: die
volle URL samt Query-String. Zugeordnet wird nach der Anfrage und nicht nach
der Reihenfolge — `oparl_compare_bodies` fragt mehrere Koerperschaften in
einem Aufruf ab.

Die Antworten stammen aus dem geteilten Client von `client.get_client()`
(gleicher User-Agent, gleiches Timeout wie im Betrieb), abgegriffen ueber einen
httpx-Response-Hook. Ausgeloest hat sie jeweils das Werkzeug selbst — so belegt
die Aufzeichnung auch, dass das Werkzeug genau diese Anfrage schickt.

Das ist hier keine Formsache. Diese Quelle antwortet auf falsch verstandene
Parameter nicht mit einem Fehler, sondern mit plausiblen Daten: `/persons/`
verwirft bei `sort_by=lastname` still den `body_key`-Filter und meldet in
`meta.total_records` weiter den korrekt gefilterten Wert. Ein Mock kann das
nicht sehen — er gibt zurueck, was man ihm vorlegt.

Die IDs der Detail-Abrufe stammen aus den Suchen daneben und stehen nirgends
als Zahl im Code. Sonst muesste die Aufzeichnung zur eingetragenen ID passen —
und der naechstliegende Weg dahin waere, sie danach auszuwaehlen.

## Auswahl

Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der
Listeneintraege. Kein Feld eines behaltenen Eintrags ist angetastet, und
`meta.total_records` daneben steht wie geliefert — gerade dieses Feld ist hier
der Beleg.

Wo der Server *in* einer Liste sucht oder zaehlt, wird nicht gekuerzt: ein
Schnitt erfaende dort ein anderes Ergebnis.

Die Fehlerpfade — Timeout, 5xx, leere Trefferliste — bleiben handgeschrieben.
Sie lassen sich nicht auf Zuruf aufzeichnen und sind als Erfindung in Ordnung.

## `affair_documents_1.json`

- **Werkzeuge:** `oparl_get_affair_documents`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/336140/docs?limit=100`
- **Auswahl:** ungekuerzt
- **Groesse:** 24471 Bytes
- **SHA-256:** `7691a228508f8980ed504f5be820bd35a64ffa710aee1f8c2c431857823146f6`

## `compare_bodies_1.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=4001&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2691 Bytes
- **SHA-256:** `e21139eecc67dac0514befd3ba28da474b7c11773a963ad50dd3abce1ed580a2`

## `compare_bodies_10.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=53&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2648 Bytes
- **SHA-256:** `846c5852bcda1fb0b8ba1c897d265e71603f30f8acc84d1b77dd7e8e92bea8ac`

## `compare_bodies_11.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=5002&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `b80aa6a1e3e249a886e0c7f38c4972a530e6a9b45c21465856727d4d59632de2`

## `compare_bodies_12.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=4566&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2680 Bytes
- **SHA-256:** `9baf00089ace24790816b000e082ba20c4d572e249ef1fe12be0ce367cef1cb9`

## `compare_bodies_13.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=2125&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `8fda1f91770ab38f502e21d77b9349af0c028e4e0acc1bdbbf94fd16b7722893`

## `compare_bodies_14.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=2196&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `1ef77f3be77aae37e7189a0ae9ed3c62956b694663a01b12550676c3cc413671`

## `compare_bodies_15.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6621&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `5486e2276c323e4981ce868d370ee9ec837a22d21c5a8f095117ae468eb85999`

## `compare_bodies_16.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=3443&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2664 Bytes
- **SHA-256:** `df71d6a17afd146c1782d77ef990a775a1a46b9de1ce7f9e1984c94b8fbfeab2`

## `compare_bodies_17.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=3001&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `e024654516aa0045e5746f99bdaac6d3a4fef3b17b2a2713a3cf5faabe31ea04`

## `compare_bodies_18.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=1058&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2742 Bytes
- **SHA-256:** `e83fbb974634f24245597ac2ed4cddac3fab4392c0ea851e043ed455b5656278`

## `compare_bodies_19.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=296&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 501 Bytes
- **SHA-256:** `dd7f2978240f1032e31e8ff42fe2051cbd9e7c20e80b7702a1fba914b54be6d4`

## `compare_bodies_2.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=3901&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2421 Bytes
- **SHA-256:** `47ed6b67ec587f4cd28d64cc61c87580aed1aa7dc2212881abb966a97dd75792`

## `compare_bodies_20.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=581&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 501 Bytes
- **SHA-256:** `34429455967b52a98e05a70fd592a4ccbf780700f19ee739d26b00fa0108d8b2`

## `compare_bodies_21.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=62&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2468 Bytes
- **SHA-256:** `47e32c1d50f29906a3be20bd37d02ebe0e3924f965160581f28334c2c9a1edcb`

## `compare_bodies_22.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=4671&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `be5734334ac42ffbc7accd511fac4e1be3b65d9853e6748ea6226300fd9eedcb`

## `compare_bodies_23.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=1059&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2815 Bytes
- **SHA-256:** `499f91c698d2339e07a7ddc6dce0c9f81e09720411a4081068ad6c3a70ce9cb2`

## `compare_bodies_24.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6421&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `32ccbb85adefaabf3282a1220905865d276d0397fb29e5bf209ca48c86b5ca67`

## `compare_bodies_25.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=329&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2664 Bytes
- **SHA-256:** `04d126c95f83be77663c9f22c427551455b780edff93c030605ac71cece4553c`

## `compare_bodies_26.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=5586&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `915f44bc9eb4c7089a942b3958f53d2717438960f5759d57ec8491b2f230b658`

## `compare_bodies_27.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=4201&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2723 Bytes
- **SHA-256:** `9b7d91e74783527eb15b619ba1442d6776a8df2c6141201ec9dfa5d58ac7e44d`

## `compare_bodies_28.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=2829&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 3367 Bytes
- **SHA-256:** `2a9343de8ddacb5aedba11336e0c4b4f77fa9bc65752095946eee0bd31f83f0d`

## `compare_bodies_29.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=5113&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `daedb4f8a6d292919a76b631d75a0a4337bd0781b5b4847f3a322ce021d26502`

## `compare_bodies_3.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=243&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2517 Bytes
- **SHA-256:** `1e8c16cd96a9d3c5330ba8d841efc8cbe47444a4b00b7ae39c7f4aeacd26eacd`

## `compare_bodies_30.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=5192&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `eb95c9a4f968f2fb7df842265ae4f34ece3572efbb6e70ccb12af917331ae571`

## `compare_bodies_31.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=1061&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2620 Bytes
- **SHA-256:** `62cb3eff5f1efe02bcdc9011ff411e31924b117a8ad48ec12563ba93db627668`

## `compare_bodies_32.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6136&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `3fe770ec7ce674557d8c1277e1948075d8817f463dc5887ff4c787f0b4e9460a`

## `compare_bodies_33.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=306&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2682 Bytes
- **SHA-256:** `6f43e0cd369a3c0ed12a3e6fa3799f7c118f55cc571f1e4e27b5511b799c98f0`

## `compare_bodies_34.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=5254&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `6fd8cff3888dfd5d3cefaaa1cff9a785d383261865dcd01dde7bf7943da2fede`

## `compare_bodies_35.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6153&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `fe9655a7a8a29a497257f3186756a6456b2b1ca4e2c2b8b8d25ff454eb4a4d04`

## `compare_bodies_36.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=616&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2530 Bytes
- **SHA-256:** `bd41e1d4d8e9c7d307dbf939c4f5d09e0e7280ec58f6264ef087d4061de1d125`

## `compare_bodies_37.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6458&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `138e552a8b655a9fa6fe32bb8b91ed93779a416b95f5df43596554a9e0baf7d3`

## `compare_bodies_38.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=2937&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2649 Bytes
- **SHA-256:** `c1901c708e5603a58f175e08c5279c1ac2d31b68ef2c94dfba2d0526ab6be157`

## `compare_bodies_39.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=2581&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2586 Bytes
- **SHA-256:** `1ca097c9977f6471fec5a8e640517d14169c3baacc95c8c16252c6dad111cc95`

## `compare_bodies_4.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=191&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2544 Bytes
- **SHA-256:** `5e618c17d4f572cd05e52e4760302fffb9d54d36b7de08393515e689d2d00916`

## `compare_bodies_40.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=66&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2520 Bytes
- **SHA-256:** `9c045e5a7a8660d339ac834c7a7b25c7ce4028579c6045004650856c4ceb118f`

## `compare_bodies_41.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=2831&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2610 Bytes
- **SHA-256:** `f2e79708e076436d62361bcd461481ec3e71295e0c939f41aaaa6cf7b3e9a419`

## `compare_bodies_42.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=2703&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2725 Bytes
- **SHA-256:** `f851b6b07104bf3a25358a9fae45249d81fd6fe3a9c8ea4ac21230b23f6bc35d`

## `compare_bodies_43.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=2939&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2725 Bytes
- **SHA-256:** `3208d0aa89256c5652e53dc15725385043b7625bf693c23d47c4dc22febd13b2`

## `compare_bodies_44.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=247&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 501 Bytes
- **SHA-256:** `392a54786eed53c8b4c011e2f475c614dffa40fc1799fe8be5c2241c3ef97a6c`

## `compare_bodies_45.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6248&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `efd6ef545a03fc073949e80954cd054d415c412f6f23edaf1ebabd3e7cb22886`

## `compare_bodies_46.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6266&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `6d6e13ab7bcf72cdfa277a53f9577fb69243b2807e1277beef9fb4129c4e2caf`

## `compare_bodies_47.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=3203&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 3003 Bytes
- **SHA-256:** `1a921d5f8bbbcc80f3880bdab2249d261c7fb840974ef36a9987eca968c8a9d4`

## `compare_bodies_48.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=942&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2624 Bytes
- **SHA-256:** `509f143b1ae824f27cfe4eec31127cbce8f8716e236118921acfe4484e6e0042`

## `compare_bodies_49.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=198&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2661 Bytes
- **SHA-256:** `b9e1ec793d5c2159003582d55e7f7f9046e18df932930cb8610838e3ed523550`

## `compare_bodies_5.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=1024&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2695 Bytes
- **SHA-256:** `e81e247d9afe8c15a334d349066df0fc46b468f144e82fed744c439098bca31e`

## `compare_bodies_50.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6643&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `2128d9bfb404b462363a106bfdf3c8b145b9dbdf0f289030846694e7094a7539`

## `compare_bodies_51.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=4045&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2716 Bytes
- **SHA-256:** `1e9340e1e7e9304af178d31ff861c72c6aeb276dc8ab00ef3e208bf093f82b94`

## `compare_bodies_52.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=121&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2696 Bytes
- **SHA-256:** `a06b9e9153a10a972679229a9f666f1aca9f8ccdc2dab8fef5c81ab58e384f07`

## `compare_bodies_53.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=3427&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2816 Bytes
- **SHA-256:** `985d2d1e99d1e85aa4c03d4bda6cc6c395acab9f53c5fc74517bdb5a22bb4c7f`

## `compare_bodies_54.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=230&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2618 Bytes
- **SHA-256:** `74b098e11f76648fca7ea3282068a65e19093a3a8a6b2fd5722b4ead03a55be8`

## `compare_bodies_55.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=293&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2726 Bytes
- **SHA-256:** `66b1bb281ababaac1904da7a32a55905fbc05598bcbce1455ffca74f9960ea81`

## `compare_bodies_56.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=4082&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2651 Bytes
- **SHA-256:** `0722d4aa6668413edd67b10c8cc19b5b0ec175f535706f1c317799a6661187b8`

## `compare_bodies_57.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=5938&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `a2edde0fb8e797130aba4274f4e9b7f960c27a871784d651d5041b7e2781ac38`

## `compare_bodies_58.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=4289&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2630 Bytes
- **SHA-256:** `42afc8bb3a36d103c3a0060546966da302e6b24b8fb1efbaa04da3bee9c89470`

## `compare_bodies_59.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=361&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2912 Bytes
- **SHA-256:** `980633d7fd788ca346d3bf5fe7202426ad3a09e5e62d657d4f437f56e08bc570`

## `compare_bodies_6.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=131&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2515 Bytes
- **SHA-256:** `1d61a2f05aa0718c68d7a113b047d91b1c6396a635c78535fee4dad59d40892b`

## `compare_bodies_60.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=1711&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2642 Bytes
- **SHA-256:** `e5a3623d704a0dfd01c2272920adaf755038afb6e582d0e162d5bae7e710d47f`

## `compare_bodies_61.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=261&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2866 Bytes
- **SHA-256:** `eac5e4a3a255fd4c0ce84dc009c2241905c8aa45b5b97244bc6eb4310ef54ac3`

## `compare_bodies_62.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6082&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `30cd9d2f726970cf2e26cc81982bed23160af6acd8315ffce054e52dcba6e6fd`

## `compare_bodies_63.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6152&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `989a26c6692fbdd301d908d4e6dd44e6a16526e0d990d84f19844d50e9fdc8e7`

## `compare_bodies_64.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6023&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `2061f0a290e094980a56d665a9e0f5229bdebd271bb8bb0185929fd63e71449e`

## `compare_bodies_65.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6133&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `6ccb76ce7653a94700910fbe457be23a1a8d6f8959ee4507cd755c3291ef11d3`

## `compare_bodies_66.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6217&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `8efdd4a046b8337cc06c8b78d7eedf57c19b355731380c600a4e7ffd698ddec6`

## `compare_bodies_67.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6037&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `fa77b9992928811b1011684a545110732a2b525214010d8f28efd59bb0f0a5c4`

## `compare_bodies_68.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=6025&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 504 Bytes
- **SHA-256:** `dd0e15c9d4043e9c50fb9735949dc84df310a95962e7d998a3c9a21a56a99240`

## `compare_bodies_69.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=743&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2760 Bytes
- **SHA-256:** `116c9e7925d5c6665e226c456768e4e9b0677c4932c737f7dea12a527e287477`

## `compare_bodies_7.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=4401&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2876 Bytes
- **SHA-256:** `0f0b9d0736ee4bda9b26d124fd06847f1e3c09fb96be8823a7d539e345dea977`

## `compare_bodies_8.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=351&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2860 Bytes
- **SHA-256:** `7e6f4310ef23b2f2a5a67180ed00ec24c1d3a4f9f3fe026c8f59d8812442c278`

## `compare_bodies_9.json`

- **Werkzeuge:** `oparl_compare_bodies`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=404&search=Klima&limit=1`
- **Notiz:** Ungekuerzt: der Vergleich zaehlt *in* den Antworten je Koerperschaft.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2637 Bytes
- **SHA-256:** `37c5d18fb20667ebf0c39cc9ab4bc9afc0623cb8d05b23d431e940fa498e5938`

## `get_affair_1.json`

- **Werkzeuge:** `oparl_get_affair`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/336140`
- **Auswahl:** ungekuerzt
- **Groesse:** 2066 Bytes
- **SHA-256:** `bba0782edb8a00525fd2079629d3674caf757fca91e8a97f8611ac77a28299d7`

## `get_person_1.json`

- **Werkzeuge:** `oparl_get_person`
- **Schluessel:** `https://api.openparldata.ch/v1/persons/572`
- **Auswahl:** ungekuerzt
- **Groesse:** 2293 Bytes
- **SHA-256:** `7babd87f459b73de1c69ca67ae19a24babf2606e4911c885e1ba82a857719b17`

## `get_votings_1.json`

- **Werkzeuge:** `oparl_get_votings`
- **Schluessel:** `https://api.openparldata.ch/v1/votings/?limit=3&offset=0&sort_by=-date&body_key=261`
- **Auswahl:** ungekuerzt
- **Groesse:** 5195 Bytes
- **SHA-256:** `8984b0a44d624c36a454f5979a1f1779478d7e2cd30164cddda1a78dee16bbb2`

## `list_bodies_1.json`

- **Werkzeuge:** `oparl_compare_bodies`, `oparl_get_votings`, `oparl_list_bodies`, `oparl_search_affairs`, `oparl_search_interests`, `oparl_search_meetings`, `oparl_search_persons`
- **Schluessel:** `https://api.openparldata.ch/v1/bodies/?indexed=true&limit=500`
- **Notiz:** Ungekuerzt: der Server sucht die Koerperschaft *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 217076 Bytes
- **SHA-256:** `de5101a503833da5516f7efbba95e6d6b07a040f164056b6403f6002e53dd2a6`

## `person_interests_1.json`

- **Werkzeuge:** `oparl_get_person_interests`
- **Schluessel:** `https://api.openparldata.ch/v1/persons/572/interests?limit=100`
- **Auswahl:** ungekuerzt
- **Groesse:** 481 Bytes
- **SHA-256:** `56bc1cf5a8be60ae4fd0356665129e7e03ecf19cdcba170bcf48c37e9fd1249d`

## `search_affairs_1.json`

- **Werkzeuge:** `oparl_search_affairs`
- **Schluessel:** `https://api.openparldata.ch/v1/affairs/?body_key=261&search=Klima&search_mode=partial&search_scope=metadata&sort_by=-begin_date&limit=3&offset=0`
- **Auswahl:** ungekuerzt
- **Groesse:** 7988 Bytes
- **SHA-256:** `fffd666308659beffb84f6a5d752eb13f2c382dec748346723a9af66278a55bc`

## `search_interests_1.json`

- **Werkzeuge:** `oparl_search_interests`
- **Schluessel:** `https://api.openparldata.ch/v1/interests/?body_key=261&limit=3&offset=0`
- **Auswahl:** ungekuerzt
- **Groesse:** 3968 Bytes
- **SHA-256:** `27747bed365919255fd3f68d1acd328b6d5bfa760f13f0fc0ec665e5211e03de`

## `search_meetings_1.json`

- **Werkzeuge:** `oparl_search_meetings`
- **Schluessel:** `https://api.openparldata.ch/v1/meetings/?body_key=261&sort_by=-begin_date&limit=3&offset=0`
- **Auswahl:** ungekuerzt
- **Groesse:** 5040 Bytes
- **SHA-256:** `dd76f9eb9ccaa0a513e9514af6fe548c4c204a4a87a9383d5fdae8c7aa426b86`

## `search_persons_1.json`

- **Werkzeuge:** `oparl_search_persons`
- **Schluessel:** `https://api.openparldata.ch/v1/persons/?body_key=261&limit=3&offset=0&sort_by=id`
- **Auswahl:** ungekuerzt
- **Groesse:** 8245 Bytes
- **SHA-256:** `eac56f3ba49698e75933ec3c255b5a5803304ca9a49f3fb4cde55e1f633c8091`

## `source_status_1.json`

- **Werkzeuge:** `oparl_source_status`
- **Schluessel:** `https://api.openparldata.ch/v1/bodies/?indexed=true&limit=1`
- **Auswahl:** ungekuerzt
- **Groesse:** 2784 Bytes
- **SHA-256:** `dde76e3af548c210db78def0a489b987bde99818810b7f52f76ab63e7f6c1076`

## `voting_results_1.json`

- **Werkzeuge:** `oparl_get_voting_results`
- **Schluessel:** `https://api.openparldata.ch/v1/votings/105130`
- **Notiz:** Ungekuerzt: der Server zaehlt die Stimmen *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 1406 Bytes
- **SHA-256:** `d6f29fbc22c2989499f4fe08ca18059b5fb3840dfc5e5c2a2f45e1a5ab2c3d31`

## `voting_results_2.json`

- **Werkzeuge:** `oparl_get_voting_results`
- **Schluessel:** `https://api.openparldata.ch/v1/votes/?voting_id=105130&limit=200&offset=0`
- **Notiz:** Ungekuerzt: der Server zaehlt die Stimmen *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server sucht oder zaehlt *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 120837 Bytes
- **SHA-256:** `2d2327a4902e4ac0a1fef35d2e86d0bac4448f78e7fc26dd407dcce2a55e72ff`
