"""Werkstatt-Gerüst für die KONTINUUM-Testsuite.

Eine Wahrheit, die jeden ersten Test der WS-Werkstatt traf (05.10.,
Flug 2629): ``aiodns``/``pycares`` startet beim ersten zerstörten
DNS-Kanal einen Daemon-Thread ``_run_safe_shutdown_loop``, der ewig
auf weitere Kanäle wartet — er läuft bis zum Prozessende und ist
beabsichtigt (Kanäle werden dort geordnet zerstört, damit die C-Bibli-
othek nicht unter laufenden Abfragen abgerissen wird).

Der Teardown-Wächter von pytest-homeassistant-custom-component
vergleicht die Threads JE TEST gegen den Bestand bei seinem Start:
der Daemon fällt also nur dem ALLERERSTEN Test auf und färbt ihn rot
— ganz zu Unrecht, der Thread gehört zur Werkstatt, nicht zum
Test. Wir lassen ihn daher vor dem ersten Test entstehen (ein Kanal
wird geboren und begraben, der Daemon erwacht); ab dann steht er in
jeder Baseline und stört niemanden mehr.
"""

import gc
import threading

import asyncio
import pytest


@pytest.fixture(scope="session", autouse=True)
def _pycares_daemon_vorweg():
    """Lässt den pycares-Daemon VOR dem ersten Test erwachen.

    Ohne diesen Vorweg: ``AssertionError`` im Teardown des ersten
    Web-Socket-Tests (``_run_safe_shutdown_loop`` ist kein
    ``_DummyThread``). Mit ihm: Stille — der Thread steht in jeder
    Bestandsaufnahme.
    """
    try:
        import aiodns
    except ImportError:  # pragma: no cover — aiodns gehört zum Test-Gerüst
        return
    # Ein eigener, nie laufender Loop: der Resolver braucht einen zum
    # Anlegen, laufen soll er nicht (kein Deprecations-Gejamper über
    # fehlende aktuelle Schleifen, kein Netzverkehr).
    loop = asyncio.new_event_loop()
    try:
        resolver = aiodns.DNSResolver(loop=loop)
        del resolver
    finally:
        loop.close()
    gc.collect()
    assert any(
        "_run_safe_shutdown_loop" in (t.name or "") for t in threading.enumerate()
    ), "der pycares-Daemon ist nicht erwacht — die Werkstatt hat sich geändert"
