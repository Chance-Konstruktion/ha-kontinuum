"""Tests für die mitreisenden Schriften (Durchsicht 04.10., Punkt 4).

Der Befund: das Dashboard lud seine Schriften von Googles CDN —
``@import url('https://fonts.googleapis.com/css2?family=Orbitron…')``.
Jeder Panel-Aufruf meldete IP und User-Agent an Google, bevor auch nur
ein Buchstabe stand.

Der Heil: Orbitron und JetBrains Mono (beide SIL Open Font License 1.1)
reisen jetzt als WOFF2 mit der Integration — 9 Dateien, latin und
latin-ext (die Umlaute wohnen dort), geliefert über dieselbe
Install-Route wie das Dashboard selbst: ``/local/kontinuum-fonts/``.
"""

import re
from pathlib import Path

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kontinuum.const import DOMAIN

HTML = Path("custom_components/kontinuum/assets/kontinuum.html")
FONTS = Path("custom_components/kontinuum/assets/fonts")


def _geladene_schriften():
    """Alle @font-face-Quellpfade im Dashboard (ohne Query/Fragment)."""
    html = HTML.read_text(encoding="utf-8")
    return re.findall(r"@font-face\{[^}]*?src:url\('([^']+)'\)", html)


def test_dashboard_laedt_keine_externen_schriften():
    """Kein @import, keine absolute URL — nichts verlässt das Haus."""
    html = HTML.read_text(encoding="utf-8")
    assert "@import" not in html, "das Dashboard importiert noch externe Stile"
    assert not re.search(r"url\(\s*['\"]https?://", html), (
        "das Dashboard lädt eine Ressource über eine absolute URL"
    )


def test_geladene_schriften_reisen_mit():
    """Jede im Dashboard geladene Schrift liegt als Datei daneben."""
    pfade = _geladene_schriften()
    assert pfade, "das Dashboard lädt gar keine Schriften (mehr)?"
    for pfad in pfade:
        datei = FONTS / Path(pfad).name
        assert datei.is_file(), f"geladene Schrift fehlt im Gepäck: {pfad}"


def test_lizenzen_reisen_mit():
    """Bündeln ohne Lizenz wäre ein Diebstahl — beide OFL-Texte liegen dabei."""
    assert (FONTS / "OFL-Orbitron.txt").is_file()
    assert (FONTS / "OFL-JetBrains-Mono.txt").is_file()


@pytest.mark.asyncio
async def test_installation_legt_schriften_ab(hass, enable_custom_integrations):
    """Nach dem Setup liegen Dashboard und Schriften unter /local/."""
    assert await async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    www = Path(hass.config.config_dir) / "www"
    assert (www / "kontinuum.html").is_file()

    gelegt = list((www / "kontinuum-fonts").glob("*.woff2"))
    geladen = {Path(p).name for p in _geladene_schriften()}
    assert geladen, "das Dashboard lädt gar keine Schriften (mehr)?"
    assert geladen <= {f.name for f in gelegt}, (
        f"nicht alle geladenen Schriften wurden installiert: "
        f"{sorted(geladen - {f.name for f in gelegt})}"
    )
