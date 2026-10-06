"""Tests für die API-Schluessel-Hygiene (Durchsicht 04.10., Punkt 6).

Der Befund (ha-kontinuum #1), beide Haelften:
1. Der Dienst ``configure_agent`` nahm ``api_key`` als Dienstdaten an —
   damit lief der Schluessel als ``call_service``-Ereignis ueber den
   Event-Bus (fuer jeden Lauscher lesbar, vom Recorder gespeichert).
2. Das Gehirn schrieb den Schluessel im Klartext in ``brain.json.gz``
   (``cortex_agents``).

Die Heilung: Der Schluessel wohnt NUR im Config-Entry (Config-/
Options-Flow). Das Gehirn speichert die Agent-Form ohne ihn, der Dienst
nimmt ihn nicht mehr an (laut verfallen), und eine einmalige Wanderung
bringt alte Schluessel aus brain.json.gz in den Entry, bevor das
naechste Speichern die Datei schluesselfrei neu schreibt.

Alle Tests laufen gegen eine echte (leere) Test-Home.
"""

import gzip
import json
import os

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.kontinuum as kontinuum_init
from custom_components.kontinuum.const import DOMAIN

GEHEIM_ENTRY = "sk-ENTRY-geheim-123"
GEHEIM_ENTRY_2 = "sk-ENTRY-zwei-456"


def _agent(mit_schluessel="", slot_name="comfort", provider="openai"):
    """Eine Agent-Form wie sie Entry und Gehirn tragen."""
    agent = {
        "name": slot_name, "provider": provider,
        "model": "gpt-4o-mini", "url": "https://api.openai.com/v1",
        "system_prompt": "du bist " + slot_name,
    }
    if mit_schluessel:
        agent["api_key"] = mit_schluessel
    return agent


@pytest.fixture
def entry(hass):
    """Ein KONTINUUM-Entry mit zwei Agenten — Schluessel im Entry."""
    mock = MockConfigEntry(
        domain=DOMAIN, title="KONTINUUM",
        data={
            "enable_cortex": True,
            "cortex_agents": {
                "1": _agent(mit_schluessel=GEHEIM_ENTRY),
                "2": _agent(mit_schluessel=GEHEIM_ENTRY_2, slot_name="energy"),
            },
        },
    )
    mock.add_to_hass(hass)
    return mock


async def _starten(hass, entry):
    """Entry aufsetzen und fertig warten; liefert das Gehirn."""
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_gehirn_traegt_den_schluessel_nie(
    hass, enable_custom_integrations, entry
):
    """Setup mit Entry-Agents: Agent-Form ja, Schluessel nein.

    Das Gehirn (hass.data[DOMAIN]['_cortex_agents']) speichert die
    Agenten OHNE api_key — der Schluessel bleibt im Entry. Die
    Arbeits-Exemplare im Cortex behalten ihn.
    """
    brain = await _starten(hass, entry)

    for slot in ("1", "2"):
        assert "api_key" not in brain["_cortex_agents"][slot]

    schluessel = {a.name: a.api_key for a in brain["cortex"].agents}
    assert schluessel["comfort"] == GEHEIM_ENTRY
    assert schluessel["energy"] == GEHEIM_ENTRY_2


@pytest.mark.asyncio
async def test_snapshot_schreibt_keinen_schluessel(
    hass, enable_custom_integrations, entry
):
    """Die Momentaufnahme (→ brain.json.gz) bleibt schluesselfrei.

    Vor dem Fix stand der Schluessel im Klartext in der Datei — hier
    zaehlt beides: kein api_key-Feld UND kein Schluessel-Wert in den
    Bytes.
    """
    brain = await _starten(hass, entry)

    roh = kontinuum_init._snapshot_brain(brain)
    data = json.loads(roh)

    for slot in ("1", "2"):
        assert "api_key" not in data["cortex_agents"][slot]
    assert GEHEIM_ENTRY.encode() not in roh
    assert GEHEIM_ENTRY_2.encode() not in roh


@pytest.mark.asyncio
async def test_dienst_verweigert_den_schluessel(
    hass, enable_custom_integrations, entry, caplog
):
    """configure_agent mit api_key: laut verfallen, nicht annehmen.

    Vor dem Fix reiste der Schluessel als call_service-Ereignis ueber
    den Bus und landete danach im Gehirn. Jetzt: Warnung im Log,
    Agent-Form ohne Schluessel, Arbeits-Exemplar ohne Schluessel.
    """
    brain = await _starten(hass, entry)

    await hass.services.async_call(
        DOMAIN, "configure_agent",
        {
            "slot": 3, "name": "safety", "provider": "openai",
            "model": "gpt-4o-mini", "url": "https://api.openai.com/v1",
            "api_key": "sk-DIENST-verboten", "prompt": "du bist safety",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "api_key" not in brain["_cortex_agents"]["3"]
    nach_name = {a.name: a.api_key for a in brain["cortex"].agents}
    assert nach_name["safety"] == ""
    assert any("IGNORIERT" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_dienst_bekommt_den_schluessel_aus_dem_entry(
    hass, enable_custom_integrations, entry
):
    """Dienst konfiguriert Slot 1 neu — der Entry-Schluessel bleibt.

    Der Dienst pflegt die Agent-Form (Modell, URL, Prompt); der
    Schluessel kommt zur Laufzeit aus dem Entry dazu. So bleibt ein
    dienstkonfigurierter Agent schluesselversorgt, ohne dass das
    Gehirn den Schluessel je haelt.
    """
    brain = await _starten(hass, entry)

    await hass.services.async_call(
        DOMAIN, "configure_agent",
        {
            "slot": 1, "name": "comfort", "provider": "openai",
            "model": "gpt-4o-2024-11-20", "url": "https://api.openai.com/v1",
            "prompt": "neuer Prompt",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    comfort = {a.name: a for a in brain["cortex"].agents}["comfort"]
    assert comfort.model == "gpt-4o-2024-11-20"
    assert comfort.api_key == GEHEIM_ENTRY
    assert "api_key" not in brain["_cortex_agents"]["1"]


@pytest.mark.asyncio
async def test_dienst_loeschen_haelt_andere_schluessel(
    hass, enable_custom_integrations, entry
):
    """remove_agent Slot 1: Slot 2 behaelt seinen Entry-Schluessel."""
    brain = await _starten(hass, entry)

    await hass.services.async_call(
        DOMAIN, "remove_agent", {"slot": 1}, blocking=True,
    )
    await hass.async_block_till_done()

    assert set(brain["_cortex_agents"]) == {"2"}
    energy = {a.name: a for a in brain["cortex"].agents}["energy"]
    assert energy.api_key == GEHEIM_ENTRY_2


@pytest.mark.asyncio
async def test_altersschluessel_wandern_in_den_entry(
    hass, enable_custom_integrations, caplog
):
    """Legacy-Installation: Schluessel in brain.json.gz → Entry.

    Der alte Weg schrieb den Schluessel ins Gehirn-File. Das Laden hebt
    ihn in die Uebergangstasche, das Setup bring ihn in den Entry
    (einmalige Wanderung), das Gehirn bleibt ohne. Das naechste
    Speichern ueberschreibt die Datei schluesselfrei.
    """
    alt_geheim = "sk-LEGACY-alt-789"
    mock = MockConfigEntry(
        domain=DOMAIN, title="KONTINUUM", data={"enable_cortex": True},
    )
    mock.add_to_hass(hass)

    # Alte brain.json.gz mit Klartext-Schluessel vorgeben — der Agent
    # existiert NUR im Gehirn (per Dienst konfigurierte Zeit).
    data_dir = hass.config.path("kontinuum")
    os.makedirs(data_dir, exist_ok=True)
    alt = {
        "version": "0.28.0",
        "cortex_agents": {
            "1": _agent(mit_schluessel=alt_geheim),
        },
    }
    with gzip.open(os.path.join(data_dir, "brain.json.gz"), "wb") as f:
        f.write(json.dumps(alt).encode())

    brain = await _starten(hass, mock)

    # Die Wanderung: der Entry traegt den Schluessel jetzt.
    assert mock.data["cortex_agents"]["1"]["api_key"] == alt_geheim
    assert any("ueberfuehrt" in r.message for r in caplog.records)

    # Das Gehirn bleibt ohne, die Tasche ist leer, der Agent laeuft.
    assert "api_key" not in brain["_cortex_agents"]["1"]
    assert "_cortex_schluessel_alt" not in brain
    comfort = {a.name: a for a in brain["cortex"].agents}["comfort"]
    assert comfort.api_key == alt_geheim


@pytest.mark.asyncio
async def test_options_flow_leer_behaelt_den_schluessel(
    hass, enable_custom_integrations, entry
):
    """Options-Flow: leeres Passwort-Feld haelt den alten Schluessel.

    Das Formular ECHOt den Schluessel nicht zurueck (kein Klartext im
    Formular-DOM) — deshalb bedeutet leer: vorhandenen behalten. Ein
    ausgefuelltes Feld ueberschreibt. Der Beweis laeuft ueber die
    oeffentliche Strasse (Flow-Manager, Menue → Cortex → Agent 1 →
    speichern) und liest das Ergebnis aus dem Entry — kein Griff in
    Flow-Interna.
    """
    from homeassistant.data_entry_flow import FlowResultType
    from homeassistant.setup import async_setup_component

    # Das Speichern am Fluss-Ende laedt den Entry neu — die Integration
    # gruesst dabei per persistent_notification.
    assert await async_setup_component(hass, "persistent_notification", {})

    async def _agent_formular(flow_id, api_key):
        """Agent 1 bearbeiten: Formular mit diesem api_key absenden."""
        result = await hass.config_entries.options.async_configure(
            flow_id, user_input={"action": "edit_1"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "agent_setup"
        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                "role": "comfort", "provider": "openai",
                "url": "https://api.openai.com/v1",
                "api_key": api_key,
            },
        )
        # openai — kein Ollama-Verbindungstest: naechster Schritt ist
        # das Modell-Formular.
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "agent_model"
        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={"model": "gpt-4o-mini", "system_prompt": "bleib"},
        )
        # zurueck zur Uebersicht, dann Menue → Fertig → speichern
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "agents_overview"
        result = await hass.config_entries.options.async_configure(
            flow_id, user_input={"action": "back"},
        )
        result = await hass.config_entries.options.async_configure(
            flow_id, user_input={"next_step_id": "finish"},
        )
        await hass.async_block_till_done()
        return result

    async def _fahren(api_key):
        """Komplette Options-Session: Menue → Cortex → Agent 1 → Ende."""
        result = await hass.config_entries.options.async_init(
            entry.entry_id
        )
        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "cortex"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "enable_cortex": True, "sequential_mode": False,
                "discussion_rounds": 2,
            },
        )
        assert result["step_id"] == "agents_overview"
        return await _agent_formular(result["flow_id"], api_key)

    # Leer: der gespeicherte Schluessel bleibt.
    ergebnis = await _fahren("")
    assert ergebnis["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data["cortex_agents"]["1"]["api_key"] == GEHEIM_ENTRY
    # Der zweite Agent bleibt unberuehrt.
    assert entry.data["cortex_agents"]["2"]["api_key"] == GEHEIM_ENTRY_2

    # Gefuellt: der Schluessel wechselt.
    ergebnis = await _fahren("sk-NEU-999")
    assert ergebnis["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data["cortex_agents"]["1"]["api_key"] == "sk-NEU-999"
