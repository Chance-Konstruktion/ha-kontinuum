"""Tests für Punkt 8 der Durchsicht 04.10.: der Cortex-Nachhall liest erst
NACH den Selbst- und Ignore-Filtern.

Der Befund (ha-kontinuum #1): ``brain["cortex"].nachhall.beobachte(...)``
lief für JEDE Zustandsänderung — auch für die eigenen ``sensor.kontinuum_*``
Sensoren und für mit ``ignore_kontinuum`` markierte Entitäten. Der Nachhall
sollte das Ergebnis von Beratungen gegen die Handlungen der BEWOHNER
messen, nicht gegen das Echo der eigenen Sensoren oder gegen Geräte, die
das Haus ausdrücklich stumm gestellt hat.

Der Beweis: das echte KONTINUUM Setup fahren, das Gehirn bekommt einen
aufzeichnenden Cortex-Standort, und dann sprechen drei Quellen: ein
normaler Sensor (wird gehört), ein Kontinuum-Eigener (schweigt), ein
ignorierter (schweigt).
"""

import pytest
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import State
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kontinuum.const import DOMAIN


class NachhallAufzeichner:
    """Steht für Cortex; nur der Nachhall ist im State-Changed-Pfad lebendig."""

    class Nachhall:
        def __init__(self, rufe):
            self._rufe = rufe

        def beobachte(self, entity_id, new_state, zeit):
            self._rufe.append((entity_id, new_state))

    def __init__(self):
        self.rufe = []
        self.nachhall = self.Nachhall(self.rufe)


@pytest.fixture
def entry(hass):
    mock = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    mock.add_to_hass(hass)
    return mock


@pytest.fixture
async def mit_benachrichtigungen(hass):
    assert await async_setup_component(hass, "persistent_notification", {})
    await hass.async_block_till_done()


def _aendere(hass, entity_id, zustand):
    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": entity_id,
            "old_state": State(entity_id, "alt"),
            "new_state": State(entity_id, zustand),
        },
    )


@pytest.mark.asyncio
async def test_nachhall_hoert_bewohner_nicht_eigenes_echo(
    hass, enable_custom_integrations, mit_benachrichtigungen, entry
):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    brain = hass.data[DOMAIN]
    aufzeichner = NachhallAufzeichner()
    brain["cortex"] = aufzeichner

    # 1. Ein normaler Sensor: gehört.
    _aendere(hass, "sensor.wohnzimmer_temperatur", "21.5")
    await hass.async_block_till_done()
    assert aufzeichner.rufe == [("sensor.wohnzimmer_temperatur", "21.5")]

    # 2. Ein KONTINUUM-eigener Sensor: das eigene Echo — schweigt.
    _aendere(hass, "sensor.kontinuum_vorhersage", "wohnzimmer")
    await hass.async_block_till_done()
    assert aufzeichner.rufe == [("sensor.wohnzimmer_temperatur", "21.5")]


@pytest.mark.asyncio
async def test_nachhall_hoert_ignorierte_entitaeten_nicht(
    hass, enable_custom_integrations, mit_benachrichtigungen, entry
):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    brain = hass.data[DOMAIN]
    aufzeichner = NachhallAufzeichner()
    brain["cortex"] = aufzeichner
    brain["thalamus"]._ignored_entities.add("sensor.keller_alarm")

    _aendere(hass, "sensor.keller_alarm", "an")
    await hass.async_block_till_done()
    assert aufzeichner.rufe == []
