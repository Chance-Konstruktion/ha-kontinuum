"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM v0.12.0 – Neuroinspired Home Intelligence           ║
║  Home Assistant Custom Component                                 ║
║                                                                  ║
║  Architektur:                                                    ║
║  Thalamus → Hippocampus → Cerebellum → PFC → Aktion           ║
║      ↑           ↑                       ↑                      ║
║  Hypothalamus  Spatial Cortex        Amygdala                   ║
║      ↑           ↑                                              ║
║    Insula ←─────┘                                               ║
║                                                                  ║
║  v0.12.0 – Intelligenz-Upgrade:                                ║
║  • Sonnenstand im Kontextvektor (sun.sun)                      ║
║  • Hypothalamus-Trends (Δtemp, Δbattery, Δsolar)             ║
║  • Wochentag-Gedächtnis (Werktag vs Wochenende Buckets)       ║
║  • Bewegungsmuster im Spatial Cortex                           ║
║  • Zirkadiane Priors in der Insula                             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import logging
import os
import time
from collections import Counter, deque
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_STOP
from homeassistant import config_entries

from .thalamus import Thalamus
from .hippocampus import Hippocampus
from .hypothalamus import Hypothalamus
from .spatial_cortex import SpatialCortex
from .insula import Insula
from .amygdala import Amygdala
from .cerebellum import Cerebellum
from .prefrontal_cortex import PrefrontalCortex

from .config_flow import PRESETS

_LOGGER = logging.getLogger(__name__)
DOMAIN = "kontinuum"
VERSION = "0.12.0"
BRAIN_FILE = "brain.json"
SAVE_INTERVAL = 300


# ══════════════════════════════════════════════════════════════════
# ASYNC-SAFE HELPERS
# ══════════════════════════════════════════════════════════════════

def _notify(hass, title, message, notification_id):
    """Async-safe Notification (fire-and-forget)."""
    hass.async_create_task(
        hass.services.async_call("persistent_notification", "create", {
            "title": title,
            "message": message,
            "notification_id": notification_id,
        })
    )


def _async_service_call(hass, domain, service, data):
    """Async-safe Service-Call (fire-and-forget)."""
    hass.async_create_task(
        hass.services.async_call(domain, service, data)
    )


# ══════════════════════════════════════════════════════════════════
# SETUP – Config Flow Entry Point
# ══════════════════════════════════════════════════════════════════

async def async_setup(hass: HomeAssistant, config: dict):
    """YAML-basiertes Setup (Rückwärtskompatibel)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Config-Flow-basiertes Setup – Haupteinstieg."""
    try:
        _LOGGER.info("KONTINUUM v%s wird initialisiert...", VERSION)

        # ── Preset laden ──────────────────────────────────────
        preset_key = entry.data.get("preset", "ausgeglichen")
        preset = PRESETS.get(preset_key, PRESETS["ausgeglichen"])
        config_data = {**preset, **entry.data}

        # ── Module initialisieren ─────────────────────────────
        thalamus = Thalamus()
        hippocampus = Hippocampus()
        hypothalamus = Hypothalamus()
        spatial = SpatialCortex()
        insula = Insula()
        amygdala = Amygdala()
        cerebellum = Cerebellum()
        prefrontal = PrefrontalCortex(amygdala)

        # ── Presets anwenden ──────────────────────────────────
        cerebellum.MIN_OBSERVATIONS = config_data.get("cerebellum_min_obs", 5)
        cerebellum.MIN_CONFIDENCE = config_data.get("cerebellum_min_conf", 0.75)
        hippocampus.DECAY_RATE = config_data.get("hippocampus_decay", 0.993)
        hippocampus.MIN_OBSERVATIONS = config_data.get("hippocampus_min_obs", 3)
        prefrontal.shadow_mode = config_data.get("shadow_mode", True)

        _LOGGER.info(
            "Preset '%s': Cerebellum(obs=%d, conf=%.0f%%), "
            "Hippocampus(decay=%.3f, obs=%d), Shadow=%s",
            preset_key, cerebellum.MIN_OBSERVATIONS,
            cerebellum.MIN_CONFIDENCE * 100,
            hippocampus.DECAY_RATE, hippocampus.MIN_OBSERVATIONS,
            prefrontal.shadow_mode,
        )

        # ── Brain-Dict ────────────────────────────────────────
        brain = {
            "thalamus": thalamus,
            "hippocampus": hippocampus,
            "hypothalamus": hypothalamus,
            "spatial": spatial,
            "insula": insula,
            "amygdala": amygdala,
            "cerebellum": cerebellum,
            "prefrontal": prefrontal,
            "preset": preset_key,
            "_scenes_enabled": False,
            "_scene_config": _default_scene_config(),
            "_notified_modes": set(),
            "_notified_rules": set(),
            "_notified_milestones": set(),
            "_last_compile": 0,
            "_last_save": time.time(),
            "_last_persons_update": 0,
        }

        # ── Gehirn laden ──────────────────────────────────────
        brain_path = hass.config.path(BRAIN_FILE)
        await hass.async_add_executor_job(_load_brain, brain, brain_path)

        # ── Entities entdecken ────────────────────────────────
        await _discover_entities(hass, thalamus)

        # ── Sensoren erstellen ────────────────────────────────
        _create_sensors(hass, brain)

        # ── Services registrieren ─────────────────────────────
        _register_services(hass, brain)

        # ── Event-Listener ────────────────────────────────────
        @callback
        def on_state_changed(event):
            """Hauptverarbeitungsloop – wird bei jedem State-Change aufgerufen."""
            try:
                entity_id = event.data.get("entity_id", "")
                new_state_obj = event.data.get("new_state")
                old_state_obj = event.data.get("old_state")

                if not new_state_obj or not old_state_obj:
                    return

                new_state = new_state_obj.state
                old_state = old_state_obj.state

                if new_state == old_state:
                    return

                # KONTINUUM-eigene Sensoren ignorieren
                if entity_id.startswith("sensor.kontinuum_"):
                    return

                # Sonnenstand tracken (v0.12.0)
                if entity_id == "sun.sun":
                    elevation = new_state_obj.attributes.get("elevation", 0)
                    is_daylight = new_state == "above_horizon"
                    thalamus.update_sun(elevation, is_daylight)
                    insula.update_sun(is_daylight)
                    return

                now = datetime.now(timezone.utc)
                semantic = thalamus.entity_semantic.get(entity_id)
                room = thalamus.entity_room.get(entity_id, "unknown")

                if not semantic:
                    # v0.12.1: Events von unassigned Entities zählen
                    thalamus.track_unassigned_event(entity_id)
                    return

                # ── Override-Erkennung ────────────────────────
                if prefrontal.is_own_action(entity_id):
                    return
                prefrontal.check_override(entity_id, new_state, amygdala)
                prefrontal.check_implicit_positives(amygdala)

                # ── Hypothalamus (Energie/Klima) ──────────────
                if hypothalamus.is_hypothalamus_signal(semantic):
                    transition = hypothalamus.absorb(room, semantic, new_state, entity_id)
                    if transition:
                        _inject_token(hass, brain, transition, now)
                    return

                # ── Spatial Cortex (Raum) ─────────────────────
                if spatial.is_spatial_signal(semantic):
                    tokens = spatial.absorb(room, semantic, new_state, entity_id)
                    for tok in tokens:
                        _inject_token(hass, brain, tok, now)

                    # Insula mit räumlichem Signal füttern
                    mode_result = insula.process(semantic, new_state, room)
                    if mode_result:
                        old_mode = brain.get("_last_mode", "active")
                        new_mode = mode_result["state"]
                        brain["_last_mode"] = new_mode
                        _on_mode_changed(hass, brain, old_mode, new_mode)
                    return

                # ── Thalamus (Token erzeugen) ─────────────────
                signal = thalamus.process(entity_id, new_state, old_state, now)
                if not signal:
                    return

                token_id = signal["token_id"]

                # Insula füttern
                mode_result = insula.process(semantic, signal["state"], room)
                if mode_result:
                    old_mode = brain.get("_last_mode", "active")
                    new_mode = mode_result["state"]
                    brain["_last_mode"] = new_mode
                    _on_mode_changed(hass, brain, old_mode, new_mode)

                # Kontextvektor bauen (21 Dimensionen: time(9) + hypo(9) + insula(3))
                time_ctx = thalamus.encode_time_context(now)
                hypo_ctx = hypothalamus.get_context_vector()
                mode_ctx = insula.get_mode_context()
                ctx = time_ctx + hypo_ctx + mode_ctx

                # Hippocampus lernt
                hippocampus.learn(token_id, ctx, now)

                # Predictions
                predictions = hippocampus.predict(ctx)

                # PFC entscheidet
                decision = prefrontal.evaluate(predictions, thalamus)
                if decision:
                    _process_decision(hass, brain, decision)

                # Sensoren updaten
                _update_sensors(hass, brain, last_signal=signal, predictions=predictions)

                # Periodisch: Cerebellum kompilieren + speichern
                now_ts = time.time()
                if now_ts - brain["_last_compile"] > 600:
                    old_count = len(cerebellum.rules)
                    cerebellum.compile_rules(hippocampus)
                    new_count = len(cerebellum.rules)
                    brain["_last_compile"] = now_ts

                    if new_count > old_count:
                        _notify_new_rules(hass, brain, new_count - old_count, new_count)

                    _check_accuracy_milestone(hass, brain)

                if now_ts - brain["_last_save"] > SAVE_INTERVAL:
                    hass.async_add_executor_job(_save_brain, brain, brain_path)
                    brain["_last_save"] = now_ts

                # Personen-Zähler
                if now_ts - brain["_last_persons_update"] > 30:
                    _update_persons_sensor(hass, brain)
                    brain["_last_persons_update"] = now_ts

            except Exception as e:
                _LOGGER.error("KONTINUUM Fehler: %s", e, exc_info=True)

        hass.bus.async_listen(EVENT_STATE_CHANGED, on_state_changed)

        # ── Shutdown-Handler ──────────────────────────────────
        async def on_shutdown(event):
            _LOGGER.info("KONTINUUM wird heruntergefahren – speichere Gehirn...")
            await hass.async_add_executor_job(_save_brain, brain, brain_path)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_shutdown)

        # ── In hass.data speichern ────────────────────────────
        hass.data[DOMAIN] = brain

        _LOGGER.info(
            "KONTINUUM v%s gestartet: %d Entities, %d Tokens, %d Räume, Preset '%s'",
            VERSION,
            len(thalamus.entity_semantic),
            thalamus._next_id - 1,
            len(thalamus._known_rooms),
            preset_key,
        )

        # Sonnenstand initial laden (v0.12.0)
        sun_state = hass.states.get("sun.sun")
        if sun_state:
            elevation = sun_state.attributes.get("elevation", 0)
            is_daylight = sun_state.state == "above_horizon"
            thalamus.update_sun(elevation, is_daylight)
            insula.update_sun(is_daylight)
            _LOGGER.info("Sonnenstand geladen: elevation=%.1f°, daylight=%s", elevation, is_daylight)

        # Startup-Notification
        filtered = thalamus.stats.get("entities_filtered", 0)
        movement_count = len(spatial.movement_memory)
        _notify(hass,
            f"🧠 KONTINUUM v{VERSION} gestartet",
            f"Preset: **{preset_key}**\n"
            f"Entities: {len(thalamus.entity_semantic)}"
            f"{f' (+ {filtered} ohne Raum gefiltert)' if filtered else ''}\n"
            f"Tokens: {thalamus._next_id - 1}\n"
            f"Räume: {len(thalamus._known_rooms)}\n"
            f"Events bisher: {hippocampus.total_events}\n"
            f"Accuracy: {hippocampus.accuracy:.1%}\n"
            f"Bewegungsmuster: {movement_count}\n"
            f"Kontextvektor: 21 Dimensionen (Sonne + Trends)",
            "kontinuum_startup",
        )

        # v0.12.1: Unassigned Entities Notification
        _notify_unassigned_entities(hass, thalamus)

        return True

    except Exception as e:
        _LOGGER.error("KONTINUUM Setup fehlgeschlagen: %s", e, exc_info=True)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Entlädt KONTINUUM und speichert das Gehirn."""
    brain = hass.data.get(DOMAIN)
    if brain:
        brain_path = hass.config.path(BRAIN_FILE)
        await hass.async_add_executor_job(_save_brain, brain, brain_path)
    _LOGGER.info("KONTINUUM entladen und gespeichert.")
    return True


# ══════════════════════════════════════════════════════════════════
# TOKEN INJECTION
# ══════════════════════════════════════════════════════════════════

def _inject_token(hass, brain, token_info, timestamp):
    """Injiziert einen synthetischen Token ins System."""
    thalamus = brain["thalamus"]
    hippocampus = brain["hippocampus"]
    hypothalamus = brain["hypothalamus"]
    insula = brain["insula"]

    token_str = token_info["token"]
    if token_str not in thalamus.token_to_id:
        thalamus.token_to_id[token_str] = thalamus._next_id
        thalamus.id_to_token[thalamus._next_id] = token_str
        thalamus._next_id += 1

    token_id = thalamus.token_to_id[token_str]

    time_ctx = thalamus.encode_time_context(timestamp)
    hypo_ctx = hypothalamus.get_context_vector()
    mode_ctx = insula.get_mode_context()
    ctx = time_ctx + hypo_ctx + mode_ctx

    hippocampus.learn(token_id, ctx, timestamp)


# ══════════════════════════════════════════════════════════════════
# DECISION PROCESSING
# ══════════════════════════════════════════════════════════════════

def _process_decision(hass, brain, decision):
    """Verarbeitet eine PFC-Entscheidung."""
    if decision.stage == "SUGGEST":
        _notify(hass,
            "🧠 KONTINUUM – Vorschlag",
            f"KONTINUUM würde gerne **{decision.token}** ausführen.\n"
            f"Confidence: {decision.confidence:.0%} | "
            f"Risiko: {decision.risk:.2f}\n"
            f"Quelle: {decision.source}\n\n"
            f"(Noch im Lernmodus – keine Aktion)",
            "kontinuum_suggest",
        )


# ══════════════════════════════════════════════════════════════════
# MODE CHANGED – Events, Notifications, Szenen
# ══════════════════════════════════════════════════════════════════

def _on_mode_changed(hass, brain, old_mode, new_mode):
    """Wird aufgerufen wenn die Insula den Modus wechselt."""
    insula = brain["insula"]

    hass.bus.async_fire("kontinuum_mode_changed", {
        "old_mode": old_mode,
        "new_mode": new_mode,
        "confidence": insula.stats.get("confidence", 0),
        "room": brain["spatial"].get_current_location(),
    })

    _LOGGER.info("Modus: %s → %s", old_mode, new_mode)

    notified = brain.get("_notified_modes", set())
    if new_mode not in notified:
        notified.add(new_mode)
        _notify(hass,
            "🧠 KONTINUUM – Neuer Modus erkannt",
            f"Zum ersten Mal Modus **{new_mode}** erkannt!\n"
            f"Vorher: {old_mode}\n"
            f"Raum: {brain['spatial'].get_current_location()}\n\n"
            f"Tipp: Du kannst HA-Automationen auf `kontinuum_mode_changed` auslösen.",
            f"kontinuum_mode_{new_mode}",
        )

    if brain.get("_scenes_enabled"):
        _apply_scene_for_mode(hass, brain, new_mode)


def _apply_scene_for_mode(hass, brain, mode):
    """Wendet Licht-Szene für den aktuellen Modus an."""
    config = brain.get("_scene_config", {})
    scene = config.get(mode)
    if not scene:
        return

    room = brain["spatial"].get_current_location()
    prefrontal = brain["prefrontal"]
    thalamus = brain["thalamus"]

    lights = [
        eid for eid, sem in thalamus.entity_semantic.items()
        if sem == "light" and thalamus.entity_room.get(eid) == room
    ]

    for light_id in lights:
        try:
            if scene.get("state") == "off":
                _async_service_call(hass, "light", "turn_off", {"entity_id": light_id})
                prefrontal.mark_own_action(light_id, token=f"{room}.light.off", semantic="light")
            else:
                data = {"entity_id": light_id}
                if "brightness_pct" in scene:
                    data["brightness_pct"] = scene["brightness_pct"]
                if "color_temp_kelvin" in scene:
                    data["color_temp_kelvin"] = scene["color_temp_kelvin"]
                elif "kelvin" in scene:
                    data["color_temp_kelvin"] = scene["kelvin"]
                _async_service_call(hass, "light", "turn_on", data)
                prefrontal.mark_own_action(light_id, token=f"{room}.light.on", semantic="light")
            _LOGGER.info("Szene '%s': %s", mode, light_id)
        except Exception as e:
            _LOGGER.error("Szene Fehler %s: %s", light_id, e)


def _default_scene_config():
    """Standard Licht-Szenen pro Modus."""
    return {
        "sleeping": {"state": "off"},
        "relaxing": {"state": "on", "brightness_pct": 30, "kelvin": 2700},
        "active": {"state": "on", "brightness_pct": 80, "kelvin": 4000},
        "waking_up": {"state": "on", "brightness_pct": 40, "kelvin": 3000},
    }


# ══════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════

def _notify_new_rules(hass, brain, new_count, total):
    """Benachrichtigung wenn Cerebellum neue Regeln gelernt hat."""
    thalamus = brain["thalamus"]
    cerebellum = brain["cerebellum"]
    notified = brain.get("_notified_rules", set())

    rules_text = []
    for rule_key in cerebellum.rules:
        if rule_key not in notified:
            notified.add(rule_key)
            parts = rule_key.split("_")
            if len(parts) == 2:
                t1 = thalamus.id_to_token.get(int(parts[0]), f"?{parts[0]}")
                t2 = thalamus.id_to_token.get(int(parts[1]), f"?{parts[1]}")
                rules_text.append(f"• {t1} → {t2}")

    if rules_text:
        _notify(hass,
            f"🧠 KONTINUUM – {len(rules_text)} neue Routine(n)!",
            "Gelernte Muster:\n\n" + "\n".join(rules_text[:10]) +
            f"\n\nGesamt: {total} Routinen",
            "kontinuum_rules",
        )


def _check_accuracy_milestone(hass, brain):
    """Prüft ob ein Accuracy-Milestone erreicht wurde."""
    hippocampus = brain["hippocampus"]
    acc = hippocampus.accuracy
    notified = brain.get("_notified_milestones", set())

    milestones = [
        (0.50, "50%", "KONTINUUM versteht schon die Hälfte deiner Muster!"),
        (0.75, "75%", "Drei von vier Events werden korrekt vorhergesagt!"),
        (0.90, "90%", "KONTINUUM kennt dein Haus fast perfekt!"),
    ]

    for threshold, label, msg in milestones:
        if acc >= threshold and label not in notified:
            notified.add(label)
            _notify(hass,
                f"🎯 KONTINUUM – {label} Genauigkeit!",
                f"{msg}\n\n{hippocampus.shadow_hits} von "
                f"{hippocampus.shadow_total} Vorhersagen korrekt.",
                f"kontinuum_accuracy_{label}",
            )


def _notify_unassigned_entities(hass, thalamus):
    """
    v0.12.1: Benachrichtigt über Entities ohne Raum mit Vorschlägen.
    Human-in-the-loop Learning – das System sagt was ihm fehlt.
    """
    report = thalamus.get_unassigned_report(5)
    if not report:
        return

    # Nur Entities mit Raum-Vorschlag oder hoher Aktivität anzeigen
    relevant = [
        (eid, cnt, sem, name, sug) for eid, cnt, sem, name, sug in report
        if sug or cnt > 0
    ]

    if not relevant:
        return

    lines = []
    for eid, cnt, sem, name, sug in relevant:
        # Klickbarer Link direkt zur Entity-Konfiguration
        link = f"[{name or eid}](/config/entities?search={eid})"
        if sug:
            lines.append(f"• {link} → Vorschlag: **{sug}**")
        else:
            lines.append(f"• {link} ({sem})")
        if cnt > 0:
            lines[-1] += f" – {cnt} Events"

    total = len(thalamus._unassigned_entities)

    _notify(hass,
        f"🧠 KONTINUUM – {total} Entities ohne Raum",
        f"Damit ich besser lernen kann, brauche ich Raum-Zuordnungen.\n\n"
        + "\n".join(lines) +
        f"\n\n**Tipp:** Klick auf eine Entity oben, um direkt den "
        f"Bereich zuzuweisen.",
        "kontinuum_unassigned",
    )


# ══════════════════════════════════════════════════════════════════
# SERVICES
# ══════════════════════════════════════════════════════════════════

def _register_services(hass, brain):
    """Registriert KONTINUUM Services in HA."""

    async def handle_enable_scenes(call):
        brain["_scenes_enabled"] = True
        _LOGGER.info("Licht-Szenen aktiviert")
        await hass.services.async_call("persistent_notification", "create", {
            "title": "🧠 KONTINUUM – Licht-Szenen aktiviert",
            "message": "Lichter werden nach Modus angepasst:\n\n"
                       "• **sleeping** → aus\n"
                       "• **relaxing** → 30%, 2700K\n"
                       "• **active** → 80%, 4000K\n"
                       "• **waking_up** → 40%, 3000K",
            "notification_id": "kontinuum_scenes",
        })

    async def handle_disable_scenes(call):
        brain["_scenes_enabled"] = False
        _LOGGER.info("Licht-Szenen deaktiviert")

    async def handle_set_scene(call):
        mode = call.data.get("mode", "")
        state = call.data.get("state", "on")
        brightness = call.data.get("brightness_pct")
        kelvin = call.data.get("kelvin")

        if mode not in brain["_scene_config"]:
            brain["_scene_config"][mode] = {}

        scene = brain["_scene_config"][mode]
        scene["state"] = state
        if brightness is not None:
            scene["brightness_pct"] = brightness
        if kelvin is not None:
            scene["kelvin"] = kelvin
        _LOGGER.info("Szene '%s' konfiguriert: %s", mode, scene)

    async def handle_status(call):
        hp = brain["hippocampus"]
        th = brain["thalamus"]
        sp = brain["spatial"]
        ins = brain["insula"]
        pf = brain["prefrontal"]
        cb = brain["cerebellum"]

        room_entities = {}
        for eid, room in th.entity_room.items():
            sem = th.entity_semantic.get(eid, "?")
            room_entities.setdefault(room, []).append(sem)

        room_summary = []
        for room in sorted(room_entities.keys()):
            entities = room_entities[room]
            counts = Counter(entities)
            items = ", ".join(f"{n}× {s}" for s, n in counts.most_common(5))
            room_summary.append(f"**{room}** ({len(entities)}): {items}")

        msg = (
            f"**Version:** {VERSION}\n"
            f"**Preset:** {brain.get('preset', '?')}\n"
            f"**Events:** {hp.total_events}\n"
            f"**Tokens:** {th._next_id}\n"
            f"**Entities:** {len(th.entity_semantic)}\n"
            f"**Accuracy:** {hp.accuracy:.1%}\n"
            f"**Modus:** {ins.current_mode}\n"
            f"**Raum:** {sp.get_current_location()}\n"
            f"**Routinen:** {len(cb.rules)}\n"
            f"**Entscheidungen:** {pf.total_decisions}\n"
            f"**Overrides:** {pf.overrides_detected}\n"
            f"**Szenen:** {'AN' if brain.get('_scenes_enabled') else 'AUS'}\n\n"
            f"**Räume:**\n" + "\n".join(room_summary[:15])
        )

        await hass.services.async_call("persistent_notification", "create", {
            "title": "🧠 KONTINUUM – Status",
            "message": msg,
            "notification_id": "kontinuum_status_detail",
        })

    hass.services.async_register(DOMAIN, "enable_scenes", handle_enable_scenes)
    hass.services.async_register(DOMAIN, "disable_scenes", handle_disable_scenes)
    hass.services.async_register(DOMAIN, "set_scene", handle_set_scene)
    hass.services.async_register(DOMAIN, "status", handle_status)

    _LOGGER.info("Services registriert: enable_scenes, disable_scenes, set_scene, status")


# ══════════════════════════════════════════════════════════════════
# ENTITY DISCOVERY
# ══════════════════════════════════════════════════════════════════

async def _discover_entities(hass, thalamus):
    """Entdeckt Entities aus HA-Registries."""
    try:
        from homeassistant.helpers.entity_registry import async_get as get_er
    except ImportError:
        from homeassistant.helpers import entity_registry
        get_er = entity_registry.async_get

    try:
        from homeassistant.helpers.area_registry import async_get as get_ar
    except ImportError:
        from homeassistant.helpers import area_registry
        get_ar = area_registry.async_get

    try:
        from homeassistant.helpers.device_registry import async_get as get_dr
    except ImportError:
        from homeassistant.helpers import device_registry
        get_dr = device_registry.async_get

    er = get_er(hass)
    ar = get_ar(hass)
    dr = get_dr(hass)

    areas = {a.id: a.name for a in ar.async_list_areas()}

    for entity in er.entities.values():
        entity_id = entity.entity_id
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        device_class = entity.device_class or entity.original_device_class or ""
        unit = entity.unit_of_measurement or ""
        name = entity.name or entity.original_name or entity_id

        area_name = ""
        if entity.area_id and entity.area_id in areas:
            area_name = areas[entity.area_id]
        elif entity.device_id:
            device = dr.async_get(entity.device_id)
            if device and device.area_id and device.area_id in areas:
                area_name = areas[device.area_id]

        thalamus.register_entity(
            entity_id=entity_id,
            ha_area=area_name,
            device_class=str(device_class) if device_class else "",
            domain=domain,
            friendly_name=str(name) if name else "",
            unit=str(unit) if unit else "",
        )

    _LOGGER.info(
        "Entity Discovery: %d Entities in %d Räumen registriert",
        len(thalamus.entity_semantic), len(thalamus._known_rooms),
    )


# ══════════════════════════════════════════════════════════════════
# SENSORS
# ══════════════════════════════════════════════════════════════════

def _create_sensors(hass, brain):
    """Erstellt KONTINUUM Sensoren (inkl. Dashboard-Sensoren)."""
    hippocampus = brain["hippocampus"]
    insula = brain["insula"]
    spatial = brain["spatial"]
    hypothalamus = brain["hypothalamus"]
    cerebellum = brain["cerebellum"]

    hass.states.async_set("sensor.kontinuum_status", "learning", {
        "friendly_name": "KONTINUUM Status", "icon": "mdi:brain",
        "version": VERSION, "preset": brain.get("preset", "?"),
    })
    hass.states.async_set("sensor.kontinuum_events", hippocampus.total_events, {
        "friendly_name": "KONTINUUM Events", "icon": "mdi:counter",
        "unit_of_measurement": "events",
    })
    hass.states.async_set("sensor.kontinuum_accuracy", f"{hippocampus.accuracy:.1%}", {
        "friendly_name": "KONTINUUM Accuracy", "icon": "mdi:target",
        "hits": hippocampus.shadow_hits, "misses": hippocampus.shadow_misses,
        "total": hippocampus.shadow_total,
    })
    hass.states.async_set("sensor.kontinuum_mode", insula.current_mode, {
        "friendly_name": "KONTINUUM Modus", "icon": "mdi:home-automation",
        "confidence": insula.stats.get("confidence", 0),
    })
    hass.states.async_set("sensor.kontinuum_room", spatial.get_current_location(), {
        "friendly_name": "KONTINUUM Raum", "icon": "mdi:map-marker",
    })
    # Dashboard-Sensoren
    hass.states.async_set("sensor.kontinuum_last_event", "startup", {
        "friendly_name": "Letztes Event", "icon": "mdi:lightning-bolt",
        "token": "", "room": "", "semantic": "",
    })
    hass.states.async_set("sensor.kontinuum_prediction", "waiting", {
        "friendly_name": "Vorhersage", "icon": "mdi:crystal-ball",
        "confidence": 0, "token": "", "source": "",
    })
    energy = hypothalamus.get_energy_summary()
    hass.states.async_set("sensor.kontinuum_energy", energy.get("battery", "?"), {
        "friendly_name": "Energie", "icon": "mdi:battery", **energy,
    })
    next_room = spatial.predict_next_room()
    hass.states.async_set("sensor.kontinuum_location", spatial.get_current_location(), {
        "friendly_name": "Standort", "icon": "mdi:crosshairs-gps",
        "presence_map": spatial.stats.get("presence_map", {}),
        "predicted_next": next_room[0] if next_room else None,
        "movement_patterns": len(spatial.movement_memory),
    })
    hass.states.async_set("sensor.kontinuum_cerebellum", f"{len(cerebellum.rules)} Regeln", {
        "friendly_name": "Cerebellum", "icon": "mdi:cog-transfer",
        "rules_count": len(cerebellum.rules),
        "top_rules": cerebellum.stats.get("top_rules", []),
    })
    hass.states.async_set("sensor.kontinuum_persons_home", 0, {
        "friendly_name": "Personen Zuhause", "icon": "mdi:account-group",
        "unit_of_measurement": "Personen", "home": [], "away": [],
    })
    # Unassigned Entities Sensor (v0.12.1)
    thalamus = brain["thalamus"]
    unassigned = thalamus.get_unassigned_report(10)
    hass.states.async_set("sensor.kontinuum_unknown_entities",
        len(thalamus._unassigned_entities), {
        "friendly_name": "Entities ohne Raum",
        "icon": "mdi:help-circle-outline",
        "unit_of_measurement": "Entities",
        "top_unassigned": [
            {"entity_id": eid, "events": cnt, "semantic": sem,
             "name": name, "suggested_room": sug}
            for eid, cnt, sem, name, sug in unassigned
        ],
    })


def _update_sensors(hass, brain, last_signal=None, predictions=None):
    """Aktualisiert KONTINUUM Sensoren (inkl. Dashboard)."""
    hippocampus = brain["hippocampus"]
    insula = brain["insula"]
    spatial = brain["spatial"]
    cerebellum = brain["cerebellum"]
    hypothalamus = brain["hypothalamus"]
    thalamus = brain["thalamus"]

    hass.states.async_set("sensor.kontinuum_status", "learning", {
        "friendly_name": "KONTINUUM Status", "icon": "mdi:brain",
        "version": VERSION, "preset": brain.get("preset", "?"),
        "rules": len(cerebellum.rules),
    })
    hass.states.async_set("sensor.kontinuum_events", hippocampus.total_events, {
        "friendly_name": "KONTINUUM Events", "icon": "mdi:counter",
        "unit_of_measurement": "events",
    })
    hass.states.async_set("sensor.kontinuum_accuracy", f"{hippocampus.accuracy:.1%}", {
        "friendly_name": "KONTINUUM Accuracy", "icon": "mdi:target",
        "hits": hippocampus.shadow_hits, "misses": hippocampus.shadow_misses,
        "total": hippocampus.shadow_total,
    })
    hass.states.async_set("sensor.kontinuum_mode", insula.current_mode, {
        "friendly_name": "KONTINUUM Modus", "icon": "mdi:home-automation",
        "confidence": insula.stats.get("confidence", 0),
    })
    hass.states.async_set("sensor.kontinuum_room", spatial.get_current_location(), {
        "friendly_name": "KONTINUUM Raum", "icon": "mdi:map-marker",
    })

    # Dashboard-Sensoren
    if last_signal:
        hass.states.async_set("sensor.kontinuum_last_event", last_signal.get("token", "?"), {
            "friendly_name": "Letztes Event", "icon": "mdi:lightning-bolt",
            "token": last_signal.get("token", ""),
            "room": last_signal.get("room", ""),
            "semantic": last_signal.get("semantic", ""),
            "entity_id": last_signal.get("entity_id", ""),
        })

    if predictions:
        top = predictions[0] if predictions else (0, 0, 0, "")
        tok_id, prob, conf, src = top
        hass.states.async_set("sensor.kontinuum_prediction",
            thalamus.decode_token(tok_id), {
            "friendly_name": "Vorhersage", "icon": "mdi:crystal-ball",
            "confidence": conf, "probability": prob,
            "token": thalamus.decode_token(tok_id), "source": src,
            "alternatives": [
                {"token": thalamus.decode_token(t), "conf": c}
                for t, p, c, s in predictions[1:3]
            ],
        })

    energy = hypothalamus.get_energy_summary()
    hass.states.async_set("sensor.kontinuum_energy", energy.get("battery", "?"), {
        "friendly_name": "Energie", "icon": "mdi:battery", **energy,
    })
    next_room = spatial.predict_next_room()
    hass.states.async_set("sensor.kontinuum_location", spatial.get_current_location(), {
        "friendly_name": "Standort", "icon": "mdi:crosshairs-gps",
        "presence_map": spatial.stats.get("presence_map", {}),
        "predicted_next": next_room[0] if next_room else None,
        "movement_patterns": len(spatial.movement_memory),
    })
    hass.states.async_set("sensor.kontinuum_cerebellum", f"{len(cerebellum.rules)} Regeln", {
        "friendly_name": "Cerebellum", "icon": "mdi:cog-transfer",
        "rules_count": len(cerebellum.rules),
        "top_rules": cerebellum.stats.get("top_rules", []),
    })
    # Unassigned Entities aktualisieren (v0.12.1)
    unassigned = thalamus.get_unassigned_report(10)
    hass.states.async_set("sensor.kontinuum_unknown_entities",
        len(thalamus._unassigned_entities), {
        "friendly_name": "Entities ohne Raum",
        "icon": "mdi:help-circle-outline",
        "unit_of_measurement": "Entities",
        "top_unassigned": [
            {"entity_id": eid, "events": cnt, "semantic": sem,
             "name": name, "suggested_room": sug}
            for eid, cnt, sem, name, sug in unassigned
        ],
    })


def _update_persons_sensor(hass, brain):
    """Aktualisiert den Personen-Zähler."""
    home_list = []
    away_list = []

    for state in hass.states.async_all("person"):
        name = state.attributes.get("friendly_name", state.entity_id)
        if state.state == "home":
            home_list.append(name)
        else:
            away_list.append(name)

    hass.states.async_set("sensor.kontinuum_persons_home", len(home_list), {
        "friendly_name": "Personen Zuhause",
        "icon": "mdi:account-group",
        "unit_of_measurement": "Personen",
        "home": home_list,
        "away": away_list,
    })


# ══════════════════════════════════════════════════════════════════
# BRAIN PERSISTENCE
# ══════════════════════════════════════════════════════════════════

def _save_brain(brain, path=None):
    """Speichert das Gehirn in eine JSON-Datei."""
    if not path:
        return

    try:
        data = {
            "version": VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "preset": brain.get("preset", "ausgeglichen"),
            "thalamus": brain["thalamus"].to_dict(),
            "hippocampus": brain["hippocampus"].to_dict(),
            "hypothalamus": brain["hypothalamus"].to_dict(),
            "spatial": brain["spatial"].to_dict(),
            "insula": brain["insula"].to_dict(),
            "amygdala": brain["amygdala"].to_dict(),
            "cerebellum": brain["cerebellum"].to_dict(),
            "prefrontal": brain["prefrontal"].to_dict(),
            "scenes_enabled": brain.get("_scenes_enabled", False),
            "scene_config": brain.get("_scene_config", {}),
        }

        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=1, default=str)
        os.replace(tmp_path, path)

        _LOGGER.debug("Gehirn gespeichert: %s", path)
    except Exception as e:
        _LOGGER.error("Fehler beim Speichern: %s", e)


def _load_brain(brain, path):
    """Lädt das Gehirn aus einer JSON-Datei."""
    if not os.path.exists(path):
        _LOGGER.info("Kein gespeichertes Gehirn gefunden – starte frisch.")
        return

    try:
        with open(path) as f:
            data = json.load(f)

        brain["thalamus"].from_dict(data.get("thalamus", {}))
        brain["hippocampus"].from_dict(data.get("hippocampus", {}))
        brain["hypothalamus"].from_dict(data.get("hypothalamus", {}))
        brain["spatial"].from_dict(data.get("spatial", {}))
        brain["insula"].from_dict(data.get("insula", {}))
        brain["amygdala"].from_dict(data.get("amygdala", {}))
        brain["cerebellum"].from_dict(data.get("cerebellum", {}))
        brain["prefrontal"].from_dict(data.get("prefrontal", {}))
        brain["_scenes_enabled"] = data.get("scenes_enabled", False)
        brain["_scene_config"] = data.get("scene_config", _default_scene_config())

        # v0.11.0 Migration: Unknown-Tokens bereinigen
        _migrate_purge_unknown(brain)

        hp = brain["hippocampus"]
        _LOGGER.info(
            "Gehirn geladen: %d Events, %d Tokens, Accuracy %s",
            hp.total_events, brain["thalamus"]._next_id - 1, hp.stats["accuracy"],
        )
    except Exception as e:
        _LOGGER.error("Fehler beim Laden: %s – starte frisch.", e)


def _migrate_purge_unknown(brain):
    """
    v0.11.0 Migration: Entfernt alle unknown-Tokens aus dem Gehirn.

    Bereinigt:
    1. Thalamus: entity_room/entity_semantic für unknown-Entities
    2. Thalamus: Token-Vokabular (unknown.* Tokens)
    3. Hippocampus: Transitions/Totals die unknown-Token-IDs referenzieren
    4. Hippocampus: Buffer von unknown-Token-IDs
    """
    thalamus = brain["thalamus"]
    hippocampus = brain["hippocampus"]

    # 1. Unknown-Token-IDs sammeln
    unknown_token_ids = set()
    unknown_tokens = set()
    for token_str, token_id in list(thalamus.token_to_id.items()):
        if token_str.startswith("unknown."):
            unknown_token_ids.add(token_id)
            unknown_tokens.add(token_str)

    if not unknown_token_ids:
        return

    # 2. Thalamus: Unknown-Entities entfernen
    unknown_entities = [
        eid for eid, room in thalamus.entity_room.items()
        if room == "unknown"
    ]
    for eid in unknown_entities:
        del thalamus.entity_room[eid]
        thalamus.entity_semantic.pop(eid, None)
        thalamus.entity_last_token.pop(eid, None)
    thalamus.stats["entities_registered"] = len(thalamus.entity_semantic)

    # 3. Thalamus: Token-Vokabular bereinigen
    for token_str in unknown_tokens:
        token_id = thalamus.token_to_id.pop(token_str, None)
        if token_id is not None:
            thalamus.id_to_token.pop(token_id, None)

    # 4. Hippocampus: Transitions bereinigen
    purged_transitions = 0
    for bucket in list(hippocampus.transitions.keys()):
        for ngram in list(hippocampus.transitions[bucket].keys()):
            # N-Gram enthält unknown-Token → komplett entfernen
            if any(t in unknown_token_ids for t in ngram):
                del hippocampus.transitions[bucket][ngram]
                hippocampus.totals[bucket].pop(ngram, None)
                purged_transitions += 1
                continue

            # Target ist unknown-Token → entfernen
            for tok_id in list(hippocampus.transitions[bucket][ngram].keys()):
                if tok_id in unknown_token_ids:
                    count = hippocampus.transitions[bucket][ngram].pop(tok_id)
                    hippocampus.totals[bucket][ngram] = max(
                        0, hippocampus.totals[bucket].get(ngram, 0) - count
                    )
                    purged_transitions += 1

            # Leeres N-Gram aufräumen
            if not hippocampus.transitions[bucket][ngram]:
                del hippocampus.transitions[bucket][ngram]
                hippocampus.totals[bucket].pop(ngram, None)

        # Leeren Bucket aufräumen
        if not hippocampus.transitions[bucket]:
            del hippocampus.transitions[bucket]
            hippocampus.totals.pop(bucket, None)

    # 5. Hippocampus: Buffer bereinigen
    clean_buffer = [t for t in hippocampus.buffer if t not in unknown_token_ids]
    hippocampus.buffer = deque(clean_buffer, maxlen=20)

    # 6. Hippocampus: Durations bereinigen
    for dur_key in list(hippocampus.durations.keys()):
        parts = dur_key.split("_")
        if len(parts) == 2:
            if int(parts[0]) in unknown_token_ids or int(parts[1]) in unknown_token_ids:
                del hippocampus.durations[dur_key]

    # 7. Shadow-Predictions Reset (alte Predictions basieren auf vergiftetem Kontext)
    hippocampus.shadow_predictions.clear()
    hippocampus.shadow_hits = 0
    hippocampus.shadow_misses = 0
    hippocampus.shadow_total = 0

    _LOGGER.warning(
        "v0.11.0 Migration: %d unknown-Tokens entfernt, %d Transitions bereinigt, "
        "%d Entities gefiltert, Accuracy-Zähler zurückgesetzt",
        len(unknown_token_ids), purged_transitions, len(unknown_entities),
    )
