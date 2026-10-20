"""Das KONTINUUM-Panel in der Seitenleiste von Home Assistant.

Das Dashboard ist ein natives Panel (Custom Element, ``panel_custom``) statt
der früheren Iframe-Seite unter ``/local/kontinuum.html`` (siehe CHANGELOG,
„Unveröffentlicht“): Home Assistant reicht
``hass``, ``narrow``, ``route`` und ``panel`` herein, das Panel baut sich aus
den Elementen des Hauses (siehe ``frontend/kontinuum-panel.js``). Daten und
Dienste laufen über die Verbindung von Home Assistant, es gibt keine eigene
Anmeldung mehr und nichts wird nach ``/config/www`` kopiert.

Dieses Modul importiert beim Laden nichts von Home Assistant: die Bausteine
werden erst in der Funktion geholt, damit es sich auch ohne HA prüfen lässt.
"""

from __future__ import annotations

import logging
import os

_LOGGER = logging.getLogger(__name__)

URL_PATH = "kontinuum"                      # Adresse in der Seitenleiste: /kontinuum
WEBCOMPONENT = "kontinuum-panel"            # Name des Custom Elements in der JS-Datei
SIDEBAR_TITLE = "KONTINUUM"
SIDEBAR_ICON = "mdi:brain"
PANEL_JS_URL = "/kontinuum_panel/kontinuum-panel.js"
PANEL_JS_DATEI = os.path.join(os.path.dirname(__file__), "frontend", "kontinuum-panel.js")
# Merker in hass.data: die statische Adresse darf nur einmal angemeldet werden
# (bei einem Neuladen des Eintrags wirft HA sonst, die Panel-Registrierung wird wiederholt).
_STATISCH_ANGEMELDET = "kontinuum_panel_statisch"


def asset_version() -> str:
    """Kennung der ausgelieferten Panel-Datei (für ?v= in der Adresse).

    Ohne wechselnde Adresse hält der Browser nach einem Update die alte
    JS-Datei im Cache (am 17.10.2026 lief so eine reparierte Datei in der
    alten Fassung weiter).
    """
    try:
        return str(int(os.path.getmtime(PANEL_JS_DATEI)))
    except OSError:
        return "0"


async def _statisch_anmelden(hass) -> None:
    """Die JS-Datei unter PANEL_JS_URL ausliefern (einmal je HA-Lauf)."""
    if hass.data.get(_STATISCH_ANGEMELDET):
        return
    try:
        # HA 2024.7 und neuer
        from homeassistant.components.http import StaticPathConfig
    except ImportError:
        # ältere HA-Versionen
        hass.http.register_static_path(PANEL_JS_URL, PANEL_JS_DATEI, False)
    else:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_JS_URL, PANEL_JS_DATEI, False)]
        )
    hass.data[_STATISCH_ANGEMELDET] = True


async def async_register_dashboard_panel(hass) -> bool:
    """Meldet die JS-Datei und das Panel an. ``True``, wenn das Panel steht.

    Ein Fehler hier darf das Einrichten der Integration nicht kippen: er wird
    gemeldet, die Sensoren laufen weiter.
    """
    try:
        # Panel entfernen, falls es schon existiert (Neuladen des Eintrags)
        try:
            from homeassistant.components.frontend import async_remove_panel
            async_remove_panel(hass, URL_PATH)
        except Exception:  # noqa: BLE001 - war nicht registriert
            pass

        from homeassistant.components import panel_custom

        await _statisch_anmelden(hass)
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=URL_PATH,
            webcomponent_name=WEBCOMPONENT,
            module_url=f"{PANEL_JS_URL}?v={asset_version()}",
            sidebar_title=SIDEBAR_TITLE,
            sidebar_icon=SIDEBAR_ICON,
            require_admin=False,
            config={},
            embed_iframe=False,
        )
    except Exception as err:  # noqa: BLE001 - Panel ist Beiwerk, nicht Kern
        _LOGGER.warning("KONTINUUM Panel konnte nicht registriert werden: %s", err)
        return False
    _LOGGER.info("KONTINUUM Panel registriert (panel_custom, /%s)", URL_PATH)
    return True
