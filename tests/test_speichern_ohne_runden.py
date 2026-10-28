"""Zeugen: der Options-Flow schreibt discussion_rounds nicht mehr neu,
und Klima-Alias-Zustaende gelten als Erfolg."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kontinuum import _states_match
from custom_components.kontinuum.config_flow import KontinuumOptionsFlow
from custom_components.kontinuum.const import DOMAIN


async def _speichern(hass, daten):
    eintrag = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data=daten)
    eintrag.add_to_hass(hass)
    flow = KontinuumOptionsFlow(eintrag)
    flow.hass = hass
    flow._data = dict(eintrag.data)
    with patch.object(hass.config_entries, "async_reload", AsyncMock()):
        await flow._save_and_finish()
    return eintrag


@pytest.mark.asyncio
async def test_neuer_eintrag_bekommt_keine_runden(hass):
    eintrag = await _speichern(hass, {"preset": "ausgeglichen"})
    assert "discussion_rounds" not in eintrag.data


@pytest.mark.asyncio
async def test_alter_eintrag_behaelt_seinen_schluessel(hass):
    eintrag = await _speichern(hass, {"preset": "ausgeglichen", "discussion_rounds": 3})
    assert eintrag.data["discussion_rounds"] == 3


@pytest.mark.parametrize("wunsch,ist", [
    ("heat", "heating"), ("cool", "cooling"), ("dry", "drying"),
    ("fan_only", "fan"),
])
def test_klima_alias_zustaende_passen(wunsch, ist):
    assert _states_match("climate.x", wunsch, ist)


def test_klima_alias_gilt_nur_im_passenden_wunsch():
    assert not _states_match("climate.x", "heat", "cooling")
    assert not _states_match("light.x", "heat", "heating")
