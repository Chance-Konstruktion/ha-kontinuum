"""Tests für das native KONTINUUM-Panel (Umbau auf das native Panel).

Das Dashboard war eine Iframe-Seite unter ``/local/kontinuum.html`` mit eigener
Anmeldung (Token aus dem Eltern-Frame). Jetzt ist es ein Custom Element
(``panel_custom``), das ``hass`` von Home Assistant bekommt und aus den Elementen
des Hauses gebaut ist (``frontend/kontinuum-panel.js``).

Diese Tests brauchen kein laufendes Home Assistant und nicht einmal dessen
Pytest-Plugin: ``panel.py`` wird mit Attrappen der HA-Bausteine geladen, die
JS-Datei fährt der Node-Zeuge (tests/js/panel_pruefung.js). Was sie NICHT
prüfen: wie das Panel in einem echten Home Assistant aussieht und ob die
Elemente des Hauses (hass-tabs-subpage, ha-card ...) wie erwartet reagieren.
"""

import asyncio
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Unter dem HA-Pytest-Plugin brauchen auch diese Tests eine laufende Schleife;
# als async-Tests bekommen sie die vom Plugin (sync-Tests nach async-Tests
# fanden "no current event loop").

WURZEL = Path(__file__).resolve().parent.parent
KOMPONENTE = WURZEL / "custom_components" / "kontinuum"
PANEL_PY = KOMPONENTE / "panel.py"
PANEL_JS = KOMPONENTE / "frontend" / "kontinuum-panel.js"



def _panel_laden():
    """panel.py als eigenes Modul laden (ohne das Paket, das Home Assistant importiert)."""
    spec = importlib.util.spec_from_file_location("kontinuum_panel_unter_test", PANEL_PY)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture
def ha(monkeypatch):
    """Attrappen der Home-Assistant-Bausteine, die panel.py in der Funktion holt."""
    class StaticPathConfig:
        def __init__(self, url_path, path, cache_headers=True):
            self.url_path, self.path, self.cache_headers = url_path, path, cache_headers

    http = types.ModuleType("homeassistant.components.http")
    http.StaticPathConfig = StaticPathConfig
    frontend = types.ModuleType("homeassistant.components.frontend")
    frontend.async_remove_panel = MagicMock()
    panel_custom = types.ModuleType("homeassistant.components.panel_custom")
    panel_custom.async_register_panel = AsyncMock()
    komponenten = types.ModuleType("homeassistant.components")
    komponenten.http, komponenten.frontend, komponenten.panel_custom = http, frontend, panel_custom
    hauptmodul = types.ModuleType("homeassistant")
    hauptmodul.components = komponenten
    for name, m in (("homeassistant", hauptmodul), ("homeassistant.components", komponenten),
                    ("homeassistant.components.http", http), ("homeassistant.components.frontend", frontend),
                    ("homeassistant.components.panel_custom", panel_custom)):
        monkeypatch.setitem(sys.modules, name, m)
    hass = SimpleNamespace(data={}, http=SimpleNamespace(async_register_static_paths=AsyncMock()))
    return SimpleNamespace(hass=hass, frontend=frontend, panel_custom=panel_custom)


async def test_panel_wird_als_custom_element_angemeldet(ha):
    p = _panel_laden()
    assert await (p.async_register_dashboard_panel(ha.hass)) is True
    ha.panel_custom.async_register_panel.assert_awaited_once()
    k = ha.panel_custom.async_register_panel.await_args.kwargs
    assert k["frontend_url_path"] == "kontinuum", "Adresse in der Seitenleiste bleibt /kontinuum"
    assert k["sidebar_title"] == "KONTINUUM"
    assert k["sidebar_icon"] == "mdi:brain"
    assert k["webcomponent_name"] == "kontinuum-panel"
    assert k["embed_iframe"] is False, "kein Iframe mehr: das Panel bekommt hass selbst"
    assert k["require_admin"] is False
    assert k["module_url"].startswith("/kontinuum_panel/kontinuum-panel.js?v="), k["module_url"]
    assert "iframe" not in json.dumps(k, default=str).replace("embed_iframe", "")
    assert "/local/" not in json.dumps(k, default=str)


async def test_alte_registrierung_wird_vorher_entfernt(ha):
    """Ein Neuladen des Eintrags darf nicht an dem alten Panel scheitern."""
    p = _panel_laden()
    await (p.async_register_dashboard_panel(ha.hass))
    ha.frontend.async_remove_panel.assert_called_once_with(ha.hass, "kontinuum")


async def test_datei_wird_statisch_ausgeliefert_und_nur_einmal_angemeldet(ha):
    p = _panel_laden()
    await (p.async_register_dashboard_panel(ha.hass))
    await (p.async_register_dashboard_panel(ha.hass))        # Neuladen des Eintrags
    anmelden = ha.hass.http.async_register_static_paths
    anmelden.assert_awaited_once()
    (liste,) = anmelden.await_args.args
    assert len(liste) == 1
    assert liste[0].url_path == "/kontinuum_panel/kontinuum-panel.js"
    assert Path(liste[0].path) == PANEL_JS and Path(liste[0].path).is_file()
    assert liste[0].cache_headers is False
    assert ha.panel_custom.async_register_panel.await_count == 2, "das Panel selbst wird bei jedem Neuladen neu gemeldet"


async def test_fehler_beim_anmelden_kippt_die_einrichtung_nicht(ha):
    ha.panel_custom.async_register_panel.side_effect = ValueError("Panel schon da")
    p = _panel_laden()
    assert await (p.async_register_dashboard_panel(ha.hass)) is False


async def test_ohne_http_kein_absturz(ha):
    ha.hass.http = None                                   # z. B. in Tests ohne http-Komponente
    p = _panel_laden()
    assert await (p.async_register_dashboard_panel(ha.hass)) is False


async def test_asset_version_folgt_der_datei():
    p = _panel_laden()
    v = p.asset_version()
    assert v.isdigit() and int(v) > 0, "die Kennung muss aus dem Änderungsdatum der JS-Datei kommen"


async def test_webcomponent_name_passt_zur_js_datei():
    p = _panel_laden()
    js = PANEL_JS.read_text(encoding="utf-8")
    assert f'customElements.define("{p.WEBCOMPONENT}"' in js


async def test_einrichtung_kopiert_nichts_mehr_und_registriert_kein_iframe():
    """Der Iframe-Weg ist aus __init__.py verschwunden."""
    q = (KOMPONENTE / "__init__.py").read_text(encoding="utf-8")
    assert "_install_dashboard" not in q
    assert not re.search(r"_register_dashboard_panel", q), "die alte Iframe-Registrierung lebt noch"
    assert "/local/kontinuum.html" not in q
    assert '"iframe"' not in q and "'iframe'" not in q
    assert "async_register_dashboard_panel(hass)" in q
    assert re.search(r"from \.panel import async_register_dashboard_panel", q)
    pq = PANEL_PY.read_text(encoding="utf-8")
    assert 'component_name="iframe"' not in pq and "async_register_built_in_panel" not in pq


async def test_manifest_nennt_http_und_panel_custom():
    m = json.loads((KOMPONENTE / "manifest.json").read_text(encoding="utf-8"))
    assert set(m["after_dependencies"]) == {"http", "panel_custom"}
    assert m["dependencies"] == [], "harte Abhängigkeiten würden die Tests ohne Frontend-Paket kippen"


async def test_altes_iframe_dashboard_bleibt_unangetastet_im_repo():
    """Die Wächter-Tests am alten Dashboard (Schriften, Datenschicht) lesen diese Dateien weiter."""
    assert (KOMPONENTE / "assets" / "kontinuum.html").is_file()
    assert (KOMPONENTE / "assets" / "kontinuum-daten.js").is_file()


async def test_js_panel_laeuft_unter_node():
    """Node fährt das Panel gegen Attrappen: Erkennung, Anzeigewerte, Tabs, Abo, Dienste."""
    if shutil.which("node") is None:
        pytest.skip("Node ist nicht installiert — der JS-Zeuge kann nicht fahren")
    lauf = subprocess.run(
        ["node", str(Path(__file__).parent / "js" / "panel_pruefung.js")],
        capture_output=True, text=True, timeout=60, encoding="utf-8",
    )
    assert lauf.returncode == 0, f"der Node-Zeuge fiel:\n{lauf.stdout}\n{lauf.stderr}"
    zeugnis = [z for z in lauf.stdout.splitlines() if z.startswith("ZEUGNIS")]
    assert zeugnis, f"kein Zeugnis in der Ausgabe:\n{lauf.stdout}"
    daten = json.loads(zeugnis[-1][len("ZEUGNIS "):])
    assert daten["fehler"] == 0, lauf.stdout
    assert daten["pruefungen"] >= 45, f"zu wenige Prüfungen gefahren: {daten['pruefungen']}"
