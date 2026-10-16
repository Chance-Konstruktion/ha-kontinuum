"""Tests für Punkt 3 der Durchsicht 04.10.: die Entdeckung wählt aus.

Der Befund (ha-kontinuum #1): ``_discover_entities`` meldete JEDE Entität
der Registry an, ausgeschlossen wurde nur per Label. In Häusern mit vielen
Server- und Netzwerksensoren lernte das Gehirn das Betriebspersonal statt
der Bewohner.

Die Heilung: Standard-Ausschluss nach Integrations-Plattform
(Systemüberwachung, Hypervisor/Add-ons, Speedtest, Update-Zähler,
Router/Netz — :data:`STANDARD_AUSGESCHLOSSEN`), der Opt-in-Modus
(``track_mode == "labeled"``) wird in der Entdeckung ERNST GENOMMEN
(ohne ``kontinuum``-Label wird nichts angemeldet), und das Label
``kontinuum`` gewinnt in beiden Fällen gegen den Ausschluss.

Die Tests fahren die echte Entity-Registry des Test-Homes; der Thalamus
ist eine aufzeichnende Attrappe (geprüft wird, WER angemeldet wird).
"""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kontinuum import STANDARD_AUSGESCHLOSSEN, _discover_entities
from custom_components.kontinuum.const import DOMAIN


class ThalamusAttrappe:
    """Zeichnet register_entity-Aufrufe auf; nur was das Setup braucht."""

    def __init__(self):
        self.registriert = []
        self.entity_semantic = {}
        self._known_rooms = set()

    def register_entity(self, **kwargs):
        self.registriert.append(kwargs["entity_id"])
        self.entity_semantic[kwargs["entity_id"]] = kwargs.get("domain", "")
        raum = kwargs.get("ha_area") or ""
        if raum:
            self._known_rooms.add(raum)


def _entry(hass, track_mode="standard"):
    mock = MockConfigEntry(domain=DOMAIN, title="K", data={"track_mode": track_mode})
    mock.add_to_hass(hass)
    return mock


@pytest.fixture
async def registry(hass):
    """Vier Bewohner, vier Betriebsgeräte, zwei Marken."""
    from homeassistant.helpers.entity_registry import async_get as get_er
    from homeassistant.helpers.label_registry import async_get as get_lr

    er = get_er(hass)
    lr = get_lr(hass)
    bewohner = er.async_get_or_create(
        "sensor", "mqtt", "wohnzimmer_temperatur",
        original_name="Wohnzimmer Temperatur",
    )
    alarm = er.async_get_or_create(
        "sensor", "mqtt", "keller_alarm", original_name="Keller Alarm",
    )
    betriebs = er.async_get_or_create(
        "sensor", "system_monitor", "cpu_last", original_name="CPU Last",
    )
    router = er.async_get_or_create(
        "sensor", "fritz", "verkehr", original_name="Fritzbox Verkehr",
    )
    marke = lr.async_create("kontinuum")
    er.async_update_entity(bewohner.entity_id, labels=[marke.label_id])
    return {"bewohner": bewohner, "alarm": alarm,
            "betriebs": betriebs, "router": router}


@pytest.mark.asyncio
async def test_standard_schliesst_betriebspersonal_aus(hass, registry):
    thalamus = ThalamusAttrappe()
    await _discover_entities(hass, thalamus, _entry(hass, "standard"))
    assert "sensor.mqtt_wohnzimmer_temperatur" in thalamus.registriert
    assert "sensor.mqtt_keller_alarm" in thalamus.registriert
    # Das Betriebspersonal: Systemüberwachung und Router bleiben draußen.
    assert "sensor.system_monitor_cpu_last" not in thalamus.registriert
    assert "sensor.fritz_verkehr" not in thalamus.registriert


@pytest.mark.asyncio
async def test_opt_in_nimmt_nur_markierte(hass, registry):
    thalamus = ThalamusAttrappe()
    await _discover_entities(hass, thalamus, _entry(hass, "labeled"))
    assert thalamus.registriert == ["sensor.mqtt_wohnzimmer_temperatur"]


@pytest.mark.asyncio
async def test_label_gewinnt_gegen_ausschluss(hass, registry):
    """Wer ein Betriebsgerät mit ``kontinuum`` markiert, will es lernen."""
    from homeassistant.helpers.entity_registry import async_get as get_er
    from homeassistant.helpers.label_registry import async_get as get_lr

    er = get_er(hass)
    lr = get_lr(hass)
    marke = lr.async_create("kontinuum")
    er.async_update_entity(
        registry["betriebs"].entity_id, labels=[marke.label_id],
    )
    thalamus = ThalamusAttrappe()
    await _discover_entities(hass, thalamus, _entry(hass, "standard"))
    assert "sensor.system_monitor_cpu_last" in thalamus.registriert


@pytest.mark.asyncio
async def test_ohne_entry_gilt_der_standard(hass, registry):
    """Der alte Aufruf (ohne Entry) schließt ebenso aus — kein stilles
    Zurückfallen auf das alte Alles-Lernen."""
    thalamus = ThalamusAttrappe()
    await _discover_entities(hass, thalamus)
    assert "sensor.mqtt_wohnzimmer_temperatur" in thalamus.registriert
    assert "sensor.system_monitor_cpu_last" not in thalamus.registriert


def test_die_ausschlussliste_ist_nur_maschine():
    """Wachswache gegen Übergriffe: alles in der Liste ist Betriebsgerät —
    keine Bewohner-Domänen (Licht, Klima, Anwesenheit) dürfen hier stehen."""
    for fremd in ("light", "climate", "person", "device_tracker", "switch",
                  "mqtt", "hue", "zwave_js"):
        assert fremd not in STANDARD_AUSGESCHLOSSEN
