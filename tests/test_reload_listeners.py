"""Tests für das Listener-Leck beim Neuladen (Durchsicht 04.10., Punkt 1).

Der Befund (ha-kontinuum #1): ``__init__.py`` warf die Abmeldefunktion
von ``hass.bus.async_listen(EVENT_STATE_CHANGED, …)`` und von
``async_listen_once(EVENT_HOMEASSISTANT_STOP, …)`` weg. Jede Options-
änderung lädt den Entry neu (config_flow). Danach liefen zwei Listener
parallel, und beim Stopp schrieben beide ``on_shutdown`` dieselbe
``brain.json.gz`` — wer zuletzt fertig wurde, gewann, notfalls das
veraltete Gehirn.

Beweisführung wie von Claudes Auftrag verlangt: setup → unload →
setup, und danach zählt der Bus für STATE_CHANGED genau EINEN
Listener mehr als vorher (vor dem Fix waren es zwei). Für
HOMEASSISTANT_STOP ist der absolute Zähler nicht allein unserer:
die Entity-Plattformen von Home Assistant melden eigene Stop-Listener
am selben Entry an — sie reisen mit dem Entry mit und sind kein Leck.
Deshalb zählt der Test dort die Invariante: nach dem Entladen ist der
Bestand wieder der Grundstand, und nach dem erneuten Setup ist er
genau der Stand des ersten Setups — kein Wachstum über den Zyklus.
Der zweite Test wiegt das zweite genanntes Leck direkt: nach einem
Neuladen darf EVENT_HOMEASSISTANT_STOP nur EIN on_shutdown auslösen.

Alle Tests laufen gegen eine echte (leere) Test-Home — keine
Hausdaten, keine Attrappen nötig.
"""

import pytest
from homeassistant.core import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.kontinuum as kontinuum_init
from custom_components.kontinuum.const import DOMAIN


def _zaehler(hass, event_type) -> int:
    """Zählt die registrierten Listener eines Events — über die
    dokumentierte Bus-Methode, nicht über Interna."""
    return hass.bus.async_listeners().get(event_type, 0)


@pytest.fixture
def entry(hass):
    """Ein leerer KONTINUUM-Entry — Presets auf Werkseinstellung."""
    mock = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    mock.add_to_hass(hass)
    return mock


@pytest.fixture
async def mit_benachrichtigungen(hass):
    """persistent_notification laden, bevor KONTINUUM startet.

    Die Startup-Meldung der Integration ruft den Dienst als Aufgabe
    auf. Ohne geladene Komponente scheitert diese Aufgabe laut — der
    Test-Home-Teardown hebt das dann als Fehler hoch. Das ist Straßen-
    lärm, nicht der Befund.
    """
    assert await async_setup_component(hass, "persistent_notification", {})


@pytest.mark.asyncio
async def test_reload_meldet_beide_bus_listener_ab(
    hass, enable_custom_integrations, mit_benachrichtigungen, entry
):
    """Setup → Entladen → Setup: danach genau EIN Listener je Event."""
    basis_state = _zaehler(hass, EVENT_STATE_CHANGED)
    basis_stop = _zaehler(hass, EVENT_HOMEASSISTANT_STOP)

    # 1. Setup: der Lern-Pfad (STATE_CHANGED) ist eindeutig unserer —
    #    niemand sonst hört in der Test-Home darauf.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _zaehler(hass, EVENT_STATE_CHANGED) == basis_state + 1
    stand_stop = _zaehler(hass, EVENT_HOMEASSISTANT_STOP)
    assert stand_stop > basis_stop

    # 2. Entladen: der Lern-Pfad ist wieder auf dem Grundstand — hier
    #    hing früher das Leck (unser STATE_CHANGED-Listener blieb stehen,
    #    das entladene Gehirn lernte weiter).
    #    Für STOP gilt: der Zähler SINKT (unser on_shutdown ist abgemeldet).
    #    Die restlichen Stop-Listener gehören Home Assistant selbst
    #    (EntityComponent-Verabschiedungen der geladenen Plattformen) —
    #    sie leben mit der Instanz, nicht mit dem Entry, und sind kein
    #    Leck. Ihr genauer Bestand ist Versionssache; deshalb zählt der
    #    Test STOP über den Zyklus wachstumsfrei (Schritt 3).
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert _zaehler(hass, EVENT_STATE_CHANGED) == basis_state
    assert _zaehler(hass, EVENT_HOMEASSISTANT_STOP) < stand_stop

    # 3. Erneutes Setup: STATE_CHANGED wieder genau EINEN mehr (nicht
    #    zwei — das war das Leck), und STOP genau auf dem Stand des
    #    ersten Setups — über den Neulade-Zyklus wächst nichts.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _zaehler(hass, EVENT_STATE_CHANGED) == basis_state + 1
    assert _zaehler(hass, EVENT_HOMEASSISTANT_STOP) == stand_stop


@pytest.mark.asyncio
async def test_stopp_schreibt_nur_das_aktuelle_gehirn(
    hass, enable_custom_integrations, mit_benachrichtigungen, entry, monkeypatch
):
    """Nach einem Neuladen löst EVENT_HOMEASSISTANT_STOP nur EIN Speichern aus.

    Vor dem Fix schrieben das alte und das neue on_shutdown beide die
    selbe brain.json.gz — zwei Gehirne, eine Datei, das Rennen entscheidet.
    """
    # _save_brain mitzählen (der Aufruf läuft über den Modulnamen,
    # deshalb greift die Ersetzung).
    schreibungen = []
    original = kontinuum_init._save_brain

    def _zaehl_speicherung(brain, path):
        schreibungen.append(id(brain))
        return original(brain, path)

    monkeypatch.setattr(kontinuum_init, "_save_brain", _zaehl_speicherung)

    # Setup → Entladen → Setup: der Neulade-Unfall aus dem Ticket.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    schreibungen.clear()

    # Der Stopp: nur das AKTUELLE Gehirn darf sich verabschieden.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert len(schreibungen) == 1
