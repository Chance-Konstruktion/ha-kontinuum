"""
KONTINUUM – Native Sensor Platform (v0.14.0)

Alle KONTINUUM-Sensoren als echte HA-Entitäten.
Ersetzt sowohl hass.states.async_set() als auch die template-Sensoren
aus der configuration.yaml. Entitäten werden automatisch erstellt und
beim Entfernen der Integration wieder gelöscht.
"""

import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

DOMAIN = "kontinuum"
SIGNAL_SENSORS_UPDATE = f"{DOMAIN}_sensors_update"
SIGNAL_PERSONS_UPDATE = f"{DOMAIN}_persons_update"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensor-Plattform einrichten."""
    brain = hass.data[DOMAIN]

    sensors = [
        KontinuumStatusSensor(brain, entry),
        KontinuumEventsSensor(brain, entry),
        KontinuumAccuracySensor(brain, entry),
        KontinuumModeSensor(brain, entry),
        KontinuumRoomSensor(brain, entry),
        KontinuumLastEventSensor(brain, entry),
        KontinuumPredictionSensor(brain, entry),
        KontinuumEnergySensor(brain, entry),
        KontinuumLocationSensor(brain, entry),
        KontinuumCerebellumSensor(brain, entry),
        KontinuumBasalGangliaSensor(brain, entry),
        KontinuumPersonsSensor(brain, entry),
        KontinuumUnknownEntitiesSensor(brain, entry),
        # ── Aktivitäts-Sensoren (ersetzen template-Sensoren) ──
        KontinuumActivitySensor(brain, entry, "thalamus", "mdi:transit-connection-variant"),
        KontinuumActivitySensor(brain, entry, "hippocampus", "mdi:head-lightbulb"),
        KontinuumActivitySensor(brain, entry, "hypothalamus", "mdi:thermometer-lines"),
        KontinuumActivitySensor(brain, entry, "amygdala", "mdi:shield-alert"),
        KontinuumActivitySensor(brain, entry, "insula", "mdi:head-heart"),
        KontinuumActivitySensor(brain, entry, "cerebellum", "mdi:cog-transfer"),
        KontinuumActivitySensor(brain, entry, "prefrontal", "mdi:head-cog"),
        KontinuumActivitySensor(brain, entry, "spatial", "mdi:map-marker-radius"),
        KontinuumActivitySensor(brain, entry, "basalganglia", "mdi:arrow-decision"),
    ]

    async_add_entities(sensors)
    _LOGGER.info("KONTINUUM: %d Sensoren als native Entitäten erstellt", len(sensors))


# ══════════════════════════════════════════════════════════════════
# BASE CLASS
# ══════════════════════════════════════════════════════════════════

class KontinuumSensorBase(SensorEntity):
    """Basisklasse für KONTINUUM Sensoren."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, brain: dict, entry: ConfigEntry, key: str,
                 name: str, icon: str):
        self._brain = brain
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._signal = SIGNAL_SENSORS_UPDATE

    async def async_added_to_hass(self) -> None:
        """Dispatcher-Signal verbinden."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self, **kwargs) -> None:
        """Sensor-Update bei Signal."""
        self.async_write_ha_state()


# ══════════════════════════════════════════════════════════════════
# SYSTEM SENSORS
# ══════════════════════════════════════════════════════════════════

class KontinuumStatusSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "status",
                         "KONTINUUM Status", "mdi:brain")

    @property
    def native_value(self):
        return "learning"

    @property
    def extra_state_attributes(self):
        from . import VERSION
        cerebellum = self._brain["cerebellum"]
        return {
            "version": VERSION,
            "preset": self._brain.get("preset", "?"),
            "rules": len(cerebellum.rules),
        }


class KontinuumEventsSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "events",
                         "KONTINUUM Events", "mdi:counter")
        self._attr_native_unit_of_measurement = "events"

    @property
    def native_value(self):
        return self._brain["hippocampus"].total_events


class KontinuumAccuracySensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "accuracy",
                         "KONTINUUM Accuracy", "mdi:target")

    @property
    def native_value(self):
        return f"{self._brain['hippocampus'].accuracy:.1%}"

    @property
    def extra_state_attributes(self):
        hp = self._brain["hippocampus"]
        return {
            "hits": hp.shadow_hits,
            "misses": hp.shadow_misses,
            "total": hp.shadow_total,
            "accuracy_by_window": hp.stats.get("accuracy_by_window", {}),
        }


class KontinuumModeSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "mode",
                         "KONTINUUM Modus", "mdi:home-automation")

    @property
    def native_value(self):
        return self._brain["insula"].current_mode

    @property
    def extra_state_attributes(self):
        return {
            "confidence": self._brain["insula"].stats.get("confidence", 0),
        }


class KontinuumRoomSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "room",
                         "KONTINUUM Raum", "mdi:map-marker")

    @property
    def native_value(self):
        return self._brain["spatial"].get_current_location()


class KontinuumLastEventSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "last_event",
                         "Letztes Event", "mdi:lightning-bolt")
        self._last_signal = None

    @callback
    def _handle_update(self, **kwargs):
        if "last_signal" in kwargs:
            self._last_signal = kwargs["last_signal"]
        self.async_write_ha_state()

    @property
    def native_value(self):
        if self._last_signal:
            return self._last_signal.get("token", "?")
        return "startup"

    @property
    def extra_state_attributes(self):
        s = self._last_signal or {}
        return {
            "token": s.get("token", ""),
            "room": s.get("room", ""),
            "semantic": s.get("semantic", ""),
            "entity_id": s.get("entity_id", ""),
        }


class KontinuumPredictionSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "prediction",
                         "Vorhersage", "mdi:crystal-ball")
        self._predictions = None

    @callback
    def _handle_update(self, **kwargs):
        if "predictions" in kwargs:
            self._predictions = kwargs["predictions"]
        self.async_write_ha_state()

    @property
    def native_value(self):
        if self._predictions:
            thalamus = self._brain["thalamus"]
            return thalamus.decode_token(self._predictions[0][0])
        return "waiting"

    @property
    def extra_state_attributes(self):
        if not self._predictions:
            return {"confidence": 0, "token": "", "source": "", "observations": 0}
        thalamus = self._brain["thalamus"]
        top = self._predictions[0]
        tok_id, prob, conf, src = top[:4]
        n_obs = top[4] if len(top) > 4 else 0
        return {
            "confidence": conf,
            "probability": prob,
            "token": thalamus.decode_token(tok_id),
            "source": src,
            "observations": n_obs,
            "alternatives": [
                {
                    "token": thalamus.decode_token(p[0]),
                    "conf": p[2],
                    "observations": p[4] if len(p) > 4 else 0,
                }
                for p in self._predictions[1:3]
            ],
        }


class KontinuumEnergySensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "energy",
                         "Energie", "mdi:battery")

    @property
    def native_value(self):
        return self._brain["hypothalamus"].get_energy_summary().get("battery", "?")

    @property
    def extra_state_attributes(self):
        return self._brain["hypothalamus"].get_energy_summary()


class KontinuumLocationSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "location",
                         "Standort", "mdi:crosshairs-gps")

    @property
    def native_value(self):
        return self._brain["spatial"].get_current_location()

    @property
    def extra_state_attributes(self):
        spatial = self._brain["spatial"]
        next_room = spatial.predict_next_room()
        return {
            "presence_map": spatial.stats.get("presence_map", {}),
            "predicted_next": next_room[0] if next_room else None,
            "movement_patterns": len(spatial.movement_memory),
        }


class KontinuumCerebellumSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "cerebellum",
                         "Cerebellum", "mdi:cog-transfer")

    @property
    def native_value(self):
        return f"{len(self._brain['cerebellum'].rules)} Regeln"

    @property
    def extra_state_attributes(self):
        cb = self._brain["cerebellum"]
        return {
            "rules_count": len(cb.rules),
            "rules_1gram": cb.stats.get("rules_1gram", 0),
            "rules_2gram": cb.stats.get("rules_2gram", 0),
            "rules_3gram": cb.stats.get("rules_3gram", 0),
            "top_rules": cb.stats.get("top_rules", []),
        }


class KontinuumBasalGangliaSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "basal_ganglia",
                         "Basalganglien", "mdi:brain")

    @property
    def native_value(self):
        return f"{self._brain['basal_ganglia'].total_habits} Habits"

    @property
    def extra_state_attributes(self):
        bg = self._brain["basal_ganglia"]
        return {
            "total_updates": bg.total_updates,
            "total_habits": bg.total_habits,
            "go_actions": bg.stats.get("go_actions", 0),
            "nogo_actions": bg.stats.get("nogo_actions", 0),
            "dopamine_signal": bg.stats.get("dopamine_signal", 0),
            "q_entries": len(bg.q_values),
            "active_habits": bg.stats.get("active_habits", []),
        }


class KontinuumPersonsSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "persons_home",
                         "Personen Zuhause", "mdi:account-group")
        self._attr_native_unit_of_measurement = "Personen"
        self._home = []
        self._away = []
        self._signal = SIGNAL_PERSONS_UPDATE

    @callback
    def _handle_update(self, **kwargs):
        if "home" in kwargs:
            self._home = kwargs["home"]
        if "away" in kwargs:
            self._away = kwargs["away"]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Beide Signale verbinden."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._signal, self._handle_update
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SENSORS_UPDATE, self._handle_update
            )
        )

    @property
    def native_value(self):
        return len(self._home)

    @property
    def extra_state_attributes(self):
        return {"home": self._home, "away": self._away}


class KontinuumUnknownEntitiesSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "unknown_entities",
                         "Entities ohne Raum", "mdi:help-circle-outline")
        self._attr_native_unit_of_measurement = "Entities"

    @property
    def native_value(self):
        return len(self._brain["thalamus"]._unassigned_entities)

    @property
    def extra_state_attributes(self):
        thalamus = self._brain["thalamus"]
        unassigned = thalamus.get_unassigned_report(10)
        return {
            "top_unassigned": [
                {"entity_id": eid, "events": cnt, "semantic": sem,
                 "name": name, "suggested_room": sug}
                for eid, cnt, sem, name, sug in unassigned
            ],
        }


# ══════════════════════════════════════════════════════════════════
# AKTIVITÄTS-SENSOREN (ersetzen template-Sensoren + input_number)
# ══════════════════════════════════════════════════════════════════

# Aktivitäts-Berechnung pro Modul
_ACTIVITY_GETTERS = {
    "thalamus": lambda brain: min(1.0,
        brain["thalamus"].stats.get("events_processed", 0) /
        max(1, brain["hippocampus"].total_events) * 10
        if brain["hippocampus"].total_events > 0 else 0.0),
    "hippocampus": lambda brain:
        brain["hippocampus"].accuracy,
    "hypothalamus": lambda brain: min(1.0, sum(
        abs(v) for v in brain["hypothalamus"].get_energy_summary().values()
        if isinstance(v, (int, float))
    ) / 5.0),
    "amygdala": lambda brain:
        brain["amygdala"].stats.get("last_risk", 0.0)
        if hasattr(brain["amygdala"], "stats") else 0.0,
    "insula": lambda brain:
        brain["insula"].stats.get("confidence", 0.0),
    "cerebellum": lambda brain: min(1.0,
        len(brain["cerebellum"].rules) / 50.0),
    "prefrontal": lambda brain:
        brain["prefrontal"].stats.get("decision_rate", 0.0)
        if hasattr(brain["prefrontal"], "stats") else 0.0,
    "spatial": lambda brain: max(
        brain["spatial"].stats.get("presence_map", {}).values(), default=0.0
    ),
    "basalganglia": lambda brain: min(1.0,
        brain["basal_ganglia"].total_habits / 20.0),
}


class KontinuumActivitySensor(KontinuumSensorBase):
    """Aktivitäts-Sensor für ein Gehirnmodul (0.0 – 1.0)."""

    def __init__(self, brain, entry, module_key: str, icon: str):
        super().__init__(
            brain, entry,
            f"{module_key}_activity",
            f"kontinuum_{module_key}_activity",  # Ergibt entity_id sensor.kontinuum_*_activity
            icon,
        )
        # Entity-ID explizit setzen (kompatibel mit alten template-Sensoren)
        self.entity_id = f"sensor.kontinuum_{module_key}_activity"
        self._module_key = module_key

    @property
    def native_value(self):
        getter = _ACTIVITY_GETTERS.get(self._module_key)
        if getter:
            try:
                val = getter(self._brain)
                return round(float(val), 2)
            except Exception:
                return 0.0
        return 0.0

    @property
    def extra_state_attributes(self):
        return {"module": self._module_key}
