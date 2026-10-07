"""Stufe 3 in einer echten (leeren) Test-Home.

Das Lagebild hört jede Zustandsänderung — auch ``unavailable``, auch den
ersten Zustand nach dem Start —, lernt KONTINUUMs eigene Sensoren nie und
meldet sich als Sensor ``sensor.kontinuum_lagebild``.

Mit einem Kern < 0.7 überspringt sich die Datei (mit Grund im Log): Dann
gibt es kein Lagebild, und die Manifest-Regel erlaubt den neuen Kern erst
mit dem bewussten Sprung auf >=0.7.0,<0.8.
"""

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kontinuum import lagebild
from custom_components.kontinuum.const import DOMAIN

pytestmark = pytest.mark.skipif(
    not lagebild.STUFE3, reason="kontinuum-core < 0.7: kein Lagebild, keine Börse")


@pytest.fixture
def entry(hass):
    """Ein leerer KONTINUUM-Entry — Presets auf Werkseinstellung."""
    mock = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    mock.add_to_hass(hass)
    return mock


@pytest.fixture
async def mit_benachrichtigungen(hass):
    """persistent_notification vor KONTINUUM laden (die Startmeldung ruft
    den Dienst; ohne Komponente scheitert die Aufgabe laut)."""
    assert await async_setup_component(hass, "persistent_notification", {})


@pytest.mark.asyncio
async def test_lagebild_hoert_auch_unavailable_und_den_ersten_zustand(
    hass, enable_custom_integrations, mit_benachrichtigungen, entry
):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    kortex = hass.data[DOMAIN]["association_cortex"]
    assert kortex is not None
    assert hass.states.get("sensor.kontinuum_lagebild") is not None

    # Der erste Zustand kommt ohne old_state — der übrige Pfad wirft ihn
    # weg, das Lagebild nicht.
    hass.states.async_set("person.test", "home")
    await hass.async_block_till_done()
    assert kortex.zustand.get("person.test") == "home"
    assert "person.test" in kortex.ziele

    hass.states.async_set("person.test", "unavailable")
    await hass.async_block_till_done()
    assert kortex.zustand.get("person.test") == "weg"


@pytest.mark.asyncio
async def test_eigene_sensoren_lernt_das_lagebild_nie(
    hass, enable_custom_integrations, mit_benachrichtigungen, entry
):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_set("person.test", "home")
    hass.states.async_set("person.test", "not_home")
    await hass.async_block_till_done()
    kortex = hass.data[DOMAIN]["association_cortex"]
    assert not any(lagebild.ist_eigene(e) for e in kortex.zustand)
