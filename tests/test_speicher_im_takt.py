"""Tests für die Momentaufnahme im Ereignis-Takt (Durchsicht 04.10., Punkt 2).

Der Befund (ha-kontinuum #1): ``_save_brain`` lief als Executor-Job und
rief dort ``to_dict()`` ALLER Module auf, während die Ereignis-Schleife
dieselben Module weiter veränderte. Die Folge war eine Rennbahn:
inkonsistente Momentaufnahmen oder „dictionary changed size during
iteration“, still verworfen (im Betrieb bisher nicht beobachtet — aber
nicht beobachtet heißt nicht nicht vorhanden).

Der Beweis hier wiegt drei Dinge:

1. Die Momentaufnahme (``_snapshot_brain`` / ``_snapshot_aux_modules``)
   entsteht IM Takt — im selben Faden, der die Module verändert —,
   während gzip+Schreiben (``_write_brain_gz`` /
   ``_write_aux_modules_gz``) im Executor-Faden läuft.
2. Eine plat-zende Momentaufnahme tötet weder den Takt noch das
   Entladen (Fehler fangen, weitersummen).
3. Das gespeicherte Gehirn ist ladbar — dasselbe Format, dieselben
   Module (der Rundweg läuft über das echte Entladen).
"""

import asyncio
import gzip
import json
import os
import threading

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.kontinuum as kontinuum_init
from custom_components.kontinuum.const import DOMAIN


@pytest.fixture
def entry(hass):
    """Ein leerer KONTINUUM-Entry — Presets auf Werkseinstellung."""
    mock = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    mock.add_to_hass(hass)
    return mock


@pytest.fixture
async def benachrichtigungen(hass):
    """persistent_notification laden, bevor KONTINUUM startet (Straßenlärm
    einer sonst scheiternden Startup-Aufgabe — siehe test_reload_listeners)."""
    assert await async_setup_component(hass, "persistent_notification", {})


@pytest.mark.asyncio
async def test_momentaufnahme_im_takt_gzip_im_executor(
    hass, enable_custom_integrations, benachrichtigungen, entry, monkeypatch
):
    """Entladen lost eine Speicherung aus: Foto im Takt, gzip im Executor."""
    takt_faden = threading.get_ident()
    faden = {"foto": [], "gzip": []}

    orig_foto = kontinuum_init._snapshot_brain
    orig_write = kontinuum_init._write_brain_gz

    def spion_foto(brain):
        try:
            im_takt = asyncio.get_running_loop() is hass.loop
        except RuntimeError:
            im_takt = False
        faden["foto"].append(im_takt)
        return orig_foto(brain)

    def spion_write(raw, path):
        faden["gzip"].append(threading.get_ident())
        return orig_write(raw, path)

    monkeypatch.setattr(kontinuum_init, "_snapshot_brain", spion_foto)
    monkeypatch.setattr(kontinuum_init, "_write_brain_gz", spion_write)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Jede Momentaufnahme entstand im Takt (Schleifen-Faden, laufender Loop) …
    assert faden["foto"], "keine Momentaufnahme ausgelöst"
    assert all(faden["foto"])
    # … und jedes gzippen in einem ANDEREN Faden (Executor).
    assert faden["gzip"], "kein Schreib-Job ausgelöst"
    assert all(f != takt_faden for f in faden["gzip"])


@pytest.mark.asyncio
async def test_momentaufnahme_der_aux_module_auch_im_takt(
    hass, enable_custom_integrations, benachrichtigungen, entry, monkeypatch
):
    """Die Aux-Module (Reticular, Locus, Entorhinal …) laufen im selben Takt.

    Sie gehören zur selben Rennbahn: to_dict() im Executor-Faden war auch
    hier eine Momentaufnahme aus zwei Fäden zugleich.
    """
    takt_faden = threading.get_ident()
    faden = []

    orig_foto = kontinuum_init._snapshot_aux_modules
    orig_write = kontinuum_init._write_aux_modules_gz

    def spion_foto(brain):
        try:
            im_takt = asyncio.get_running_loop() is hass.loop
        except RuntimeError:
            im_takt = False
        faden.append(im_takt)
        return orig_foto(brain)

    def spion_write(snapshots, config_dir):
        assert threading.get_ident() != takt_faden
        return orig_write(snapshots, config_dir)

    monkeypatch.setattr(kontinuum_init, "_snapshot_aux_modules", spion_foto)
    monkeypatch.setattr(kontinuum_init, "_write_aux_modules_gz", spion_write)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Die Aux-Speicherung reist im Stopp-Handler (wie im Betrieb: das
    # Entladen speichert nur das Gehirn, der Stopp beide).
    from homeassistant.core import EVENT_HOMEASSISTANT_STOP

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert faden and all(faden)


@pytest.mark.asyncio
async def test_platzende_momentaufnahme_toetet_den_takt_nicht(
    hass, enable_custom_integrations, benachrichtigungen, entry, monkeypatch
):
    """Wenn to_dict() mitten im Fotografieren platzt (der alte Feind:
    „dictionary changed size during iteration“), bleibt alles handhabbar —
    das Entladen läuft durch, die Schleife lebt, der nächste Zyklus geht.
    """

    def boeses_foto(brain):
        raise RuntimeError("dictionary changed size during iteration")

    monkeypatch.setattr(kontinuum_init, "_snapshot_brain", boeses_foto)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_gespeichertes_gehirn_ist_ladbar(
    hass, enable_custom_integrations, benachrichtigungen, entry
):
    """Der Rundweg: nach dem Entladen steht eine echte, lesbare brain.json.gz
    mit Version und Modul-Beständen — dasselbe Format wie vorher."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    pfad = os.path.join(hass.config.config_dir, "kontinuum", "brain.json.gz")
    assert os.path.exists(pfad), "brain.json.gz fehlt"

    with gzip.open(pfad, "rb") as f:
        daten = json.load(f)

    assert daten["version"] == kontinuum_init.VERSION
    for modul in ("thalamus", "hippocampus", "cerebellum", "prefrontal"):
        assert modul in daten, f"Modul {modul} fehlt im gespeicherten Gehirn"
