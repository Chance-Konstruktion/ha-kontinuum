"""Zeugen für ha-kontinuum #2 — der Entry reist im Options-Flow mit.

Der Befund (Kimi, 06.10.): KontinuumOptionsFlow las self.config_entry,
obwohl Home Assistant das erst ab 2024.11 selbst setzt — auf 2024.1 bis
2024.10 starb der Options-Flow mit AttributeError. hacs.json verspricht
aber 2024.1.0.

Die Heilung: async_get_options_flow reicht den Entry in den Konstruktor
weiter, die Property `eintrag` zieht ihn vor — auf jeder Fassung. Die
Zeugen hier fahen den HA-vor-2024.11-Zustand NACH (die Property
`config_entry` am Flow erhebt sich als AttributeError), denn die
Test-Umgebung selbst trägt ein modernes HA.
"""

import pytest

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kontinuum.config_flow import (
    KontinuumConfigFlow,
    KontinuumOptionsFlow,
)
from custom_components.kontinuum.const import DOMAIN


@pytest.fixture
def entry(hass):
    """Ein KONTINUUM-Entry — mit Agenten und Preset, wie der Flow ihn liest."""
    mock = MockConfigEntry(
        domain=DOMAIN, title="KONTINUUM",
        data={
            "enable_cortex": True,
            "preset": "ausgeglichen",
            "cortex_agents": {
                "1": {
                    "name": "comfort", "provider": "openai",
                    "model": "gpt-4o-mini",
                    "url": "https://api.openai.com/v1",
                    "system_prompt": "du bist comfort",
                },
            },
        },
    )
    mock.add_to_hass(hass)
    return mock


class _Vor2024_11(KontinuumOptionsFlow):
    """HA vor 2024.11, ehrlich nachgebaut.

    OptionsFlow.config_entry existierte dort schlicht nicht — jedes
    Lesen war der AttributeError aus ha-kontinuum #2.
    """

    @property
    def config_entry(self):
        raise AttributeError(
            "OptionsFlow.config_entry gibt es vor HA 2024.11 nicht "
            "(ha-kontinuum #2 — der alte Zustand)"
        )


@pytest.mark.asyncio
async def test_fabrik_reicht_den_entry_weiter(hass, entry):
    """async_get_options_flow baut den Flow MIT Entry — nicht leer."""
    flow = KontinuumConfigFlow.async_get_options_flow(entry)
    assert isinstance(flow, KontinuumOptionsFlow)
    assert flow.eintrag is entry


@pytest.mark.asyncio
async def test_altes_ha_menue_ohne_attributeerror(hass, entry):
    """Vor 2024.11 stand der erste Schritt schon im Feuer.

    async_step_init las self.config_entry.data — genau dort starb der
    Flow auf alten Fassungen. Mit dem mitgereisten Entry öffnet sich
    das Menü, die Daten kommen aus dem Entry.
    """
    flow = _Vor2024_11(entry)
    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    assert flow._data == dict(entry.data)


@pytest.mark.asyncio
async def test_ohne_entry_bleibt_es_der_alte_zustand(hass, entry):
    """Der GEGENBEWEIS: ohne mitgereisten Entry gibt es nichts zu holen.

    Nur so ist die Simulation ehrlich — auf vor-2024.11 ohne Entry
    bleibt der AttributeError (der Ursprungszustand von #2). Die
    Fabrik übergibt den Entry IMMER, dieser Fall bleibt der
    defensive Rückfall auf modernem HA.
    """
    flow = _Vor2024_11(None)
    with pytest.raises(AttributeError):
        _ = flow.eintrag


@pytest.mark.asyncio
async def test_modernes_ha_property_als_rueckfall(hass, entry):
    """Auf modernem HA (>= 2024.11) bleibt die Property der Rueckfall.

    Die Property dort heisst config_entry — ihr Inneres (Backing-
    Attribut oder _config_entry_id-Aufloesung) wechselt je Fassung,
    darum steht sie hier als einfache Property: geprueft wird der
    VERTRAG — ohne mitgereisten Entry fragt `eintrag` die Property.
    """

    class _Nach2024_11(KontinuumOptionsFlow):
        @property
        def config_entry(self):
            return entry

    flow = _Nach2024_11()
    assert flow.eintrag is entry


@pytest.mark.asyncio
async def test_manager_weg_laeuft_weiter(hass, enable_custom_integrations, entry):
    """Der volle Strassenweg über den Flow-Manager bleibt heil.

    Der Manager ruft async_get_options_flow(entry) — seit der Heilung
    reist der Entry mit, das Menue oeffnet sich auf der oeffentlichen
    Strasse (kein Griff in Flow-Interna).
    """
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
