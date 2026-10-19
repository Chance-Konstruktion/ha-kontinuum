"""Tests für die mitreisenden Schriften (Durchsicht 04.10., Punkt 4).

Der Befund: das Dashboard lud seine Schriften von Googles CDN —
``@import url('https://fonts.googleapis.com/css2?family=Orbitron…')``.
Jeder Panel-Aufruf meldete IP und User-Agent an Google, bevor auch nur
ein Buchstabe stand.

Der Heil: Orbitron und JetBrains Mono (beide SIL Open Font License 1.1)
reisen als WOFF2 mit der Integration — 9 Dateien, latin und latin-ext
(die Umlaute wohnen dort). Seit dem Umbau auf das native Panel zeigt das native Panel mit den Schriften
von Home Assistant; die Iframe-Seite und diese Dateien bleiben im Repo
(assets/), werden aber nicht mehr nach /local/ kopiert. Die Datei-Prüfungen
unten gelten weiter für diese Altlast.
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
async def test_einrichtung_kopiert_keine_schriften_mehr(hass, enable_custom_integrations):
    """Seit dem Umbau auf das native Panel (natives Panel) landet nichts mehr unter /local/.

    Das Panel zeichnet mit den Schriften von Home Assistant; die
    Iframe-Seite und ihre Schriften liegen nur noch im Repo
    (assets/), werden aber nicht mehr nach /config/www kopiert.
    """
    from unittest.mock import AsyncMock, patch

    import custom_components.kontinuum as kontinuum_init

    assert await async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(domain=DOMAIN, title="KONTINUUM", data={})
    entry.add_to_hass(hass)
    with patch.object(
        kontinuum_init, "async_register_dashboard_panel", AsyncMock(return_value=True)
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    www = Path(hass.config.config_dir) / "www"
    assert not (www / "kontinuum.html").exists()
    assert not (www / "kontinuum-fonts").exists()
