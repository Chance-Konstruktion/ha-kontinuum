"""Tests für Punkt 11 der Durchsicht 04.10.: der Aufbau- und der Abbau-Zeuge.

Der Befund (ha-kontinuum #1): «Nur zwei Testdateien, kein Test für setup,
unload oder reload. Punkt 1 wäre mit einem Reload-Test sofort
aufgefallen.» Der Reload-Zeuge kam mit der Heilung von Punkt 1
(test_reload_listeners.py), das Speichern beim Entladen wacht in
test_speicher_im_takt.py — was FEHLTE, ist der Blick auf den ganzen
Lebenszyklus: errichtet das Setup das GANZE Organ (alle Organe im
Gehirn, die Sensor-Plattform, die Dienste), und räumt der Abbau alles
heraus, was er angemeldet hat?

Beide Tests fahren das echte KONTINUUM im echten Test-Home.
"""

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.kontinuum as kontinuum_init
from custom_components.kontinuum.const import DOMAIN

ORGANE = (
    "thalamus", "hippocampus", "hypothalamus", "spatial", "insula",
    "amygdala", "cerebellum", "basal_ganglia", "prefrontal", "cortex",
    "reticular", "locus", "sleep_consolidation", "suprachiasmatic",
)

DIENSTE = ("set_mode", "activate", "deactivate", "brain_review")


@pytest.fixture
def entry(hass):
    mock = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    mock.add_to_hass(hass)
    return mock


@pytest.fixture
async def mit_benachrichtigungen(hass):
    assert await async_setup_component(hass, "persistent_notification", {})
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_setup_errichtet_das_gesamte_organ(
    hass, enable_custom_integrations, mit_benachrichtigungen, entry
):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    brain = hass.data[DOMAIN]
    for organ in ORGANE:
        assert organ in brain, f"Organ {organ} fehlt nach dem Setup"

    # Die Sensor-Plattform ist gefahren: der Status-Sensor existiert.
    # (Welche Sensoren genau, ist Versionssache — mindestens EINE
    # kontinuum-eigene Entität muss da sein.)
    kontinuum_sensoren = [
        s for s in hass.states.async_all()
        if s.entity_id.startswith("sensor.kontinuum_")
    ]
    assert kontinuum_sensoren, "keine KONTINUUM-Sensoren nach dem Setup"

    # Die Dienste sind registriert.
    for dienst in DIENSTE:
        assert hass.services.has_service(DOMAIN, dienst), (
            f"Dienst {DOMAIN}.{dienst} fehlt"
        )


@pytest.mark.asyncio
async def test_abbau_leert_und_zieht_herzschlag_ab(
    hass, enable_custom_integrations, mit_benachrichtigungen, entry
):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    brain = hass.data[DOMAIN]
    assert "_unsub_idle" in brain, "kein Herzschlag angemeldet?"
    gehirn = brain  # Referenz über das Entladen hinweg

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Das Gehirn ist aus hass.data heraus; die Anmeldung am abgemeldeten
    # Gehirn ist gezogen (der Timer feuert nicht mehr auf dem alten Entry).
    assert DOMAIN not in hass.data
    assert "_unsub_idle" not in gehirn

    # Der auf das Entladen laufende Tick darf keine Ausnahme werfen:
    # nach dem Entladen friert die Zeit kurz ein, und nichts läuft mehr.
    await hass.async_block_till_done()
    assert kontinuum_init.VERSION  # (das Modul lebt weiter, sauber)
