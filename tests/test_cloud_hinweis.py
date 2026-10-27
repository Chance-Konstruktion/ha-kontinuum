"""Tests für Punkt 5 der Durchsicht 04.10.: der Cloud-Hinweis im Flow.

Der Befund (ha-kontinuum #1): Cortex mit Cloud-Anbieter (OpenAI, Anthropic,
Gemini, Grok) schickt den Hauskontext nach außen; der Config-Flow sagte das
nirgends, und es fehlte die Übersicht, WELCHE Felder reisen. Standard ist
Ollama lokal — das bleibt unangetastet und ohne Zwischenschritt.

Die Heilung: wer im Agent-Setup einen Cloud-Anbieter wählt, landet zuerst
auf dem Schritt ``cloud_hinweis`` — deutlicher Hinweis plus Feldübersicht
(dieselbe Liste, die der Code unter CLOUD_FELDER führt) — und bestätigt
bewusst. Nein führt zurück ins Setup, Ja zur Modell-Wahl.

Alle Tests fahren den echten Options-Flow im echten Test-Home.
"""

import pytest
from unittest.mock import patch
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kontinuum.config_flow import CLOUD_FELDER
from custom_components.kontinuum.const import DOMAIN


@pytest.fixture
def entry(hass):
    mock = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    mock.add_to_hass(hass)
    return mock


async def _bis_agent_setup(hass, entry):
    """Options-Flow öffnen: Menü → Cortex → Übersicht → Agent 1 bearbeiten."""
    assert await async_setup_component(hass, "persistent_notification", {})
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "cortex"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"enable_cortex": True, "sequential_mode": False},
    )
    assert result["step_id"] == "agents_overview"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "add"},
    )
    assert result["step_id"] == "agent_setup"
    return result["flow_id"]


@pytest.mark.asyncio
async def test_cloud_anbieter_fragt_erst(hass, enable_custom_integrations, entry):
    """OpenAI gewählt → zuerst der Cloud-Hinweis, NICHT das Modell-Formular."""
    flow_id = await _bis_agent_setup(hass, entry)
    result = await hass.config_entries.options.async_configure(
        flow_id,
        user_input={"role": "comfort", "provider": "openai",
                    "url": "https://api.openai.com/v1"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cloud_hinweis"
    # Die Feldübersicht reist mit und nennt die heiklen Felder beim Namen.
    platzhalter = result["description_placeholders"]
    assert "openai" in platzhalter["anbieter"].lower()
    for wort in ("Personen", "Entity-IDs", "API-Schlüssel", "Gehirn"):
        assert wort in platzhalter["felder"]


@pytest.mark.asyncio
async def test_ja_fuehrt_zum_modell_formular(hass, enable_custom_integrations, entry):
    flow_id = await _bis_agent_setup(hass, entry)
    await hass.config_entries.options.async_configure(
        flow_id,
        user_input={"role": "comfort", "provider": "openai",
                    "url": "https://api.openai.com/v1"},
    )
    result = await hass.config_entries.options.async_configure(
        flow_id, user_input={"bestaetigt": True},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "agent_model"


@pytest.mark.asyncio
async def test_nein_fuehrt_zurueck_ins_setup(hass, enable_custom_integrations, entry):
    flow_id = await _bis_agent_setup(hass, entry)
    await hass.config_entries.options.async_configure(
        flow_id,
        user_input={"role": "comfort", "provider": "openai",
                    "url": "https://api.openai.com/v1"},
    )
    result = await hass.config_entries.options.async_configure(
        flow_id, user_input={"bestaetigt": False},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "agent_setup"


@pytest.mark.asyncio
async def test_ollama_laeuft_ohne_hinweis(hass, enable_custom_integrations, entry):
    """Der Standard bleibt unangetastet: Ollama geht direkt zur Modell-Wahl.
    Der Verbindungsruf selbst wird gefangen — der Zeuge prüft die ROUTE,
    nicht das Netz (pytest_socket blockt echte Sockets)."""
    async def _verbindung_ok(url):
        return True, "Testverbindung"

    flow_id = await _bis_agent_setup(hass, entry)
    with patch("custom_components.kontinuum.config_flow._test_ollama_connection",
               _verbindung_ok):
        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={"role": "comfort", "provider": "ollama", "url": ""},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "agent_model"


def test_die_felduebersicht_nennt_was_der_code_schickt():
    """CLOUD_FELDER hält mit dem Versand Schritt: die Kontext-Felder aus
    cortex._build_context/_format_context und die Entity-Liste aus
    _brain_state_block müssen alle benannt sein."""
    for wort in ("Modus", "Raum", "Personen", "Energie", "Risiko",
                 "Ereignis", "Token", "Gehirn", "Entity-IDs", "API-Schlüssel"):
        assert wort in CLOUD_FELDER, f"CLOUD_FELDER verschweigt: {wort}"
