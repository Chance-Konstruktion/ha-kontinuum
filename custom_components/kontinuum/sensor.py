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


SIGNAL_CORTEX_UPDATE = f"{DOMAIN}_cortex_update"


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
        KontinuumActivitySensor(brain, entry, "acc", "mdi:head-sync"),
        KontinuumActivitySensor(brain, entry, "sleepconsolidation", "mdi:power-sleep"),
    ]

    # ── Cortex Agent-Sensoren (1 pro konfiguriertem Agent) ────
    cortex = brain.get("cortex")
    if cortex and cortex.enabled:
        for i, agent in enumerate(cortex.agents, 1):
            sensors.append(
                KontinuumCortexAgentSensor(brain, entry, agent, slot=i)
            )

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
        self._sensor_key = key  # Für Dashboard-Discovery
        # entity_id explizit setzen – wird von HA als Vorschlag übernommen
        self.entity_id = f"sensor.kontinuum_{key}"


    async def async_added_to_hass(self) -> None:
        """Dispatcher-Signal verbinden."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self, data=None) -> None:
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
        hippocampus = self._brain["hippocampus"]
        thalamus = self._brain["thalamus"]
        spatial = self._brain["spatial"]
        insula = self._brain["insula"]
        amygdala = self._brain["amygdala"]
        prefrontal = self._brain["prefrontal"]
        hypothalamus = self._brain["hypothalamus"]
        cortex = self._brain["cortex"]
        attrs = {
            "version": VERSION,
            "preset": self._brain.get("preset", "?"),
            "rules": len(cerebellum.rules),
            "thalamus": {
                "entities_registered": len(thalamus.entity_semantic),
                "rooms_discovered": len(set(thalamus.entity_room.values()) - {"unknown"}),
            },
            "hippocampus": {
                "total_events": hippocampus.total_events,
                "patterns": hippocampus.stats.get("patterns", 0),
                "memory_kb": hippocampus.stats.get("memory_kb", 0),
            },
            "hypothalamus": {
                "events_absorbed": hypothalamus.stats.get("events_absorbed", 0),
            },
            "spatial": {
                "current_room": spatial.get_current_location(),
                "transitions_emitted": spatial.stats.get("transitions_emitted", 0),
            },
            "insula": {
                "current_mode": insula.current_mode,
                "mode_changes": insula.stats.get("mode_changes", 0),
            },
            "amygdala": {
                "total_vetoes": amygdala.stats.get("total_vetoes", 0),
                "learned_risks": amygdala.stats.get("learned_risks", 0),
            },
            "cerebellum": {
                "rules_count": len(cerebellum.rules),
                "total_fired": cerebellum.stats.get("total_fired", 0),
            },
            "prefrontal": {
                "total_decisions": prefrontal.total_decisions,
                "total_confirms": getattr(prefrontal, "total_confirms", 0),
                "overrides_detected": prefrontal.overrides_detected,
                "operation_mode": getattr(prefrontal, "operation_mode", "shadow"),
                "shadow_mode": prefrontal.shadow_mode,
                "activated_semantics": list(prefrontal.activated_semantics),
                "pending_confirms": len(getattr(prefrontal, "_pending_confirms", {})),
            },
            "basal_ganglia": self._brain["basal_ganglia"].stats,
        }
        # Aux-Module Statistiken
        sleep_con = self._brain.get("sleep_consolidation")
        if sleep_con:
            attrs["sleep_consolidation"] = sleep_con.to_dict()
        acc_mod = self._brain.get("acc")
        if acc_mod:
            attrs["anterior_cingulate"] = acc_mod.stats
        reticular = self._brain.get("reticular")
        if reticular:
            attrs["reticular"] = reticular.to_dict()
        locus_mod = self._brain.get("locus")
        if locus_mod:
            attrs["locus_coeruleus"] = locus_mod.to_dict()
        entorhinal = self._brain.get("entorhinal")
        if entorhinal:
            attrs["entorhinal"] = entorhinal.to_dict()
        predictive = self._brain.get("predictive")
        if predictive:
            attrs["predictive_processing"] = predictive.stats
        meta = self._brain.get("metaplasticity")
        if meta:
            attrs["metaplasticity"] = {
                "last_update": meta.data.get("last_update"),
                "modules_tracked": len(meta.data.get("module_params", {})),
            }
        neuro = self._brain.get("neurorhythms")
        if neuro:
            attrs["neurorhythms"] = neuro.stats
        consolidation = self._brain.get("_last_consolidation")
        if consolidation:
            attrs["last_consolidation"] = consolidation
        # Cortex-Info (wenn aktiv)
        if cortex.enabled:
            attrs["cortex"] = {
                "enabled": True,
                "agents": len(cortex.agents),
                "sequential_mode": cortex.sequential_mode,
                "discussion_rounds": cortex.discussion_rounds,
                "total_consultations": cortex.total_consultations,
                "total_discussions": cortex.total_discussions,
                "last_consensus": cortex.last_consensus or {},
            }
        # Letzter Brain Review
        review = self._brain.get("_last_brain_review")
        if review:
            attrs["last_brain_review"] = {
                "health_score": review.get("health_score", 0),
                "timestamp": review.get("timestamp"),
                "agents_consulted": review.get("agents_consulted", 0),
            }
        return attrs


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
                         "KONTINUUM Mode", "mdi:home-automation")

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
                         "KONTINUUM Room", "mdi:map-marker")

    @property
    def native_value(self):
        return self._brain["spatial"].get_current_location()


class KontinuumLastEventSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "last_event",
                         "KONTINUUM Last Event", "mdi:lightning-bolt")
        self._last_signal = None

    @callback
    def _handle_update(self, data=None):
        if isinstance(data, dict) and "last_signal" in data:
            self._last_signal = data["last_signal"]
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
            "events_total": self._brain["hippocampus"].total_events,
        }


class KontinuumPredictionSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "prediction",
                         "KONTINUUM Prediction", "mdi:crystal-ball")
        self._predictions = None

    @callback
    def _handle_update(self, data=None):
        if isinstance(data, dict) and "predictions" in data:
            self._predictions = data["predictions"]
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
                         "KONTINUUM Energy", "mdi:battery")

    @property
    def native_value(self):
        return self._brain["hypothalamus"].get_energy_summary().get("battery", "?")

    @property
    def extra_state_attributes(self):
        return self._brain["hypothalamus"].get_energy_summary()


class KontinuumLocationSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "location",
                         "KONTINUUM Location", "mdi:crosshairs-gps")

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
                         "KONTINUUM Cerebellum", "mdi:cog-transfer")

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
            "rules_4gram": cb.stats.get("rules_4gram", 0),
            "top_rules": cb.stats.get("top_rules", []),
        }


class KontinuumBasalGangliaSensor(KontinuumSensorBase):
    def __init__(self, brain, entry):
        super().__init__(brain, entry, "basal_ganglia",
                         "KONTINUUM Basal Ganglia", "mdi:brain")

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
                         "KONTINUUM Persons Home", "mdi:account-group")
        self._attr_native_unit_of_measurement = "Personen"
        self._home = []
        self._away = []
        self._signal = SIGNAL_PERSONS_UPDATE

    @callback
    def _handle_update(self, data=None):
        if isinstance(data, dict):
            if "home" in data:
                self._home = data["home"]
            if "away" in data:
                self._away = data["away"]
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
                         "KONTINUUM Unknown Entities", "mdi:help-circle-outline")
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
    "acc": lambda brain:
        brain["acc"].conflict_level if brain.get("acc") else 0.0,
    "sleepconsolidation": lambda brain: min(1.0,
        brain["sleep_consolidation"].total_consolidations / 10.0)
        if brain.get("sleep_consolidation") else 0.0,
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


# ══════════════════════════════════════════════════════════════════
# CORTEX AGENT-SENSOREN (1 pro konfiguriertem Agent)
# ══════════════════════════════════════════════════════════════════

AGENT_ROLE_ICONS = {
    "comfort": "mdi:sofa",
    "energy": "mdi:solar-power",
    "safety": "mdi:shield-check",
    "custom": "mdi:robot",
}


class KontinuumCortexAgentSensor(KontinuumSensorBase):
    """
    Status-Sensor für einen einzelnen Cortex-Agent.

    Zeigt: Provider, Modell, Aufrufe, Fehlerrate, letzter Call.
    State: "active" / "idle" / "error" / "disabled"
    """

    def __init__(self, brain, entry, agent, slot: int):
        icon = AGENT_ROLE_ICONS.get(agent.name, "mdi:robot")
        super().__init__(
            brain, entry,
            f"cortex_agent_{slot}",
            f"Cortex Agent {slot} ({agent.name})",
            icon,
        )
        self._agent = agent
        self._slot = slot
        self._signal = SIGNAL_CORTEX_UPDATE

    async def async_added_to_hass(self) -> None:
        """Beide Signale verbinden (Cortex + allgemein)."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CORTEX_UPDATE, self._handle_update
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SENSORS_UPDATE, self._handle_update
            )
        )

    @property
    def native_value(self):
        agent = self._agent
        if agent.total_errors > 0 and agent.total_calls > 0:
            error_rate = agent.total_errors / agent.total_calls
            if error_rate > 0.5:
                return "error"
        if agent.total_calls == 0:
            return "idle"
        # Aktiv wenn letzter Call < 10min her
        import time
        if time.time() - agent.last_call_time < 600:
            return "active"
        return "idle"

    @property
    def extra_state_attributes(self):
        agent = self._agent
        import time
        last_ago = ""
        if agent.last_call_time > 0:
            secs = int(time.time() - agent.last_call_time)
            if secs < 60:
                last_ago = f"{secs}s ago"
            elif secs < 3600:
                last_ago = f"{secs // 60}m ago"
            else:
                last_ago = f"{secs // 3600}h ago"

        return {
            "slot": self._slot,
            "role": agent.name,
            "provider": agent.provider,
            "model": agent.model,
            "url": agent.url,
            "total_calls": agent.total_calls,
            "total_errors": agent.total_errors,
            "error_rate": (
                f"{agent.total_errors / max(1, agent.total_calls):.0%}"
            ),
            "last_call": last_ago,
        }
