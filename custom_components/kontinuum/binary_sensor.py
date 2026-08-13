"""
KONTINUUM – Binary Sensor Platform (Observability, engine-only)

Stellt den adaptiven Anomalie-Zustand der Engine als echte HA-Binary-Entity
bereit: ``on``, sobald das aktuelle Surprise-Niveau die robuste (Median+MAD)
Anomalie-Schwelle des Predictive-Processing-Moduls überschreitet.

Liest ausschließlich aus dem Kern-Gehirn (``predictive``) – keine Cortex-/
LLM-Abhängigkeit. Spiegelt damit auf der Pro-Seite das ``binary_sensor.
kontinuum_lite_anomaly`` der Lite-Variante (gleiche Semantik, device_class
``problem``), sodass Automationen identisch reagieren können.
"""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Identisch zum Signal in sensor.py / __init__.py – wird bei jedem Event gefeuert.
SIGNAL_SENSORS_UPDATE = f"{DOMAIN}_sensors_update"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Binary-Sensor-Plattform einrichten."""
    brain = hass.data[DOMAIN]
    async_add_entities([KontinuumAnomalyBinarySensor(brain, entry)])
    _LOGGER.info("KONTINUUM: Anomalie-Binary-Sensor erstellt")


class KontinuumAnomalyBinarySensor(BinarySensorEntity):
    """An, wenn das aktuelle Surprise die adaptive Anomalie-Schwelle erreicht."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-decagram-outline"

    def __init__(self, brain: dict, entry: ConfigEntry):
        self._brain = brain
        self._attr_unique_id = f"{entry.entry_id}_anomaly"
        self._attr_name = "KONTINUUM Anomaly"
        self.entity_id = "binary_sensor.kontinuum_anomaly"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SENSORS_UPDATE, self._handle_update
            )
        )

    @callback
    def _handle_update(self, data=None) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        pred = self._brain.get("predictive")
        if not pred:
            return False
        return pred.current_surprise >= pred.anomaly_threshold()

    @property
    def extra_state_attributes(self):
        pred = self._brain.get("predictive")
        if not pred:
            return {}
        return {
            "current_surprise": round(pred.current_surprise, 3),
            "anomaly_threshold": round(pred.anomaly_threshold(), 3),
            "average_surprise": round(pred.get_average_surprise(), 3),
            "max_surprise": round(pred.max_surprise, 3),
            "total_surprises": pred.total_surprises,
        }
