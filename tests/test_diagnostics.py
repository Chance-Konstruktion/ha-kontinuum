"""Tests für die Diagnose (Durchsicht 04.10., Punkt 9).

Der Auftrag: ``diagnostics.py`` her — Support braucht sie — und
``api_key``-Schlüssel dabei schwärzen. Drei Angriffspunkte:

1. Der Config-Entry trägt die Schlüssel (Punkt 6, Options-Flow) —
   ``entry.as_dict()`` ungefiltert in die Diagnose wäre der zweite
   Bus-Vorfall desselben Geheimnisses.
2. Das Gehirn speichert die Agent-Form schluesselfrei — aber bis das
   nächste Speichern die Datei neu schreibt, können Altdaten einen
   Schlüssel in ``_cortex_agents`` tragen. Auch dort schwärzen
   (Verteidigung in die Tiefe).
3. Was Support wirklich braucht — Versionen (HA, Integration, Kern),
   Betriebsart, Cortex-Lage, Datei-Fakten — muss da sein, ohne dass
   Muster oder gar ``brain.json.gz`` im Ganzen reisen.

Alle Tests laufen gegen eine echte (leere) Test-Home.
"""

import gzip
import pathlib
import json

import pytest
from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kontinuum.const import DOMAIN
from custom_components.kontinuum.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_diagnostics_for_integration,
)

GEHEIM_ENTRY = "sk-ENTRY-geheim-123"
GEHEIM_ALT = "sk-ALT-altlast-42"


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
                "2": _agent(slot_name="energy", provider="anthropic"),
            },
        },
    )
    mock.add_to_hass(hass)
    return mock


async def _starten(hass, entry):
    """Entry aufsetzen und fertig warten."""
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_entry_diagnose_schwaerzt_den_schluessel(
    hass, enable_custom_integrations, entry
):
    """Volles Setup: der Entry-Schluessel wird REDACTED, die Form bleibt.

    Support liest Provider, Modell und Namen — aber niemals den
    Schlüssel, nicht einmal im Klartext im JSON.
    """
    await _starten(hass, entry)

    diag = await async_get_config_entry_diagnostics(hass, entry)

    flach = json.dumps(diag)
    assert GEHEIM_ENTRY not in flach

    agenten = diag["entry"]["data"]["cortex_agents"]
    assert agenten["1"]["api_key"] == REDACTED
    assert agenten["1"]["name"] == "comfort"
    assert agenten["1"]["provider"] == "openai"
    assert agenten["1"]["model"] == "gpt-4o-mini"
    # Agent ohne Schlüssel bleibt unangetastet
    assert "api_key" not in agenten["2"]

    assert diag["entry"]["domain"] == DOMAIN
    assert diag["entry"]["title"] == "KONTINUUM"


async def test_gehirn_diagnose_schwaerzt_altschluessel(
    hass, enable_custom_integrations, entry
):
    """Altdaten-Szenario: Schlüssel noch im Gehirn bis zum nächsten Speichern.

    Das Gehirn ist schluesselfrei (Punkt 6) — aber ein Import aus einer
    Zeit davor kann noch einen tragen. Die Diagnose schwärzt trotzdem:
    Verteidigung in die Tiefe, Entry-Seite UND Gehirn-Seite.
    """
    hass.data[DOMAIN] = {
        "preset": "ausgeglichen",
        "_home_only_mode": False,
        "_scenes_enabled": False,
        "_cortex_agents": {"1": _agent(mit_schluessel=GEHEIM_ALT)},
    }

    diag = await async_get_config_entry_diagnostics(hass, entry)

    flach = json.dumps(diag)
    assert GEHEIM_ALT not in flach
    assert GEHEIM_ENTRY not in flach

    agent_alt = diag["gehirn"]["cortex_agents"]["1"]
    assert agent_alt["api_key"] == REDACTED
    assert agent_alt["name"] == "comfort"
    assert diag["gehirn"]["preset"] == "ausgeglichen"


async def test_versionen_stehen_in_jeder_diagnose(
    hass, enable_custom_integrations, entry
):
    """HA, Integration und Kern — der Support-Fall beginnt mit den Fassungen.

    Die Integrations-Fassung kommt aus manifest.json (einzige Wahrheit),
    die Kern-Fassung entscheidet über den Juli-Bruch (Punkt 0).
    """
    from homeassistant.loader import async_get_integration

    await _starten(hass, entry)
    integration = await async_get_integration(hass, DOMAIN)

    diag = await async_get_config_entry_diagnostics(hass, entry)

    versionen = diag["versionen"]
    from homeassistant.const import __version__ as ha_fassung
    assert versionen["homeassistant"] == ha_fassung
    assert versionen["integration"] == integration.version
    # Die Fassung kommt aus manifest.json — einzige Wahrheit
    manifest_pfad = (
        pathlib.Path(__file__).resolve().parent.parent
        / "custom_components" / "kontinuum" / "manifest.json"
    )
    manifest = json.loads(manifest_pfad.read_text(encoding="utf-8"))
    assert versionen["integration"] == manifest["version"]
    assert versionen["kern"] is not None
    assert versionen["kern"].startswith("0.7.")


async def test_datei_fakten_lesen_ohne_inhalt(
    hass, enable_custom_integrations, entry, tmp_path
):
    """Existenz, Größe, Alter von brain.json.gz — niemals der Inhalt.

    Die Fakten reichen für die Support-Frage „speichert das Gehirn
    überhaupt?"; die Muster darin sind personenbezogen und bleiben
    draußen. os.stat läuft im Executor (Werkstatt-Standard, Punkt 2).
    """
    gezielpfad = tmp_path / "kontinuum"
    gezielpfad.mkdir()
    payload = b"{}"
    with gzip.open(gezielpfad / "brain.json.gz", "wb") as f:
        f.write(payload)

    hass.data[DOMAIN] = {
        "preset": "ausgeglichen",
        "_cortex_agents": {},
        "_data_dir": str(gezielpfad),
    }

    diag = await async_get_config_entry_diagnostics(hass, entry)

    datei = diag["gehirn"]["datei"]
    assert datei["vorhanden"] is True
    assert datei["groesse_bytes"] > 0
    assert "T" in datei["geaendert"]  # ISO-8601


async def test_datei_fakten_fehlende_datei(
    hass, enable_custom_integrations, entry, tmp_path
):
    """Ohne brain.json.gz: vorhanden=False statt einer Ausnahme."""
    hass.data[DOMAIN] = {
        "preset": "ausgeglichen",
        "_cortex_agents": {},
        "_data_dir": str(tmp_path),
    }

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["gehirn"]["datei"]["vorhanden"] is False


async def test_diagnose_ohne_laufendes_gehirn(
    hass, enable_custom_integrations, entry
):
    """Integration nicht gestartet: None statt Ausnahme.

    Support fragt Diagnosen auch für geladene, aber NICHT laufende
    Entries ab — die Diagnose muss antworten können, ohne am Teil zu
    scheitern, das sie beschreiben soll.
    """
    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["gehirn"] is None
    assert diag["versionen"]["integration"] == "0.31.1-experimental"


async def test_integration_diagnose_listet_alle_entries(
    hass, enable_custom_integrations, entry
):
    """Die Integrations-Sicht sammelt jeden Entry, jeden geschwärzt.

    Auch hier: Form bleibt (provider, model), Schlüssel wird REDACTED —
    und die Gehirn-Übersicht steht als gemeinsames Blockstück bereit.
    """
    from homeassistant.loader import async_get_integration

    zweiter = MockConfigEntry(
        domain=DOMAIN, title="KONTINUUM ZWEI",
        data={"cortex_agents": {"1": _agent(mit_schluessel=GEHEIM_ENTRY,
                                            slot_name="energy")}},
    )
    zweiter.add_to_hass(hass)
    hass.data[DOMAIN] = {
        "preset": "neugierig",
        "_cortex_agents": {},
    }

    integration = await async_get_integration(hass, DOMAIN)
    diag = await async_get_diagnostics_for_integration(hass, integration)

    flach = json.dumps(diag)
    assert GEHEIM_ENTRY not in flach

    titel = {e["title"] for e in diag["entries"]}
    assert titel == {"KONTINUUM", "KONTINUUM ZWEI"}

    for eintrag in diag["entries"]:
        for agent in eintrag["data"].get("cortex_agents", {}).values():
            if "api_key" in agent:
                assert agent["api_key"] == REDACTED

    assert diag["gehirn"]["preset"] == "neugierig"
    assert diag["versionen"]["kern"] is not None
