"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM v0.18.0 – Neuroinspired Home Intelligence           ║
║  Home Assistant Custom Component                                 ║
║                                                                  ║
║  Architektur:                                                    ║
║  Thalamus → Hippocampus → Cerebellum → PFC → Aktion           ║
║      ↑           ↑            ↑          ↑                      ║
║  Hypothalamus  Spatial    Basalganglien Amygdala                ║
║      ↑         Cortex    (Belohnung)                            ║
║    Insula ←─────┘                                               ║
║                                                                  ║
║  v0.14.0 – Native Sensor Platform:                              ║
║  • Alle Sensoren als echte HA-Entitäten (kein YAML nötig)      ║
║  • Aktivitäts-Sensoren nativ (template-Sensoren entfallen)     ║
║  • Label-Support für Entity-Raum-Zuordnung                      ║
║  • Area-Fix: HA-Areas direkt nutzen (kein Map-Zwang)            ║
║  • Saubere Deinstallation (brain, entities, helpers entfernt)   ║
║  • Komprimiertes Speichern (brain.json.gz, gzip)                ║
╚══════════════════════════════════════════════════════════════════╝
"""

import gzip
import json
import logging
import os
import shutil
import re
import time
from collections import Counter, deque
from datetime import datetime, timezone

from homeassistant.const import EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant import config_entries
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .thalamus import Thalamus
from .hippocampus import Hippocampus
from .hypothalamus import Hypothalamus
from .spatial_cortex import SpatialCortex
from .insula import Insula
from .amygdala import Amygdala
from .cerebellum import Cerebellum
from .prefrontal_cortex import PrefrontalCortex, MODE_SHADOW, MODE_CONFIRM, MODE_ACTIVE, VALID_MODES
from .basal_ganglia import BasalGanglia
from .cortex import Cortex, PROVIDERS, DEFAULT_PROMPTS

from .config_flow import PRESETS

_LOGGER = logging.getLogger(__name__)
DOMAIN = "kontinuum"
VERSION = "0.18.0"
DATA_DIR = "kontinuum"
HISTORY_DIR = "history"
BRAIN_FILE = "brain.json.gz"
BRAIN_FILE_LEGACY = "brain.json"
SAVE_INTERVAL = 600
PLATFORMS = [Platform.SENSOR]
SIGNAL_SENSORS_UPDATE = f"{DOMAIN}_sensors_update"
SIGNAL_PERSONS_UPDATE = f"{DOMAIN}_persons_update"
SIGNAL_CORTEX_UPDATE = f"{DOMAIN}_cortex_update"


# ══════════════════════════════════════════════════════════════════
# ASYNC-SAFE HELPERS
# ══════════════════════════════════════════════════════════════════

def _install_dashboard(hass):
    """Kopiert kontinuum.html nach /config/www/community/kontinuum/ falls nötig."""
    src = os.path.join(os.path.dirname(__file__), "assets", "kontinuum.html")
    if not os.path.isfile(src):
        _LOGGER.warning("KONTINUUM Dashboard HTML nicht gefunden – übersprungen")
        return False

    # In /config/www/ ablegen (wird von HA unter /local/ bereitgestellt)
    dst_dir = hass.config.path("www")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "kontinuum.html")

    # Immer kopieren wenn Quelle neuer ist oder Ziel fehlt
    needs_copy = not os.path.isfile(dst)
    if not needs_copy:
        src_mtime = os.path.getmtime(src)
        dst_mtime = os.path.getmtime(dst)
        needs_copy = src_mtime > dst_mtime

    if needs_copy:
        shutil.copy2(src, dst)
        _LOGGER.info("KONTINUUM Dashboard installiert: %s", dst)
    else:
        _LOGGER.debug("KONTINUUM Dashboard bereits aktuell")

    return True


async def _register_dashboard_panel(hass):
    """Registriert das KONTINUUM Dashboard als iframe-Panel in der HA Sidebar.

    Nutzt mehrere Methoden als Fallback für verschiedene HA-Versionen.
    """
    url_path = "kontinuum"

    # Panel entfernen falls es bereits existiert (bei Reload)
    try:
        from homeassistant.components.frontend import async_remove_panel
        async_remove_panel(hass, url_path)
    except Exception:
        pass

    # Methode 1: Direkte Import-Funktion (Standard in HA 2023+)
    try:
        from homeassistant.components.frontend import async_register_built_in_panel
        async_register_built_in_panel(
            hass,
            component_name="iframe",
            sidebar_title="KONTINUUM",
            sidebar_icon="mdi:brain",
            frontend_url_path=url_path,
            config={"url": "/local/kontinuum.html"},
            require_admin=False,
        )
        _LOGGER.info("KONTINUUM Dashboard registriert (async_register_built_in_panel)")
        return
    except Exception as e:
        _LOGGER.debug("Methode 1 fehlgeschlagen: %s", e)

    # Methode 2: panel_custom Integration
    try:
        from homeassistant.components.panel_custom import async_register_panel
        await async_register_panel(
            hass,
            frontend_url_path=url_path,
            webcomponent_name="iframe",
            sidebar_title="KONTINUUM",
            sidebar_icon="mdi:brain",
            module_url="/local/kontinuum.html",
            require_admin=False,
            config={"url": "/local/kontinuum.html"},
        )
        _LOGGER.info("KONTINUUM Dashboard registriert (panel_custom)")
        return
    except Exception as e:
        _LOGGER.debug("Methode 2 fehlgeschlagen: %s", e)

    # Methode 3: Direkt über hass.data["frontend_panels"]
    try:
        key = "frontend_panels"
        if key in hass.data:
            hass.data[key][url_path] = {
                "component_name": "iframe",
                "sidebar_title": "KONTINUUM",
                "sidebar_icon": "mdi:brain",
                "url_path": url_path,
                "config": {"url": "/local/kontinuum.html"},
                "require_admin": False,
            }
            _LOGGER.info("KONTINUUM Dashboard registriert (frontend_panels dict)")
            return
    except Exception as e:
        _LOGGER.debug("Methode 3 fehlgeschlagen: %s", e)

    _LOGGER.warning(
        "KONTINUUM Dashboard konnte nicht als Sidebar-Panel registriert werden. "
        "Dashboard erreichbar unter: /local/kontinuum.html – "
        "Manuell als iframe-Karte in Lovelace einbinden."
    )


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


def _ensure_data_dir(hass) -> str:
    """Erstellt /config/kontinuum/ und /config/kontinuum/history/ falls nötig.
    Migriert brain.json.gz vom alten Pfad (/config/) in den neuen Ordner.
    Gibt den Pfad zum Data-Dir zurück."""
    data_dir = hass.config.path(DATA_DIR)
    history_dir = os.path.join(data_dir, HISTORY_DIR)
    os.makedirs(history_dir, exist_ok=True)

    # Migration: brain.json.gz von /config/ nach /config/kontinuum/
    old_brain = hass.config.path(BRAIN_FILE)
    new_brain = os.path.join(data_dir, BRAIN_FILE)
    if os.path.isfile(old_brain) and not os.path.isfile(new_brain):
        os.rename(old_brain, new_brain)
        _LOGGER.info("Brain migriert: %s → %s", old_brain, new_brain)

    # Migration: altes brain.json (unkomprimiert)
    old_legacy = hass.config.path(BRAIN_FILE_LEGACY)
    new_legacy = os.path.join(data_dir, BRAIN_FILE_LEGACY)
    if os.path.isfile(old_legacy) and not os.path.isfile(new_legacy):
        os.rename(old_legacy, new_legacy)
        _LOGGER.info("Legacy-Brain migriert: %s → %s", old_legacy, new_legacy)

    return data_dir


def _write_history_entry(data_dir: str, entry_type: str, data: dict):
    """Schreibt einen History-Eintrag als JSON in /config/kontinuum/history/.

    Dateiformat: {entry_type}_{timestamp}.json
    Alte Einträge werden automatisch bereinigt (max 100 pro Typ).
    """
    history_dir = os.path.join(data_dir, HISTORY_DIR)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{entry_type}_{ts}.json"
    filepath = os.path.join(history_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        _LOGGER.warning("History konnte nicht geschrieben werden: %s", e)
        return

    # Aufräumen: max 100 Dateien pro Typ behalten
    try:
        all_files = sorted([
            f for f in os.listdir(history_dir)
            if f.startswith(entry_type + "_") and f.endswith(".json")
        ])
        if len(all_files) > 100:
            for old_file in all_files[:-100]:
                os.remove(os.path.join(history_dir, old_file))
    except Exception:
        pass


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

        # ── Dashboard Auto-Install ─────────────────────────────
        if entry.data.get("enable_dashboard", True):
            installed = await hass.async_add_executor_job(_install_dashboard, hass)
            if installed:
                _LOGGER.info("KONTINUUM Dashboard verfügbar unter /local/kontinuum.html")
                await _register_dashboard_panel(hass)

        # ── Module initialisieren ─────────────────────────────
        thalamus = Thalamus()
        hippocampus = Hippocampus()
        hypothalamus = Hypothalamus()
        spatial = SpatialCortex()
        insula = Insula()
        amygdala = Amygdala()
        cerebellum = Cerebellum()
        basal_ganglia = BasalGanglia()
        prefrontal = PrefrontalCortex(amygdala)
        cortex = Cortex()

        # Optional: Context-Profile für erweiterte Semantik/Thresholds
        profile_path = hass.config.path("kontinuum_context_profile.json")
        await hass.async_add_executor_job(thalamus.load_custom_profiles, profile_path)

        # ── Presets anwenden ──────────────────────────────────
        cerebellum.MIN_OBSERVATIONS = config_data.get("cerebellum_min_obs", 5)
        cerebellum.MIN_CONFIDENCE = config_data.get("cerebellum_min_conf", 0.75)
        hippocampus.DECAY_RATE = config_data.get("hippocampus_decay", 0.993)
        hippocampus.MIN_OBSERVATIONS = config_data.get("hippocampus_min_obs", 3)
        prefrontal.shadow_mode = config_data.get("shadow_mode", True)
        prefrontal.operation_mode = config_data.get("operation_mode", MODE_SHADOW if prefrontal.shadow_mode else MODE_ACTIVE)

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
            "basal_ganglia": basal_ganglia,
            "prefrontal": prefrontal,
            "cortex": cortex,
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

        # ── Datenverzeichnis erstellen + Migration ───────────
        data_dir = await hass.async_add_executor_job(_ensure_data_dir, hass)
        brain["_data_dir"] = data_dir

        # ── Gehirn laden ──────────────────────────────────────
        brain_path = os.path.join(data_dir, BRAIN_FILE)
        await hass.async_add_executor_job(_load_brain, brain, brain_path)

        # ── Cortex aus Config Entry konfigurieren ────────────────
        entry_agents = entry.data.get("cortex_agents", {})
        if entry_agents and entry.data.get("enable_cortex", False):
            brain["_cortex_agents"] = entry_agents
            cortex.configure(list(entry_agents.values()))
            # Sequential Mode + Diskussionsrunden aus Config
            cortex.sequential_mode = entry.data.get("sequential_mode", False)
            cortex.discussion_rounds = entry.data.get("discussion_rounds", 2)
            _LOGGER.info(
                "Cortex aus Config geladen: %d Agents, sequential=%s, rounds=%d",
                len(cortex.agents), cortex.sequential_mode,
                cortex.discussion_rounds,
            )

        # ── Entities entdecken ────────────────────────────────
        await _discover_entities(hass, thalamus)

        # ── In hass.data speichern (vor Platform-Setup!) ──────
        hass.data[DOMAIN] = brain

        # ── Sensor-Plattform laden (native Entitäten) ────────
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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

                # ignore_kontinuum Label → komplett ignorieren (v0.15.0)
                if entity_id in thalamus._ignored_entities:
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
                was_override = prefrontal.check_override(entity_id, new_state, amygdala)
                if was_override:
                    # Basalganglien: Negatives Feedback (NoGo-Pathway)
                    basal_ganglia.process_outcome(entity_id, positive=False)
                # Implizite Positives → Basalganglien: Go-Pathway
                accepted = prefrontal.check_implicit_positives(amygdala)
                if accepted:
                    for acc_eid in accepted:
                        basal_ganglia.process_outcome(acc_eid, positive=True)
                basal_ganglia.cleanup_pending()

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

                # Basalganglien: Passives Lernen (beobachtete Muster)
                bucket = hippocampus._context_bucket(ctx)
                basal_ganglia.process_observation(token_id, bucket)

                # Predictions + Basalganglien-Ranking
                predictions = hippocampus.predict(ctx)
                if predictions:
                    predictions = _rank_with_basal_ganglia(
                        predictions, basal_ganglia, bucket)

                # PFC entscheidet (mit Q-Value Boost aus Basalganglien)
                decision = prefrontal.evaluate(
                    predictions, thalamus, basal_ganglia, bucket)
                if decision:
                    # Basalganglien: Aktion registrieren für Outcome-Tracking
                    if decision.entity_id:
                        basal_ganglia.register_action(
                            decision.entity_id, decision.token_id,
                            bucket, decision.token)
                    _process_decision(hass, brain, decision)

                # Letztes Signal + Vorhersage im Brain speichern (für Cortex-Kontext)
                brain["_last_signal"] = signal
                brain["_last_predictions"] = predictions

                # Sensoren updaten (native Entitäten via Dispatcher)
                async_dispatcher_send(
                    hass, SIGNAL_SENSORS_UPDATE,
                    {"last_signal": signal, "predictions": predictions},
                )

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

                # ── Brain Review: Monatlich automatisch ──
                BRAIN_REVIEW_INTERVAL = 30 * 86400  # 30 Tage
                if (cortex.enabled
                        and now_ts - brain.get("_last_review_ts", 0) > BRAIN_REVIEW_INTERVAL
                        and hippocampus.total_events > 500):
                    brain["_last_review_ts"] = now_ts
                    hass.async_create_task(
                        hass.services.async_call(
                            DOMAIN, "brain_review", {}
                        )
                    )
                    _LOGGER.info("Automatischer Brain Review gestartet (monatlich)")

                # Personen-Zähler
                if now_ts - brain["_last_persons_update"] > 30:
                    _update_persons_sensor(hass)
                    brain["_last_persons_update"] = now_ts

            except Exception as e:
                _LOGGER.error("KONTINUUM Fehler: %s", e, exc_info=True)

        hass.bus.async_listen(EVENT_STATE_CHANGED, on_state_changed)

        # ── Shutdown-Handler ──────────────────────────────────
        async def on_shutdown(event):
            _LOGGER.info("KONTINUUM wird heruntergefahren – speichere Gehirn...")
            await cortex.close()
            await hass.async_add_executor_job(_save_brain, brain, brain_path)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_shutdown)

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

        # Startup-Notification (v0.18.0: kompakt, eine Notification statt 5)
        filtered = thalamus.stats.get("entities_filtered", 0)
        op_mode = prefrontal.operation_mode
        mode_label = {"shadow": "Shadow", "confirm": "Confirm", "active": "Active"}.get(op_mode, op_mode)
        startup_parts = [
            f"**{len(thalamus.entity_semantic)}** Entities · "
            f"**{len(thalamus._known_rooms)}** Räume · "
            f"**{hippocampus.total_events}** Events · "
            f"Accuracy **{hippocampus.accuracy:.0%}**",
            f"Modus: **{mode_label}** · "
            f"Preset: {preset_key} · "
            f"Routinen: {len(cerebellum.rules)}",
        ]
        ignored_count = thalamus.stats.get("entities_ignored", 0)
        if ignored_count:
            startup_parts.append(
                f"🚫 {ignored_count} Entities via `ignore_kontinuum` Label ausgeschlossen")
        if filtered:
            startup_parts.append(
                f"*{filtered} Entities ohne Raum – "
                f"[Zuordnen](/config/entities)*")
        activated = prefrontal.activated_semantics
        if activated:
            startup_parts.append(
                f"Freigeschaltet: {', '.join(sorted(activated))}")
        if cortex.enabled:
            startup_parts.append(
                f"Cortex: {len(cortex.agents)} Agents aktiv")
        _notify(hass,
            f"KONTINUUM v{VERSION}",
            "\n".join(startup_parts),
            "kontinuum_startup",
        )

        return True

    except Exception as e:
        _LOGGER.error("KONTINUUM Setup fehlgeschlagen: %s", e, exc_info=True)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Entlädt KONTINUUM und speichert das Gehirn."""
    # Sensor-Plattform entladen
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    brain = hass.data.get(DOMAIN)
    if brain:
        data_dir = brain.get("_data_dir", hass.config.path(DATA_DIR))
        brain_path = os.path.join(data_dir, BRAIN_FILE)
        await hass.async_add_executor_job(_save_brain, brain, brain_path)

    # Dashboard-Panel entfernen
    try:
        from homeassistant.components.frontend import async_remove_panel
        async_remove_panel(hass, "kontinuum")
    except Exception:
        pass

    hass.data.pop(DOMAIN, None)
    _LOGGER.info("KONTINUUM entladen und gespeichert.")
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Deinstallation: Entfernt /config/kontinuum/ und input_number-Helfer."""
    # Kompletten kontinuum-Ordner löschen (blocking I/O → Executor)
    def _cleanup_files():
        data_dir = hass.config.path(DATA_DIR)
        if os.path.isdir(data_dir):
            shutil.rmtree(data_dir)
            _LOGGER.info("Entfernt: %s", data_dir)
        for fname in (BRAIN_FILE, BRAIN_FILE_LEGACY, BRAIN_FILE_LEGACY + ".migrated"):
            path = hass.config.path(fname)
            if os.path.exists(path):
                os.remove(path)
                _LOGGER.info("Entfernt: %s", path)

    await hass.async_add_executor_job(_cleanup_files)

    # input_number.k_* Helfer entfernen
    try:
        from homeassistant.helpers.entity_registry import async_get as get_er
        er = get_er(hass)
        to_remove = [
            eid for eid in er.entities
            if eid.startswith("input_number.k_")
        ]
        for eid in to_remove:
            er.async_remove(eid)
            _LOGGER.info("Helfer entfernt: %s", eid)
    except Exception as e:
        _LOGGER.warning("Helfer-Bereinigung fehlgeschlagen: %s", e)

    # Context-Profile bereinigen
    profile_path = hass.config.path("kontinuum_context_profile.json")
    if os.path.exists(profile_path):
        os.remove(profile_path)
        _LOGGER.info("Entfernt: %s", profile_path)

    _LOGGER.info("KONTINUUM vollständig deinstalliert.")


# ══════════════════════════════════════════════════════════════════
# TOKEN INJECTION
# ══════════════════════════════════════════════════════════════════

def _rank_with_basal_ganglia(predictions, basal_ganglia, bucket):
    """
    Basalganglien-Ranking: Sortiert Predictions nach Go/NoGo-Pathway.
    Go (positive Q-Values) → nach oben
    NoGo (negative Q-Values) → nach unten
    Predictions: [(token_id, prob, conf, source, n_obs), ...]
    """
    ranked = []
    for prediction in predictions:
        token_id, prob, conf, source = prediction[:4]
        n_obs = prediction[4] if len(prediction) > 4 else 0
        priority = basal_ganglia.get_action_priority(token_id, bucket)
        # Confidence durch Basalganglien modifizieren
        bg_conf = conf + priority * 0.1  # Max ±0.2 Einfluss
        bg_conf = max(0.05, min(1.0, bg_conf))
        ranked.append((token_id, prob, bg_conf, source, n_obs))
    # Re-sort by modified confidence * probability
    ranked.sort(key=lambda x: x[1] * x[2], reverse=True)
    return ranked


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
    prefrontal = brain["prefrontal"]
    cerebellum = brain["cerebellum"]

    if decision.stage == "EXECUTE":
        _execute_decision(hass, brain, decision)

    elif decision.stage == "CONFIRM":
        # v0.18.0: Bestätigung anfordern statt direkt ausführen
        service_call = prefrontal.get_service_call(decision)
        if service_call and decision.entity_id:
            confirm_id = prefrontal.queue_confirm(decision)
            _LOGGER.info(
                "KONTINUUM CONFIRM: %s → %s (ID: %s, conf=%.0f%%)",
                decision.token, decision.entity_id, confirm_id,
                decision.confidence * 100,
            )
            _notify(hass,
                "KONTINUUM – Bestätigung erforderlich",
                f"KONTINUUM möchte **{decision.token}** ausführen.\n"
                f"Entity: {decision.entity_id}\n"
                f"Confidence: {decision.confidence:.0%} | "
                f"Risiko: {decision.risk:.2f}\n\n"
                f"**Bestätigen:** `kontinuum.confirm_action` mit "
                f"`confirm_id: {confirm_id}`\n"
                f"**Ablehnen:** Ignorieren (verfällt nach 10 Min)",
                "kontinuum_confirm",
            )

    elif decision.stage == "SUGGEST":
        _notify(hass,
            "KONTINUUM – Vorschlag",
            f"KONTINUUM würde gerne **{decision.token}** ausführen.\n"
            f"Entity: {decision.entity_id or '?'}\n"
            f"Confidence: {decision.confidence:.0%} | "
            f"Risiko: {decision.risk:.2f}\n"
            f"Quelle: {decision.source}",
            "kontinuum_suggest",
        )


def _execute_decision(hass, brain, decision):
    """Führt eine bestätigte Entscheidung tatsächlich aus (+ Outcome-Tracking)."""
    prefrontal = brain["prefrontal"]
    cerebellum = brain["cerebellum"]
    service_call = prefrontal.get_service_call(decision)

    if not service_call or not decision.entity_id:
        _LOGGER.warning(
            "KONTINUUM EXECUTE abgebrochen: kein Service/Entity für %s", decision.token)
        return

    domain = service_call["domain"]
    service = service_call["service"]
    entity_id = decision.entity_id
    svc_data = service_call.get("data", {"entity_id": entity_id})
    parts = decision.token.split(".")
    semantic = parts[1] if len(parts) == 3 else ""
    desired_state = parts[2] if len(parts) == 3 else ""

    _LOGGER.info(
        "KONTINUUM EXECUTE: %s.%s → %s (conf=%.0f%%, util=%.2f, risk=%.2f)",
        domain, service, entity_id,
        decision.confidence * 100, decision.utility, decision.risk,
    )

    _async_service_call(hass, domain, service, svc_data)
    prefrontal.mark_own_action(entity_id, token=decision.token, semantic=semantic)

    # Cerebellum Outcome-Tracking: Nach 3s prüfen ob State dem gewünschten entspricht
    async def _check_outcome():
        import asyncio
        await asyncio.sleep(3)
        new_state_obj = hass.states.get(entity_id)
        if new_state_obj:
            actual_state = new_state_obj.state
            success = (actual_state == desired_state) if desired_state else True
            cerebellum.record_outcome(
                f"{decision.token_id}_{decision.token_id}", success)
            _LOGGER.debug(
                "Outcome-Check: %s → gewünscht=%s, ist=%s, Erfolg=%s",
                entity_id, desired_state, actual_state, success,
            )

    hass.async_create_task(_check_outcome())

    # History: Autonome Entscheidung loggen
    data_dir = brain.get("_data_dir", "")
    if data_dir:
        _write_history_entry(data_dir, "decision", {
            "type": "autonomous_execute",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": f"{domain}.{service}",
            "entity_id": entity_id,
            "token": decision.token,
            "confidence": round(decision.confidence, 3),
            "utility": round(decision.utility, 3),
            "risk": round(decision.risk, 3),
            "source": decision.source if hasattr(decision, "source") else "prefrontal",
        })


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
    for rule_key, rule in cerebellum.rules.items():
        if rule_key not in notified:
            notified.add(rule_key)
            # v0.13.0: Sequenz-Regeln anzeigen
            if rule.ngram_order > 1:
                seq_tokens = [thalamus.id_to_token.get(t, f"?{t}") for t in rule.trigger_sequence]
                target_token = thalamus.id_to_token.get(rule.target, f"?{rule.target}")
                rules_text.append(f"• {' → '.join(seq_tokens)} → {target_token} ({rule.ngram_order}-gram)")
            else:
                t1 = thalamus.id_to_token.get(rule.trigger, f"?{rule.trigger}")
                t2 = thalamus.id_to_token.get(rule.target, f"?{rule.target}")
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

    async def handle_export_brain(call):
        """Exportiert brain.json.gz als lesbare brain_export.json (für externe Analyse)."""
        data_dir = brain.get("_data_dir", hass.config.path(DATA_DIR))
        brain_path = os.path.join(data_dir, BRAIN_FILE)
        export_path = os.path.join(data_dir, "brain_export.json")
        try:
            with gzip.open(brain_path, "rb") as f:
                raw = f.read()
            with open(export_path, "w", encoding="utf-8") as f:
                data = json.loads(raw)
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            size_kb = len(raw) // 1024
            export_kb = os.path.getsize(export_path) // 1024
            await hass.services.async_call("persistent_notification", "create", {
                "title": "🧠 KONTINUUM – Brain Export",
                "message": f"Exportiert nach `/config/kontinuum/brain_export.json`\n\n"
                           f"Komprimiert: {size_kb} KB → Lesbar: {export_kb} KB\n\n"
                           f"Für DeepSeek-Analyse im Datei-Browser öffnen.",
                "notification_id": "kontinuum_export",
            })
            _LOGGER.info("Brain exportiert: %s (%d KB)", export_path, export_kb)
        except Exception as e:
            _LOGGER.error("Export fehlgeschlagen: %s", e)

    async def handle_activate(call):
        """
        Schaltet autonome Ausführung für einen semantischen Typ frei.
        Service-Call: kontinuum.activate mit data: {semantic: "light"}

        Schrittweise Freischaltung:
        1. Erst "light" freischalten, beobachten
        2. Dann "switch", "fan", etc.
        3. Jederzeit mit kontinuum.deactivate zurücknehmen
        """
        semantic = call.data.get("semantic", "").strip().lower()
        if not semantic:
            _LOGGER.warning("kontinuum.activate: 'semantic' fehlt")
            return

        valid = {"light", "switch", "fan", "cover", "climate",
                 "media", "automation", "vacuum"}
        if semantic not in valid:
            _LOGGER.warning("kontinuum.activate: '%s' ist kein gültiger Typ. "
                            "Erlaubt: %s", semantic, ", ".join(sorted(valid)))
            return

        prefrontal = brain["prefrontal"]
        prefrontal.activated_semantics.add(semantic)
        _LOGGER.info("KONTINUUM: '%s' für autonome Ausführung freigeschaltet", semantic)

        await hass.services.async_call("persistent_notification", "create", {
            "title": f"KONTINUUM – {semantic} aktiviert",
            "message": f"**{semantic}** ist jetzt für autonome Ausführung freigeschaltet.\n\n"
                       f"KONTINUUM wird {semantic}-Entities selbständig steuern, "
                       f"wenn Confidence und Utility hoch genug sind.\n\n"
                       f"Aktive Typen: {', '.join(sorted(prefrontal.activated_semantics)) or 'keine'}\n\n"
                       f"Zum Deaktivieren: `kontinuum.deactivate` mit `semantic: {semantic}`",
            "notification_id": "kontinuum_activate",
        })

    async def handle_deactivate(call):
        """Deaktiviert autonome Ausführung für einen semantischen Typ."""
        semantic = call.data.get("semantic", "").strip().lower()
        prefrontal = brain["prefrontal"]

        if semantic == "all":
            prefrontal.activated_semantics.clear()
            _LOGGER.info("KONTINUUM: Alle Semantiken deaktiviert")
        elif semantic in prefrontal.activated_semantics:
            prefrontal.activated_semantics.discard(semantic)
            _LOGGER.info("KONTINUUM: '%s' deaktiviert", semantic)
        else:
            _LOGGER.warning("KONTINUUM: '%s' war nicht aktiviert", semantic)
            return

        await hass.services.async_call("persistent_notification", "create", {
            "title": "KONTINUUM – Deaktiviert",
            "message": f"Aktive Typen: {', '.join(sorted(prefrontal.activated_semantics)) or 'keine'}",
            "notification_id": "kontinuum_activate",
        })

    async def handle_configure_agent(call):
        """
        Konfiguriert einen Cortex-Agent.
        Service: kontinuum.configure_agent
        Data: {slot: 1-4, name: "comfort", provider: "ollama",
               model: "llama3.2", url: "http://...", api_key: "", prompt: "..."}
        """
        cortex = brain["cortex"]
        slot = int(call.data.get("slot", 1))
        if slot < 1 or slot > 4:
            _LOGGER.warning("Cortex: Slot muss 1-4 sein, nicht %s", slot)
            return

        provider = call.data.get("provider", "ollama")
        if provider not in PROVIDERS:
            _LOGGER.warning("Cortex: Unbekannter Provider '%s'", provider)
            return

        provider_info = PROVIDERS[provider]
        name = call.data.get("name", f"agent_{slot}")
        model = call.data.get("model", provider_info["default_model"])
        url = call.data.get("url", provider_info["default_url"])
        api_key = call.data.get("api_key", "")
        prompt = call.data.get("prompt", DEFAULT_PROMPTS.get(name, ""))

        # Agent-Config im Brain speichern
        agents = dict(brain.get("_cortex_agents", {}))
        agents[str(slot)] = {
            "name": name, "provider": provider, "model": model,
            "url": url, "api_key": api_key, "system_prompt": prompt,
        }
        brain["_cortex_agents"] = agents

        # Cortex neu konfigurieren
        cortex.configure(list(agents.values()))

        _LOGGER.info("Cortex Agent %d konfiguriert: %s (%s/%s)",
                     slot, name, provider, model)

        await hass.services.async_call("persistent_notification", "create", {
            "title": f"KONTINUUM Cortex – Agent {slot} konfiguriert",
            "message": (
                f"**{name}** ({provider_info['label']})\n"
                f"Modell: {model}\n"
                f"URL: {url}\n"
                f"Agents aktiv: {len(cortex.agents)}"
            ),
            "notification_id": "kontinuum_cortex_config",
        })

    async def handle_cortex_consult(call):
        """
        Löst manuell eine Cortex-Beratung aus.
        Service: kontinuum.cortex_consult
        """
        cortex = brain["cortex"]
        if not cortex.enabled:
            _LOGGER.warning("Cortex nicht konfiguriert – nutze kontinuum.configure_agent")
            return

        result = await cortex.consult(brain)

        # Agent-Sensoren updaten (unabhängig vom Ergebnis)
        async_dispatcher_send(hass, SIGNAL_CORTEX_UPDATE)

        if not result:
            return

        # ── History: Vollständige Diskussion loggen ────────
        data_dir = brain.get("_data_dir", hass.config.path(DATA_DIR))
        history_entry = {
            "type": "cortex_consult",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": cortex._build_context(brain),
            "discussion_rounds": result.get("discussion_rounds", 1),
            "proposals": result.get("proposals", []),
            "revisions": result.get("revisions", []),
            "consensus": {
                "action": result.get("consensus_action"),
                "entity": result.get("consensus_entity"),
                "reason": result.get("consensus_reason"),
                "vetoed": result.get("vetoed", False),
            },
            "agents": [
                {"name": a.name, "provider": a.provider,
                 "model": a.model}
                for a in cortex.agents
            ],
        }
        await hass.async_add_executor_job(
            _write_history_entry, data_dir, "cortex_consult", history_entry
        )

        proposals_text = "\n".join(
            f"- **{p.get('agent', '?')}**: {p.get('reason', '?')} "
            f"(Priorität: {p.get('priority', 0)})"
            for p in result.get("proposals", [])
        )

        revisions_text = ""
        if result.get("revisions"):
            revisions_text = "\n\n**Revisionen (Runde 2):**\n" + "\n".join(
                f"- **{r.get('agent', '?')}**: {r.get('reason', '?')} "
                f"(Priorität: {r.get('priority', 0)})"
                for r in result.get("revisions", [])
            )

        await hass.services.async_call("persistent_notification", "create", {
            "title": f"KONTINUUM Cortex – Beratung ({result.get('discussion_rounds', 1)} Runden)",
            "message": (
                f"**Konsens:** {result.get('consensus_action') or 'Keine Aktion'}\n"
                f"**Entity:** {result.get('consensus_entity') or '–'}\n"
                f"**Grund:** {result.get('consensus_reason', '?')}\n"
                f"**Veto:** {'JA' if result.get('vetoed') else 'Nein'}\n\n"
                f"**Vorschläge (Runde 1):**\n{proposals_text}"
                f"{revisions_text}\n\n"
                f"*Vollständiges Protokoll: /config/kontinuum/history/*"
            ),
            "notification_id": "kontinuum_cortex_result",
        })

        # ── Cortex → Gehirn: Ergebnisse integrieren ──────────
        bridge_result = cortex.integrate_into_brain(brain, result)
        if bridge_result.get("integrated"):
            _LOGGER.info("Cortex Bridge: %s",
                         ", ".join(bridge_result.get("actions", [])))

        # Wenn Konsens eine Aktion vorschlägt und kein Veto → ausführen
        action = result.get("consensus_action")
        entity = result.get("consensus_entity")
        if action and entity and not result.get("vetoed"):
            parts = action.split(".")
            if len(parts) == 2:
                _LOGGER.info("Cortex EXECUTE: %s → %s", action, entity)
                _async_service_call(hass, parts[0], parts[1], {"entity_id": entity})

                # Ausführung im Prefrontal tracken (für Override-Detection)
                prefrontal = brain["prefrontal"]
                semantic = parts[0] if parts else ""
                prefrontal.mark_own_action(
                    entity, token=f"cortex.{action}", semantic=semantic,
                )

    async def handle_set_mode(call):
        """
        Setzt den Betriebsmodus von KONTINUUM.
        Service: kontinuum.set_mode mit data: {mode: "shadow/confirm/active"}
        """
        mode = call.data.get("mode", "").strip().lower()
        prefrontal = brain["prefrontal"]

        if prefrontal.set_operation_mode(mode):
            mode_labels = {
                "shadow": "Shadow – Nur beobachten",
                "confirm": "Confirm – Bestätigung vor Ausführung",
                "active": "Active – Selbständig schalten",
            }
            await hass.services.async_call("persistent_notification", "create", {
                "title": f"KONTINUUM – Modus: {mode.upper()}",
                "message": (
                    f"Betriebsmodus auf **{mode_labels.get(mode, mode)}** gesetzt.\n\n"
                    f"Aktive Semantiken: {', '.join(sorted(prefrontal.activated_semantics)) or 'keine'}\n"
                    f"Wartende Bestätigungen: {len(prefrontal._pending_confirms)}"
                ),
                "notification_id": "kontinuum_mode",
            })
        else:
            _LOGGER.warning("Ungültiger Modus: '%s'. Erlaubt: shadow, confirm, active", mode)

    async def handle_confirm_action(call):
        """
        Bestätigt eine wartende Aktion im Confirm-Modus.
        Service: kontinuum.confirm_action mit data: {confirm_id: "c_..."}
        Oder: {confirm_all: true} um alle wartenden zu bestätigen.
        """
        prefrontal = brain["prefrontal"]

        if call.data.get("confirm_all", False):
            # Alle wartenden bestätigen
            pending = list(prefrontal._pending_confirms.keys())
            for cid in pending:
                decision = prefrontal.get_pending_confirm(cid)
                if decision:
                    _execute_decision(hass, brain, decision)
            if pending:
                _LOGGER.info("KONTINUUM: %d Aktionen bestätigt", len(pending))
            return

        confirm_id = call.data.get("confirm_id", "")
        decision = prefrontal.get_pending_confirm(confirm_id)
        if decision:
            _execute_decision(hass, brain, decision)
            _LOGGER.info("KONTINUUM: Aktion bestätigt: %s → %s",
                         decision.token, decision.entity_id)
        else:
            _LOGGER.warning("KONTINUUM: confirm_id '%s' nicht gefunden oder abgelaufen",
                            confirm_id)

    async def handle_reject_action(call):
        """
        Lehnt eine wartende Aktion ab.
        Service: kontinuum.reject_action mit data: {confirm_id: "c_..."}
        """
        prefrontal = brain["prefrontal"]
        confirm_id = call.data.get("confirm_id", "")
        decision = prefrontal.get_pending_confirm(confirm_id)
        if decision:
            # Negatives Feedback lernen
            parts = decision.token.split(".")
            semantic = parts[1] if len(parts) == 3 else ""
            if semantic:
                prefrontal.learn_from_feedback(semantic, positive=False)
            _LOGGER.info("KONTINUUM: Aktion abgelehnt: %s", decision.token)
        else:
            _LOGGER.warning("KONTINUUM: confirm_id '%s' nicht gefunden", confirm_id)

    async def handle_cortex_remove_agent(call):
        """Entfernt einen Cortex-Agent. Data: {slot: 1-4}"""
        slot = str(call.data.get("slot", ""))
        agents = dict(brain.get("_cortex_agents", {}))
        if slot in agents:
            del agents[slot]
            brain["_cortex_agents"] = agents
            brain["cortex"].configure(list(agents.values()))
            _LOGGER.info("Cortex Agent %s entfernt", slot)

    async def handle_cortex_sequential(call):
        """
        Schaltet den sequentiellen Modus für Cortex-Agents ein/aus.
        Service: kontinuum.cortex_sequential mit data: {enabled: true/false}
        Für Systeme mit nur einer GPU/Ollama-Instanz.
        """
        cortex = brain["cortex"]
        enabled = call.data.get("enabled", not cortex.sequential_mode)
        cortex.sequential_mode = bool(enabled)
        _LOGGER.info("Cortex sequentieller Modus: %s",
                     "AN" if cortex.sequential_mode else "AUS")
        await hass.services.async_call("persistent_notification", "create", {
            "title": "KONTINUUM Cortex – Sequentieller Modus",
            "message": (
                f"Sequentieller Modus: **{'AN' if cortex.sequential_mode else 'AUS'}**\n\n"
                f"{'Agents werden nacheinander befragt (für Single-GPU).' if cortex.sequential_mode else 'Agents werden parallel befragt.'}"
            ),
            "notification_id": "kontinuum_cortex_sequential",
        })

    async def handle_brain_review(call):
        """
        Brain Review: Cortex-Agents analysieren den Gehirn-Zustand.

        Gibt den Agents Zugriff auf die vollständige Gehirn-Statistik
        und lässt sie Empfehlungen ableiten. Ergebnis wird als
        persistent_notification gesendet.
        """
        cortex = brain["cortex"]
        if not cortex.enabled:
            _LOGGER.warning("Brain Review: Cortex nicht aktiv")
            return

        review = await cortex.brain_review(brain)

        # Ergebnis als Notification
        score = review.get("health_score", 0)
        analyses = review.get("analyses", [])

        msg_parts = [f"**Brain Health: {score}/100**\n"]
        for a in analyses:
            agent_name = a.get("agent", "?")
            analysis = a.get("analysis", a.get("error", "keine Antwort"))
            suggestions = a.get("suggestions", [])
            msg_parts.append(f"### {agent_name}")
            msg_parts.append(f"{analysis}")
            if suggestions:
                for s in suggestions:
                    msg_parts.append(f"- {s}")
            msg_parts.append("")

        message = "\n".join(msg_parts)
        await hass.services.async_call(
            "persistent_notification", "create",
            {"title": f"KONTINUUM Brain Review (Score: {score}/100)",
             "message": message,
             "notification_id": "kontinuum_brain_review"},
        )

        # Review im Brain speichern + History
        brain["_last_brain_review"] = review
        data_dir = brain.get("_data_dir", hass.config.path(DATA_DIR))
        history_entry = {
            "type": "brain_review",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health_score": score,
            "agents_consulted": review.get("agents_consulted", 0),
            "analyses": analyses,
        }
        await hass.async_add_executor_job(
            _write_history_entry, data_dir, "brain_review", history_entry
        )
        _LOGGER.info("Brain Review abgeschlossen: Score %d/100", score)

    hass.services.async_register(DOMAIN, "enable_scenes", handle_enable_scenes)
    hass.services.async_register(DOMAIN, "disable_scenes", handle_disable_scenes)
    hass.services.async_register(DOMAIN, "set_scene", handle_set_scene)
    hass.services.async_register(DOMAIN, "status", handle_status)
    hass.services.async_register(DOMAIN, "export_brain", handle_export_brain)
    hass.services.async_register(DOMAIN, "activate", handle_activate)
    hass.services.async_register(DOMAIN, "deactivate", handle_deactivate)
    hass.services.async_register(DOMAIN, "set_mode", handle_set_mode)
    hass.services.async_register(DOMAIN, "confirm_action", handle_confirm_action)
    hass.services.async_register(DOMAIN, "reject_action", handle_reject_action)
    hass.services.async_register(DOMAIN, "configure_agent", handle_configure_agent)
    hass.services.async_register(DOMAIN, "cortex_consult", handle_cortex_consult)
    hass.services.async_register(DOMAIN, "remove_agent", handle_cortex_remove_agent)
    hass.services.async_register(DOMAIN, "cortex_sequential", handle_cortex_sequential)
    hass.services.async_register(DOMAIN, "brain_review", handle_brain_review)

    _LOGGER.info("Services registriert: enable_scenes, disable_scenes, set_scene, "
                 "status, export_brain, activate, deactivate, set_mode, "
                 "confirm_action, reject_action, "
                 "configure_agent, cortex_consult, remove_agent, brain_review")


# ══════════════════════════════════════════════════════════════════
# ENTITY DISCOVERY
# ══════════════════════════════════════════════════════════════════

async def _discover_entities(hass, thalamus):
    """Entdeckt Entities aus HA-Registries (mit Label-Support v0.14.0)."""
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

    # Label-Registry (HA 2024.1+)
    label_names = {}
    try:
        from homeassistant.helpers.label_registry import async_get as get_lr
        lr = get_lr(hass)
        label_names = {l.label_id: l.name for l in lr.async_list_labels()}
    except (ImportError, AttributeError):
        _LOGGER.debug("Label-Registry nicht verfügbar – Labels werden ignoriert")

    for entity in er.entities.values():
        entity_id = entity.entity_id
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        device_class = entity.device_class or entity.original_device_class or ""
        unit = entity.unit_of_measurement or ""
        name = entity.name or entity.original_name or entity_id

        # Area: Entity → Device → None
        area_name = ""
        if entity.area_id and entity.area_id in areas:
            area_name = areas[entity.area_id]
        elif entity.device_id:
            device = dr.async_get(entity.device_id)
            if device and device.area_id and device.area_id in areas:
                area_name = areas[device.area_id]

        # Labels sammeln (v0.14.0)
        entity_labels = []
        if hasattr(entity, "labels") and entity.labels:
            entity_labels = [
                label_names[lid] for lid in entity.labels
                if lid in label_names
            ]

        thalamus.register_entity(
            entity_id=entity_id,
            ha_area=area_name,
            device_class=str(device_class) if device_class else "",
            domain=domain,
            friendly_name=str(name) if name else "",
            unit=str(unit) if unit else "",
            labels=entity_labels,
        )

    _LOGGER.info(
        "Entity Discovery: %d Entities in %d Räumen registriert (Labels: %d)",
        len(thalamus.entity_semantic), len(thalamus._known_rooms),
        len(label_names),
    )


def _update_persons_sensor(hass):
    """Aktualisiert den Personen-Zähler via Dispatcher."""
    home_list = []
    away_list = []

    for state in hass.states.async_all("person"):
        name = state.attributes.get("friendly_name", state.entity_id)
        if state.state == "home":
            home_list.append(name)
        else:
            away_list.append(name)

    # Im Brain speichern für Cortex-Kontext
    brain = hass.data.get(DOMAIN)
    if brain:
        brain["_persons_home"] = home_list

    async_dispatcher_send(hass, SIGNAL_PERSONS_UPDATE,
                          {"home": home_list, "away": away_list})


# ══════════════════════════════════════════════════════════════════
# BRAIN PERSISTENCE
# ══════════════════════════════════════════════════════════════════

def _save_brain(brain, path=None):
    """Speichert das Gehirn komprimiert als JSON.gz (RPi-SD-Card-schonend)."""
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
            "basal_ganglia": brain["basal_ganglia"].to_dict(),
            "prefrontal": brain["prefrontal"].to_dict(),
            "cortex": brain["cortex"].to_dict(),
            "cortex_agents": brain.get("_cortex_agents", {}),
            "cortex_patterns": brain.get("_cortex_patterns", {}),
            "scenes_enabled": brain.get("_scenes_enabled", False),
            "scene_config": brain.get("_scene_config", {}),
            # v0.18.0: Notifikations-State persistieren (kein Spam bei Neustart)
            "notified_milestones": list(brain.get("_notified_milestones", set())),
            "notified_modes": list(brain.get("_notified_modes", set())),
            "notified_rules": list(brain.get("_notified_rules", set())),
        }

        tmp_path = path + ".tmp"
        raw = json.dumps(data, separators=(",", ":"), default=str).encode()
        with gzip.open(tmp_path, "wb", compresslevel=6) as f:
            f.write(raw)
        os.replace(tmp_path, path)

        _LOGGER.debug("Gehirn gespeichert (%d KB): %s", len(raw) // 1024, path)
    except Exception as e:
        _LOGGER.error("Fehler beim Speichern: %s", e)


def _load_brain(brain, path):
    """Lädt das Gehirn aus einer JSON.gz-Datei (mit Fallback auf altes brain.json)."""
    # Fallback: altes unkomprimiertes brain.json migrieren
    legacy_path = os.path.join(os.path.dirname(path), BRAIN_FILE_LEGACY)
    if not os.path.exists(path) and os.path.exists(legacy_path):
        _LOGGER.info("Migriere brain.json → brain.json.gz …")
        try:
            with open(legacy_path) as f:
                legacy_data = json.load(f)
            raw = json.dumps(legacy_data, separators=(",", ":"), default=str).encode()
            with gzip.open(path, "wb", compresslevel=6) as f:
                f.write(raw)
            os.rename(legacy_path, legacy_path + ".migrated")
            _LOGGER.info("Migration abgeschlossen, altes brain.json umbenannt.")
        except Exception as e:
            _LOGGER.warning("Migration fehlgeschlagen (%s), starte frisch.", e)
            return

    if not os.path.exists(path):
        _LOGGER.info("Kein gespeichertes Gehirn gefunden – starte frisch.")
        return

    try:
        with gzip.open(path, "rb") as f:
            data = json.loads(f.read())

        brain["thalamus"].from_dict(data.get("thalamus", {}))
        brain["hippocampus"].from_dict(data.get("hippocampus", {}))
        brain["hypothalamus"].from_dict(data.get("hypothalamus", {}))
        brain["spatial"].from_dict(data.get("spatial", {}))
        brain["insula"].from_dict(data.get("insula", {}))
        brain["amygdala"].from_dict(data.get("amygdala", {}))
        brain["cerebellum"].from_dict(data.get("cerebellum", {}))
        brain["basal_ganglia"].from_dict(data.get("basal_ganglia", {}))
        brain["prefrontal"].from_dict(data.get("prefrontal", {}))
        brain["cortex"].from_dict(data.get("cortex", {}))
        # Cortex-Agent-Config wiederherstellen
        cortex_agents = data.get("cortex_agents", {})
        if cortex_agents:
            brain["_cortex_agents"] = cortex_agents
            brain["cortex"].configure(list(cortex_agents.values()))
        brain["_cortex_patterns"] = data.get("cortex_patterns", {})
        brain["_scenes_enabled"] = data.get("scenes_enabled", False)
        brain["_scene_config"] = data.get("scene_config", _default_scene_config())
        # v0.18.0: Notifikations-State wiederherstellen (kein Spam bei Neustart)
        brain["_notified_milestones"] = set(data.get("notified_milestones", []))
        brain["_notified_modes"] = set(data.get("notified_modes", []))
        brain["_notified_rules"] = set(data.get("notified_rules", []))

        # v0.11.0 Migration: Unknown-Tokens bereinigen
        _migrate_purge_unknown(brain)

        # v0.14.2 Migration: Float-Tokens und HACS-Pre-Release-Tokens bereinigen
        _migrate_purge_float_tokens(brain)

        # v0.15.0 Migration: System-Entity-Tokens bereinigen
        _migrate_purge_system_tokens(brain)

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


def _migrate_purge_float_tokens(brain):
    """
    v0.14.2 Migration: Bereinigt Float-Tokens und HACS-Tokens aus dem Vokabular.
    Entfernt Token-Strings wie:
    - "server.network.0.546"  (unbucketed Float-Wert)
    - "area_unknown.solar.*"  (falsche Semantik durch pv→pve-Bug)
    - "*._pre_release*"       (HACS Pre-Release Switches)
    - "*._cell_voltage*"      (Batteriezellen-Spannungen)
    """
    thalamus = brain["thalamus"]
    hippocampus = brain["hippocampus"]

    # Float-Tokens: state ist eine Zahl mit Dezimalstelle (z.B. "server.network.0.546")
    float_pattern = re.compile(r"^[^.]+\.[^.]+\.\d+\.\d+$")
    noise_patterns = [
        re.compile(r"_pre_release"),
        re.compile(r"_cell_voltage"),
        re.compile(r"_cell_\d+"),
    ]

    purge_ids = set()
    for token_str, token_id in list(thalamus.token_to_id.items()):
        is_noise = bool(float_pattern.match(token_str))
        if not is_noise:
            for pat in noise_patterns:
                if pat.search(token_str):
                    is_noise = True
                    break
        if is_noise:
            purge_ids.add(token_id)
            del thalamus.token_to_id[token_str]
            thalamus.id_to_token.pop(token_id, None)

    if not purge_ids:
        _LOGGER.info("v0.14.2 Migration: Keine Float/Noise-Tokens gefunden.")
        return

    # Hippocampus: Transitions und Totals bereinigen
    purged = 0
    for bucket in list(hippocampus.transitions.keys()):
        for ngram in list(hippocampus.transitions[bucket].keys()):
            if any(t in purge_ids for t in ngram):
                del hippocampus.transitions[bucket][ngram]
                hippocampus.totals[bucket].pop(ngram, None)
                purged += 1

    _LOGGER.warning(
        "v0.14.2 Migration: %d Float/Noise-Tokens bereinigt, %d Transitions entfernt. "
        "Vokabular: %d → %d Einträge",
        len(purge_ids), purged,
        len(thalamus.token_to_id) + len(purge_ids),
        len(thalamus.token_to_id),
    )


def _migrate_purge_system_tokens(brain):
    """
    v0.15.0 Migration: Entfernt System-Entity-Tokens aus dem Gehirn.

    HA-Infrastruktur-Entities (CPU-Metriken, Addon-States, Supervisor)
    erzeugen Transitions die nichts mit menschlichem Verhalten zu tun haben.
    """
    thalamus = brain["thalamus"]
    hippocampus = brain["hippocampus"]

    # Tokens die von System-Entities stammen (area_unknown.cpu.*, etc.)
    system_patterns = [
        re.compile(r"\.cpu\."),        # CPU-Metriken
        re.compile(r"\.gpu\."),        # GPU-Metriken
        re.compile(r"\.network\."),    # Network-I/O
    ]
    # Entity-IDs die jetzt von IGNORED_PATTERNS gefiltert werden
    system_entity_patterns = [
        re.compile(r"^sensor\.home_assistant_"),
        re.compile(r"^sensor\.hassio_"),
        re.compile(r"^binary_sensor\.hassio_"),
        re.compile(r"^sensor\.supervisor_"),
        re.compile(r"^binary_sensor\.supervisor_"),
        re.compile(r"^binary_sensor\.\w+_running$"),
        re.compile(r"_cpu_prozent$"),
        re.compile(r"_cpu_percent$"),
        re.compile(r"_memory_percent$"),
        re.compile(r"_speicher_prozent$"),
    ]

    # 1. System-Entity-IDs aus Thalamus-Mapping entfernen
    purge_entities = []
    for entity_id in list(thalamus.entity_room.keys()):
        for pat in system_entity_patterns:
            if pat.search(entity_id):
                purge_entities.append(entity_id)
                break

    for eid in purge_entities:
        thalamus.entity_room.pop(eid, None)
        thalamus.entity_semantic.pop(eid, None)
        thalamus.entity_last_token.pop(eid, None)

    # 2. System-Tokens aus Vokabular entfernen
    purge_ids = set()
    for token_str, token_id in list(thalamus.token_to_id.items()):
        for pat in system_patterns:
            if pat.search(token_str):
                purge_ids.add(token_id)
                del thalamus.token_to_id[token_str]
                thalamus.id_to_token.pop(token_id, None)
                break

    if not purge_ids and not purge_entities:
        return

    # 3. Hippocampus: Transitions bereinigen
    purged = 0
    for bucket in list(hippocampus.transitions.keys()):
        for ngram in list(hippocampus.transitions[bucket].keys()):
            if any(t in purge_ids for t in ngram):
                del hippocampus.transitions[bucket][ngram]
                hippocampus.totals[bucket].pop(ngram, None)
                purged += 1
                continue
            for tok_id in list(hippocampus.transitions[bucket][ngram].keys()):
                if tok_id in purge_ids:
                    count = hippocampus.transitions[bucket][ngram].pop(tok_id)
                    hippocampus.totals[bucket][ngram] = max(
                        0, hippocampus.totals[bucket].get(ngram, 0) - count
                    )
                    purged += 1

    _LOGGER.warning(
        "v0.15.0 Migration: %d System-Entities entfernt, %d System-Tokens bereinigt, "
        "%d Transitions entfernt",
        len(purge_entities), len(purge_ids), purged,
    )
