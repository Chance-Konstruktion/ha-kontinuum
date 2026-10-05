"""Tests für das WebSocket-Abonnement auf die Kontinuum-Entitäten
(Durchsicht 04.10., ha-kontinuum #1, Punkt 7).

Der Befund: das Dashboard holte alle 3 s ALLE Zustände über
``/api/states`` — je offenem Tab. Zwei offene Tabs hiessen 40 volle
Zustandslisten pro Minute auf dem Draht, damit ein Hirn-Panel seine
acht Sensoren zeichnen kann.

Beweisführung — vier Zeugen am echten Draht (echte Test-Home,
echter WebSocket-Server, echter Client):

1. ``test_abo_liefert_ersten_stand`` — das Abo schickt den vollen
   Stand als Startereignis; die REST-Ausgangsrunde entfällt.
2. ``test_fremde_entitaeten_reisen_nicht`` — das Herzstück von
   Punkt 7: eine Fremd-Entität (``light.kueche``) ändert sich — und
   auf dem Draht passiert NICHTS. Eine Kontinuum-Entität ändert sich
   — und EIN Ereignis reist.
3. ``test_registry_entitaeten_reisen_mit`` — wer seine Entität
   umbenennt (``sensor.vorhersage`` statt des Standard-Namens),
   bleibt erreicht: die Registry kennt die Plattform. Das Abschieds-
   ereignis (Entität entfernt) reist ebenfalls — der Cache im
   Dashboard kann ehrlich leeren.
4. ``test_abmeldung_raeumt_den_bus_ab`` — das Abonnement hinterlässt
   keinen Bus-Listener (Punkt 1 hat gelehrt, wie Lecks aussehen).

Dazu die Wächter am Dashboard selbst: der 3-Sekunden-Takt ist WEG,
die Datenschicht reist mit und wird installiert, und der Node-Zeuge
fährt die JS-Schicht unverändert (Handshake, Stand, Ruhepause,
Reconnect-Treppe, REST-Notausgang).
"""

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.kontinuum as kontinuum_init
from custom_components.kontinuum.const import DOMAIN

HTML = Path("custom_components/kontinuum/assets/kontinuum.html")
JS = Path("custom_components/kontinuum/assets/kontinuum-daten.js")
ABO_TYP = "kontinuum/abonniere"


@pytest.fixture
def entry(hass):
    """Ein leerer KONTINUUM-Entry — Presets auf Werkseinstellung."""
    mock = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    mock.add_to_hass(hass)
    return mock


@pytest.fixture
async def haushalt(hass, enable_custom_integrations, entry):
    """Die Test-Home mit laufender Integration — wie ein echtes Haus.

    persistent_notification muss zuerst laden (die Startup-Meldung
    ruft den Dienst als Aufgabe auf — sonst ist das Teardown-Gejammer
    Straßenlärm, nicht der Befund).
    """
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass


_NAECHSTE_FRAGE = [0]


async def _frage(client, befehl):
    """Stellt eine Frage mit steigender Nummer — der Draht verlangt das."""
    _NAECHSTE_FRAGE[0] += 1
    await client.send_json({"id": _NAECHSTE_FRAGE[0], **befehl})
    antwort = await client.receive_json()
    assert antwort["success"], antwort
    return antwort


async def _abonnieren(client):
    """Schliesst das Abonnement und gibt den Stand zurück.

    Eine Warmlauf-Runde (get_config) geht voraus: eine erste Antwort
    auf der Leitung — ohne sie blieb die erste echte Frage in dieser
    Werkstatt manchmal ungehört hängen (Beobachtung vom 05.10., die
    Runde ist billig und ehrlich: sie beweist nur, dass die Leitung
    lebt).
    """
    await _frage(client, {"type": "get_config"})
    _NAECHSTE_FRAGE[0] += 1  # die Abonnement-Nummer (Antwort via Ereignis)
    abo_nummer = _NAECHSTE_FRAGE[0]
    await client.send_json({"id": abo_nummer, "type": ABO_TYP})
    result = await client.receive_json()
    assert result["success"], result
    stand = await client.receive_json()
    assert stand["type"] == "event", stand
    assert stand["event"]["art"] == "stand", stand
    stand["abo_nummer"] = abo_nummer
    return stand


async def _ruhig(client, dauer=0.3):
    """Der Draht muss still sein — sonst ist die Behauptung wertlos."""
    with pytest.raises(asyncio.TimeoutError):
        await client.receive_json(timeout=dauer)


# ═════════════════════════════════════════════════════════════════
# Zeugen am echten Draht
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_abo_liefert_ersten_stand(hass, haushalt, hass_ws_client):
    """Das Startereignis trägt den vollen Stand — ohne REST-Runde."""
    hass.states.async_set("sensor.kontinuum_status", "aktiv")
    hass.states.async_set("sensor.kontinuum_prediction", "warten")
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    stand = await _abonnieren(client)
    zustaende = {z["entity_id"]: z for z in stand["event"]["zustaende"]}

    assert "sensor.kontinuum_status" in zustaende
    assert zustaende["sensor.kontinuum_status"]["state"] == "aktiv"
    assert "sensor.kontinuum_prediction" in zustaende


@pytest.mark.asyncio
async def test_fremde_entitaeten_reisen_nicht(hass, haushalt, hass_ws_client):
    """Das Herzstück von Punkt 7: auf dem Draht reisen nur unsere."""
    hass.states.async_set("sensor.kontinuum_status", "aktiv")
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    stand = await _abonnieren(client)
    abo_nummer = stand["abo_nummer"]

    # Eine Fremd-Entität ändert sich — der Draht bleibt still.
    hass.states.async_set("light.kueche", "on")
    hass.states.async_set("binary_sensor.fenster", "on")
    await hass.async_block_till_done()
    await _ruhig(client)

    # Eine Kontinuum-Entität ändert sich — EIN Ereignis reist.
    hass.states.async_set("sensor.kontinuum_status", "lernt")
    await hass.async_block_till_done()
    msg = await client.receive_json(timeout=2)
    assert msg["type"] == "event"
    assert msg["id"] == abo_nummer
    assert msg["event"]["art"] == "aenderung"
    assert msg["event"]["neu"]["state"] == "lernt"
    assert msg["event"]["entity_id"] == "sensor.kontinuum_status"

    await _ruhig(client)


@pytest.mark.asyncio
async def test_registry_entitaeten_reisen_mit(hass, haushalt, hass_ws_client):
    """Umbenannte Entitäten bleiben erreicht — und verabschieden sich."""
    registry = er.async_get(hass)
    eintrag = registry.async_get_or_create(
        "sensor", DOMAIN, "test-vorhersage", suggested_object_id="vorhersage"
    )
    assert eintrag.entity_id == "sensor.vorhersage"
    hass.states.async_set("sensor.vorhersage", "wohnzimmer")
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    stand = await _abonnieren(client)
    abo_nummer = stand["abo_nummer"]
    zustaende = {z["entity_id"] for z in stand["event"]["zustaende"]}
    assert "sensor.vorhersage" in zustaende

    # Änderung reist (kein Präfix — die Registry zeugt für uns).
    hass.states.async_set("sensor.vorhersage", "kueche")
    await hass.async_block_till_done()
    msg = await client.receive_json(timeout=2)
    assert msg["event"]["neu"]["state"] == "kueche"

    # Entfernen reist ebenso — der Cache darf ehrlich leeren.
    hass.states.async_remove("sensor.vorhersage")
    await hass.async_block_till_done()
    msg = await client.receive_json(timeout=2)
    assert msg["event"]["entity_id"] == "sensor.vorhersage"
    assert msg["event"]["neu"] is None

    await _ruhig(client)


@pytest.mark.asyncio
async def test_abmeldung_raeumt_den_bus_ab(hass, haushalt, hass_ws_client):
    """Abmelden hinterlässt keinen Listener — kein Leck (Punkt 1)."""
    basis = hass.bus.async_listeners().get(EVENT_STATE_CHANGED, 0)

    client = await hass_ws_client(hass)
    stand = await _abonnieren(client)
    await hass.async_block_till_done()
    assert hass.bus.async_listeners().get(EVENT_STATE_CHANGED, 0) == basis + 1

    _NAECHSTE_FRAGE[0] += 1
    frage = _NAECHSTE_FRAGE[0]
    await client.send_json(
        {"id": frage, "type": "unsubscribe_events", "subscription": stand["abo_nummer"]}
    )
    ergebnis = await client.receive_json()
    assert ergebnis["success"], ergebnis
    await hass.async_block_till_done()
    assert hass.bus.async_listeners().get(EVENT_STATE_CHANGED, 0) == basis


# ═════════════════════════════════════════════════════════════════
# Wächter am Dashboard
# ═════════════════════════════════════════════════════════════════


def test_dashboard_hat_keinen_takt_mehr():
    """Der 3-Sekunden-Takt ist weg — kein fetchSensors, kein Intervall."""
    html = HTML.read_text(encoding="utf-8")
    assert "fetchSensors" not in html, "das Dashboard pollt noch selbst"
    assert "POLL_INTERVAL = " not in html, "der Abfrage-Takt lebt noch"
    assert "setInterval(fetchSensors" not in html


def test_dashboard_traegt_die_datenschicht():
    """Die Datenschicht reist als eigene Datei und wird geladen."""
    html = HTML.read_text(encoding="utf-8")
    assert re.search(r'<script\s+src="kontinuum-daten\.js"', html), (
        "das Dashboard lädt die Datenschicht nicht"
    )
    assert JS.is_file()


def test_datenschicht_abonniert_und_behaelt_den_notausgang():
    """Das Abo ist das Mittel, REST bleibt ehrlicher Notausgang."""
    js = JS.read_text(encoding="utf-8")
    assert ABO_TYP in js, "die Schicht abonniert nicht"
    assert "/api/states" in js, "der REST-Notausgang fehlt"
    assert "KontinuumDatenSchicht" in js


@pytest.mark.asyncio
async def test_installation_legt_die_datenschicht_ab(
    hass, enable_custom_integrations, entry
):
    """Nach dem Setup liegt die Datenschicht neben dem Dashboard."""
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    www = Path(hass.config.config_dir) / "www"
    assert (www / "kontinuum.html").is_file()
    assert (www / "kontinuum-daten.js").is_file()


# ═════════════════════════════════════════════════════════════════
# Der Node-Zeuge — die JS-Schicht unverändert gefahren
# ═════════════════════════════════════════════════════════════════


def test_js_datenschicht_laeuft_unter_node():
    """Node fährt die Schicht: Handshake, Stand, Ruhe, Treppe, Notausgang.

    Die CI installiert Node ausdrücklich für Tests, die ihn brauchen
    (siehe .gitlab-ci.yml) — ohne Node überspringt dieser Zeuge sich
    ehrlich mit Grund.
    """
    if shutil.which("node") is None:
        pytest.skip("Node ist nicht installiert — der JS-Zeuge kann nicht fahren")
    harness = Path(__file__).parent / "js" / "daten_schicht_pruefung.js"
    lauf = subprocess.run(
        ["node", str(harness)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert lauf.returncode == 0, (
        f"der Node-Zeuge fiel:\n{lauf.stdout}\n{lauf.stderr}"
    )
    zeugnis = [z for z in lauf.stdout.splitlines() if z.startswith("ZEUGNIS")]
    assert zeugnis, f"kein Zeugnis in der Ausgabe:\n{lauf.stdout}"
    daten = json.loads(zeugnis[-1][len("ZEUGNIS "):])
    assert daten["fehler"] == 0, lauf.stdout
    assert daten["pruefungen"] >= 15, (
        f"zu wenige Prüfungen gefahren: {daten['pruefungen']}"
    )
