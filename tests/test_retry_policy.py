"""Retry-Politik gegenüber Curia Vista (ARCH-014): Retry-After, Jitter, Budget.

Eigenes Modul statt einer Ergänzung von ``test_transcripts.py``: Ein Test über
*Wartezeiten* soll nicht neben Tests stehen, die ``_BACKOFF_BASE`` auf 0 setzen,
um Wartezeit loszuwerden.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx

from parlament_mcp import transcripts as tx

URL = f"{tx.ODATA_BASE}/Transcript"


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers, request=httpx.Request("GET", URL))


class TestParseRetryAfter:
    def test_delta_seconds(self):
        assert tx.parse_retry_after(_resp(429, "120")) == 120.0

    def test_http_date_in_the_future(self):
        when = datetime.now(UTC) + timedelta(seconds=90)
        got = tx.parse_retry_after(_resp(503, format_datetime(when, usegmt=True)))
        assert got is not None
        assert 80 <= got <= 95  # Header hat Sekundenauflösung

    def test_http_date_in_the_past_means_now(self):
        when = datetime.now(UTC) - timedelta(hours=1)
        assert tx.parse_retry_after(_resp(503, format_datetime(when, usegmt=True))) == 0.0

    def test_absent_header(self):
        assert tx.parse_retry_after(_resp(429)) is None

    def test_malformed_header_does_not_raise(self):
        # Eine kaputte Kopfzeile darf auf dem Fehlerpfad nicht zum Absturz werden.
        assert tx.parse_retry_after(_resp(429, "next Tuesday")) is None
        assert tx.parse_retry_after(_resp(429, "")) is None
        assert tx.parse_retry_after(_resp(429, "-5")) is None

    def test_ignored_on_other_statuses(self):
        assert tx.parse_retry_after(_resp(500, "30")) is None

    def test_no_response_at_all(self):
        # Timeouts und Verbindungsfehler tragen kein Response-Objekt.
        assert tx.parse_retry_after(None) is None


class TestRetryDelay:
    def test_retry_after_beats_the_exponential_curve(self):
        # Der gehintete Wert liegt ausserhalb der Reichweite der Kurve: Versuch 1
        # spannt [1, 3] s, eine Wartezeit um 9 kann nur aus dem Header stammen.
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "9"))
        assert 9.0 <= tx.retry_delay(1, exc) <= 9.0 * (1 + tx.RETRY_AFTER_JITTER)

    def test_retry_after_is_never_undercut(self):
        """Einseitige Streuung: später ist höflich, früher missachtet den Wert."""
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "5"))
        for _ in range(50):
            assert tx.retry_delay(1, exc) >= 5.0

    def test_absurd_retry_after_is_capped(self):
        # Exakt der Deckel, nicht "der Deckel mal Jitter": Gedeckelt wird nach
        # dem Jittern, sonst wäre MAX_DELAY_S keine Grenze (Codex-Review zu
        # PR #35). Die Gleichheit diskriminiert weiterhin — die nackte Kurve
        # ergäbe hier 2 s.
        exc = httpx.HTTPStatusError("503", request=None, response=_resp(503, "86400"))
        assert tx.retry_delay(1, exc) == tx.MAX_DELAY_S

    def test_exponential_ladder_is_capped(self):
        # 2**10 = 1024 s ohne Deckel; gejittert bis 1536 s, wenn erst gedeckelt
        # und dann gestreut würde.
        for _ in range(30):
            assert tx.retry_delay(10, None) <= tx.MAX_DELAY_S

    def test_the_cap_is_a_real_bound_not_a_midpoint(self):
        """MAX_DELAY_S muss halten, auch wenn der Jitter nach oben ausschlägt.

        Zuvor wurde erst gedeckelt und dann multipliziert: Ein 20-s-Deckel liess
        exponentielle Wartezeiten bis 30 s und ``Retry-After``-Wartezeiten bis
        25 s zu. Die Konstante behauptete eine Schranke, die sie nicht einhielt.
        """
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "86400"))
        for attempt in range(1, 12):
            assert tx.retry_delay(attempt, None) <= tx.MAX_DELAY_S
            assert tx.retry_delay(attempt, exc) <= tx.MAX_DELAY_S

    def test_delay_is_spread(self):
        """Ohne Jitter wiederholen alle Clients im Gleichtakt. Ziehungen müssen streuen."""
        draws = {tx.retry_delay(2, None) for _ in range(30)}
        assert len(draws) > 1, "Wartezeit ist deterministisch — Jitter fehlt"
        base = tx._BACKOFF_BASE**2
        assert all(
            base * (1 - tx.JITTER_SPREAD) <= d <= base * (1 + tx.JITTER_SPREAD) for d in draws
        )


@pytest.fixture
def fake_clock(monkeypatch):
    """Uhr, die nur vorrückt, wenn der Client schläft.

    Ohne sie kann das Budget im Test nie ablaufen: Ausgepatchter Schlaf
    verbraucht keine Wanduhr, ``time.monotonic()`` bewegt sich nicht, und jede
    Deadline hielte ewig. Der Test wäre grün, egal was die Budget-Logik tut.
    """
    now = {"t": 1000.0}
    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)
        now["t"] += seconds

    monkeypatch.setattr(tx.time, "monotonic", lambda: now["t"])
    monkeypatch.setattr(tx, "_sleep", _sleep)
    return slept


@respx.mock
async def test_retry_after_reaches_the_sleep(fake_clock):
    """Der Wert der Quelle muss bei asyncio.sleep ankommen, nicht die Kurve."""
    respx.get(URL).mock(side_effect=[_resp(429, "7"), httpx.Response(200, json={"value": []})])
    async with httpx.AsyncClient() as http:
        await tx._fetch(http, URL, {})
    assert len(fake_clock) == 1
    assert 7.0 <= fake_clock[0] <= 7.0 * (1 + tx.RETRY_AFTER_JITTER)


@respx.mock
async def test_404_still_fails_fast_without_waiting(fake_clock):
    """4xx ausser 429 ist eine Aussage über die Anfrage, nicht über den Moment."""
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as http:
        with pytest.raises(httpx.HTTPStatusError):
            await tx._fetch(http, URL, {})
    assert route.call_count == 1
    assert fake_clock == []


@respx.mock
async def test_budget_cuts_the_ladder_short(fake_clock):
    """Weniger als _MAX_ATTEMPTS Requests, sobald die Wartezeiten das Budget überdauern."""
    route = respx.get(URL).mock(side_effect=httpx.ConnectTimeout(""))
    async with httpx.AsyncClient() as http:
        with pytest.raises(httpx.ConnectTimeout):
            await tx._fetch(http, URL, {}, total_budget=3.0)
    assert route.call_count < tx._MAX_ATTEMPTS, "Budget hat die Leiter nicht begrenzt"
    assert route.call_count >= 1, "Der erste Versuch muss immer hinausgehen"


@respx.mock
async def test_full_ladder_runs_when_the_budget_allows(fake_clock):
    """Gegenrichtung: Ein weites Budget darf nichts abschneiden."""
    route = respx.get(URL).mock(side_effect=httpx.ConnectTimeout(""))
    async with httpx.AsyncClient() as http:
        with pytest.raises(httpx.ConnectTimeout):
            await tx._fetch(http, URL, {}, total_budget=600.0)
    assert route.call_count == tx._MAX_ATTEMPTS


@respx.mock
async def test_per_request_timeout_is_clamped_to_the_remaining_budget(fake_clock):
    """Ein einzelner Read bekommt nie mehr Zeit, als das Budget noch hergibt."""
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"value": []}))
    async with httpx.AsyncClient() as http:
        await tx._fetch(http, URL, {}, total_budget=4.0)
    sent = route.calls.last.request.extensions["timeout"]
    assert sent["read"] == pytest.approx(4.0), sent


def test_budget_deliberately_exceeds_the_mcp_client_default():
    """Curia Vista ist eine dokumentierte Ausnahme — als Entscheidung festhalten.

    Schwester-Server mit festen Dumps halten ihr Budget *unter*
    ``MCP_DEFAULT_TIMEOUT``, damit der Aufrufer noch zuhört. Hier binden
    unvorgefilterte Volltextsuchen mit bis zu ~40 s; ein Budget unter 30 s würde
    legitime Suchen abwürgen, die heute durchkommen.

    Geprüft wird die Abweichung, nicht die Konformität: So bleibt sie eine
    Entscheidung auf dem Papier, und eine spätere stille Verengung scheitert laut.
    """
    from mcp.shared._httpx_utils import MCP_DEFAULT_TIMEOUT

    assert tx.TOTAL_BUDGET_S > MCP_DEFAULT_TIMEOUT
    assert tx.TOTAL_BUDGET_S == tx.TRANSCRIPT_TIMEOUT


@respx.mock
async def test_a_slow_response_is_cut_by_the_wall_clock_deadline():
    """Das Budget muss auch greifen, wenn httpx' Timeout nicht anschlägt.

    Codex-Review zu PR #35: httpx wendet sein Timeout pro Operation an, und das
    Read-Timeout beginnt mit jedem Chunk von vorn — eine langsam tröpfelnde
    Antwort kann das Gesamtbudget also überdauern, obwohl kein einzelner Read
    ablief. Deshalb liegt eine echte ``asyncio.timeout``-Deadline um den Request.

    Bewusst ohne ``fake_clock``: Diese Zusicherung hängt an echter Zeit, und eine
    Uhr, die nur beim Schlafen vorrückt, könnte sie nicht widerlegen.
    """
    import asyncio as real_asyncio
    import time

    async def _slow(request):
        await real_asyncio.sleep(1.0)
        return httpx.Response(200, json={"value": []})

    respx.get(URL).mock(side_effect=_slow)
    started = time.monotonic()
    async with httpx.AsyncClient() as http:
        with pytest.raises(TimeoutError):
            await tx._fetch(http, URL, {}, total_budget=0.05)
    elapsed = time.monotonic() - started
    # Die Zusicherung ist die Zeit, nicht der Zähler: respx verbucht den Aufruf
    # gar nicht mehr, weil die Deadline ihn mitten im Flug abbricht — genau das
    # ist der Beleg. Ohne die Deadline liefe die Antwort ihre volle Sekunde.
    assert elapsed < 0.5, f"Deadline hat nicht geschnitten: {elapsed:.2f}s"


# --- Die Naht, und warum sie nicht `asyncio.sleep` ist -----------------------


def test_der_retry_geht_ueber_den_alias():
    """Sonst patchen die Tests eine Naht, die der Code gar nicht benutzt.

    Umgeht das Modul den Alias, bleibt der Patch wirkungslos und die Suite
    wartet die echte Backoff-Leiter ab. Kein Test faellt dabei — sie wird nur
    um ein Vielfaches langsamer, und eine laengere Laufzeit ist kein Signal,
    das jemand liest. Diese Zusicherung macht daraus einen Fehlschlag.
    """
    quelle = inspect.getsource(tx)
    assert "await _sleep(" in quelle, "der Retry ruft den Modul-Alias nicht mehr auf"
    assert "await asyncio.sleep(" not in quelle, "der Retry umgeht den Alias"
