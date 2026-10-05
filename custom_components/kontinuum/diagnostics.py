"""Diagnose für Support-Downloads (Durchsicht 04.10., Punkt 9).

Es gab keine ``diagnostics.py`` — Support hatte damit keinen geordneten
Blick in den Zustand einer Installation. Diese Datei liefert ihn:
Versionen (Home Assistant, Integration, Kern), die Konfiguration des
Config-Entry und eine Statistik über das Gehirn. Große Rohdaten gehören
hinein nicht: Weder ``brain.json.gz`` im Ganzen (personenbezogene
Muster, Megabytes) noch irgendwelche Schlüssel.

Schwärzen ist der Kern des Auftrags („Schlüssel dabei schwärzen"):
Der API-Schlüssel wohnt im Config-Entry (Punkt 6, Options-Flow) — und
bis das nächste Speichern die Datei neu schreibt, kann er aus Altdaten
NOCH in ``brain['_cortex_agents']`` stehen. Beide Orte laufen deshalb
durch :func:`async_redact_data`; für den Gehirn-Teil ist das
Verteidigung in die Tiefe, für den Entry-Teil Pflicht.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from importlib import metadata
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration, async_get_integration

from . import BRAIN_FILE, DATA_DIR
from .const import DOMAIN

# Alles, was nie in einen Support-Download gehört. async_redact_data
# schwärzt Schlüssel GANZER Übereinstimmung — auch verschachtelt — und
# Werte, die exakt einem Eintrag entsprechen. „api_key" greift die
# Agent-Slots in entry.data und (für Altdaten) im Gehirn.
TO_REDACT = {"api_key", "token", "password", "secret"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Diagnose für einen KONTINUUM-Config-Entry.

    Liefert Entry (geschwärzt), Versionen und Gehirn-Statistik —
    Support-Seiten bieten diese Funktion pro Entry an.
    """
    integration = await async_get_integration(hass, DOMAIN)
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "versionen": _versionen(integration),
        "gehirn": await _gehirn_uebersicht(hass),
    }


async def async_get_diagnostics_for_integration(
    hass: HomeAssistant, integration: Integration
) -> dict[str, Any]:
    """Diagnose für die Integration als Ganzes.

    Alle Entries (geschwärzt) plus dieselbe Gehirn-Übersicht — für den
    Fall, dass ein Eintrag nicht geladen werden kann.
    """
    eintraege = hass.config_entries.async_entries(DOMAIN)
    return {
        "versionen": _versionen(integration),
        "entries": [
            async_redact_data(eintrag.as_dict(), TO_REDACT)
            for eintrag in eintraege
        ],
        "gehirn": await _gehirn_uebersicht(hass),
    }


def _versionen(integration: Integration) -> dict[str, Any]:
    """HA-Fassung, Integrations-Fassung (manifest.json), Kern-Fassung.

    Die Kern-Fassung entscheidet über den Juli-Bruch (Punkt 0) — sie
    gehört in jeden Support-Fall. Fehlt das Paket (unwahrscheinlich,
    es ist Anforderung des Manifests), steht ``None`` statt einer
    Ausnahme: Die Diagnose darf nie am Systemteil scheitern, das sie
    gerade beschreiben soll.
    """
    try:
        kern = metadata.version("kontinuum-core")
    except metadata.PackageNotFoundError:
        kern = None
    return {
        "homeassistant": HA_VERSION,
        "integration": integration.version,
        "kern": kern,
    }


def _gehirn_statistik(brain: Any) -> dict[str, Any] | None:
    """Zahlen und Formen aus dem Gehirn — keine Muster, keine Schlüssel.

    ``brain`` ist das Wörterbuch aus ``hass.data[DOMAIN]``: Modul-Objekte
    (deren volle ``to_dict()``-Bilder gehören hier nicht her) und
    private Einträge. Geholt wird nur, was Support braucht: Betriebsart,
    Cortex-Lage und die Agent-Form. Letztere ist normalerweise schon
    schluesselfrei (Punkt 6) — Altdaten können bis zum nächsten Speichern
    aber noch einen tragen, darum die Schwärzung auch hier.
    """
    if not isinstance(brain, dict):
        return None
    statistik: dict[str, Any] = {
        "preset": brain.get("preset"),
        "home_only_mode": brain.get("_home_only_mode"),
        "scenes_enabled": brain.get("_scenes_enabled"),
        "cortex_agents": async_redact_data(
            brain.get("_cortex_agents", {}), TO_REDACT
        ),
    }
    cortex = brain.get("cortex")
    if cortex is not None:
        statistik["cortex"] = {
            "agenten_anzahl": len(getattr(cortex, "agents", None) or []),
            "sequential_mode": getattr(cortex, "sequential_mode", None),
            "discussion_rounds": getattr(cortex, "discussion_rounds", None),
        }
    return statistik


def _gehirn_datei_fakten(data_dir: str) -> dict[str, Any]:
    """Existenz, Größe und Alter von brain.json.gz (läuft im Executor).

    Der Pfad kommt aus dem Gehirn (``_data_dir``, beim Setup gesetzt)
    oder dem Standardort. Nur Zahlen — der Inhalt der Datei ist
    personenbezogen und gehört nicht in die Diagnose.
    """
    pfad = os.path.join(data_dir, BRAIN_FILE)
    try:
        st = os.stat(pfad)
    except OSError:
        return {"vorhanden": False}
    return {
        "vorhanden": True,
        "groesse_bytes": st.st_size,
        "geaendert": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
    }


async def _gehirn_uebersicht(hass: HomeAssistant) -> dict[str, Any] | None:
    """Statistik + Datei-Fakten des Gehirns, alles Executor-sauber.

    Läuft die Integration nicht (oder fehlt das Gehirn), kommt ``None``
    — Support liest daraus „nicht gestartet", nicht „Fehler". Das
    Datei-Fakten-Stück (os.stat) reist in den Executor, wie es der
    Werkstatt-Standard seit Punkt 2 verlangt: nichts Blockierendes in
    der Ereignis-Schleife.
    """
    brain = hass.data.get(DOMAIN)
    if not isinstance(brain, dict):
        return None
    data_dir = brain.get("_data_dir") or hass.config.path(DATA_DIR)
    datei = await hass.async_add_executor_job(
        _gehirn_datei_fakten, data_dir
    )
    uebersicht = _gehirn_statistik(brain)
    if uebersicht is not None:
        uebersicht["datei"] = datei
    return uebersicht
