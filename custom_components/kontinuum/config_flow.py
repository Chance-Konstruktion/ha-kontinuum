"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Config Flow                                        ║
║  Ein-Klick-Installation über Integrationen → Hinzufügen        ║
║  Kein configuration.yaml nötig.                                 ║
║                                                                  ║
║  Options Flow:                                                   ║
║  - Persönlichkeit ändern                                        ║
║  - Cortex aktivieren/deaktivieren                               ║
║  - Bis zu 3 LLM-Agents konfigurieren (Provider/Modell/Key)     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .cortex import PROVIDERS, DEFAULT_PROMPTS

DOMAIN = "kontinuum"

PRESETS = {
    "mutig": {
        "label": "🔥 Mutig – Lernt schnell, macht anfangs Fehler",
        "cerebellum_min_obs": 3,
        "cerebellum_min_conf": 0.60,
        "hippocampus_decay": 0.993,
        "hippocampus_min_obs": 2,
        "shadow_mode": True,
    },
    "ausgeglichen": {
        "label": "⚖️ Ausgeglichen – Guter Kompromiss (empfohlen)",
        "cerebellum_min_obs": 4,
        "cerebellum_min_conf": 0.65,
        "hippocampus_decay": 0.997,
        "hippocampus_min_obs": 2,
        "shadow_mode": True,
    },
    "konservativ": {
        "label": "🛡️ Konservativ – Beobachtet lange, handelt selten",
        "cerebellum_min_obs": 7,
        "cerebellum_min_conf": 0.80,
        "hippocampus_decay": 0.998,
        "hippocampus_min_obs": 3,
        "shadow_mode": True,
    },
}

# Provider-Optionen fürs UI
PROVIDER_OPTIONS = {k: v["label"] for k, v in PROVIDERS.items()}

# Agent-Rollen mit Beschreibungen
AGENT_ROLES = {
    "comfort": "Comfort – Beleuchtung, Temperatur, Stimmung",
    "energy": "Energy – Solar, Batterie, Verbrauch",
    "safety": "Safety – Sicherheit, Anomalien, Veto-Recht",
    "custom": "Custom – Eigene Rolle mit eigenem Prompt",
}


class KontinuumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für KONTINUUM."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Erster Schritt: Persönlichkeit wählen."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            self._preset_key = user_input["preset"]
            return await self.async_step_dashboard()

        preset_options = {k: v["label"] for k, v in PRESETS.items()}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("preset", default="ausgeglichen"): vol.In(
                    preset_options
                ),
            }),
        )

    async def async_step_dashboard(self, user_input=None):
        """Zweiter Schritt: Dashboard aktivieren?"""
        if user_input is not None:
            preset_key = self._preset_key
            preset = PRESETS[preset_key]

            return self.async_create_entry(
                title="KONTINUUM",
                data={
                    "preset": preset_key,
                    "enable_dashboard": user_input.get("enable_dashboard", True),
                    **{k: v for k, v in preset.items() if k != "label"},
                },
            )

        return self.async_show_form(
            step_id="dashboard",
            data_schema=vol.Schema({
                vol.Required("enable_dashboard", default=True): bool,
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Options Flow für nachträgliche Änderungen."""
        return KontinuumOptionsFlow()


class KontinuumOptionsFlow(config_entries.OptionsFlow):
    """
    Options Flow – Mehrstufige Konfiguration.

    Schritt 1 (init):     Persönlichkeit + Cortex aktivieren
    Schritt 2 (agent_1):  Agent 1 konfigurieren (wenn Cortex an)
    Schritt 3 (agent_2):  Agent 2 konfigurieren (optional)
    Schritt 4 (agent_3):  Agent 3 konfigurieren (optional)
    """

    def __init__(self):
        """Init."""
        self._data = {}
        self._agents = {}

    async def async_step_init(self, user_input=None):
        """Schritt 1: Persönlichkeit + Cortex-Toggle."""
        if user_input is not None:
            self._data = user_input
            # Wenn Cortex aktiviert → Agent-Konfiguration
            if user_input.get("enable_cortex", False):
                return await self.async_step_agent_1()
            # Sonst direkt speichern
            return self._save_and_finish()

        current = self.config_entry.data.get("preset", "ausgeglichen")
        current_dashboard = self.config_entry.data.get("enable_dashboard", True)
        current_cortex = self.config_entry.data.get("enable_cortex", False)
        preset_options = {k: v["label"] for k, v in PRESETS.items()}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("preset", default=current): vol.In(
                    preset_options
                ),
                vol.Required("enable_dashboard", default=current_dashboard): bool,
                vol.Required("enable_cortex", default=current_cortex): bool,
            }),
        )

    # ── Agent 1 (Pflicht wenn Cortex an) ────────────────────────

    async def async_step_agent_1(self, user_input=None):
        """Schritt 2: Ersten Agent konfigurieren."""
        if user_input is not None:
            self._agents["1"] = self._parse_agent_input(user_input)
            if user_input.get("add_more", False):
                return await self.async_step_agent_2()
            return self._save_and_finish()

        return self._show_agent_form(
            "agent_1", slot=1, show_add_more=True,
        )

    # ── Agent 2 (Optional) ──────────────────────────────────────

    async def async_step_agent_2(self, user_input=None):
        """Schritt 3: Zweiten Agent konfigurieren."""
        if user_input is not None:
            self._agents["2"] = self._parse_agent_input(user_input)
            if user_input.get("add_more", False):
                return await self.async_step_agent_3()
            return self._save_and_finish()

        return self._show_agent_form(
            "agent_2", slot=2, show_add_more=True,
        )

    # ── Agent 3 (Optional, letzter) ────────────────────────────

    async def async_step_agent_3(self, user_input=None):
        """Schritt 4: Dritten Agent konfigurieren."""
        if user_input is not None:
            self._agents["3"] = self._parse_agent_input(user_input)
            return self._save_and_finish()

        return self._show_agent_form(
            "agent_3", slot=3, show_add_more=False,
        )

    # ── Helper: Agent-Formular ──────────────────────────────────

    def _show_agent_form(self, step_id: str, slot: int,
                         show_add_more: bool):
        """Zeigt das Agent-Konfigurationsformular."""
        # Bestehende Werte laden
        existing = self.config_entry.data.get(
            "cortex_agents", {}
        ).get(str(slot), {})

        schema_dict = {
            vol.Required(
                "role",
                default=existing.get("name", "comfort" if slot == 1
                                     else "energy" if slot == 2
                                     else "safety"),
            ): vol.In(AGENT_ROLES),
            vol.Required(
                "provider",
                default=existing.get("provider", "ollama"),
            ): vol.In(PROVIDER_OPTIONS),
            vol.Optional(
                "model",
                description={"suggested_value": existing.get("model", "")},
            ): str,
            vol.Optional(
                "url",
                description={"suggested_value": existing.get("url", "")},
            ): str,
            vol.Optional(
                "api_key",
                description={"suggested_value": existing.get("api_key", "")},
            ): str,
            vol.Optional(
                "system_prompt",
                description={
                    "suggested_value": existing.get("system_prompt", ""),
                },
            ): str,
        }

        if show_add_more:
            schema_dict[
                vol.Required("add_more", default=False)
            ] = bool

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema_dict),
        )

    def _parse_agent_input(self, user_input: dict) -> dict:
        """Konvertiert Formular-Eingabe in Agent-Config."""
        role = user_input.get("role", "custom")
        provider = user_input.get("provider", "ollama")
        provider_info = PROVIDERS.get(provider, {})

        return {
            "name": role if role != "custom" else "custom",
            "provider": provider,
            "model": (user_input.get("model")
                      or provider_info.get("default_model", "")),
            "url": (user_input.get("url")
                    or provider_info.get("default_url", "")),
            "api_key": user_input.get("api_key", ""),
            "system_prompt": (user_input.get("system_prompt")
                              or DEFAULT_PROMPTS.get(role, "")),
        }

    # ── Speichern ───────────────────────────────────────────────

    def _save_and_finish(self):
        """Speichert alle Einstellungen und beendet den Flow."""
        preset_key = self._data.get(
            "preset",
            self.config_entry.data.get("preset", "ausgeglichen"),
        )
        preset = PRESETS.get(preset_key, PRESETS["ausgeglichen"])

        new_data = {
            **self.config_entry.data,
            "preset": preset_key,
            "enable_dashboard": self._data.get("enable_dashboard", True),
            "enable_cortex": self._data.get("enable_cortex", False),
            **{k: v for k, v in preset.items() if k != "label"},
        }

        # Agents speichern (nur wenn Cortex aktiv)
        if self._data.get("enable_cortex", False) and self._agents:
            new_data["cortex_agents"] = self._agents
        elif not self._data.get("enable_cortex", False):
            # Cortex deaktiviert → Agents entfernen
            new_data.pop("cortex_agents", None)

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )

        return self.async_create_entry(title="", data={})
