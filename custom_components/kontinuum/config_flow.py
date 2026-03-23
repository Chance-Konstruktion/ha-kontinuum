"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Config Flow                                        ║
║  Ein-Klick-Installation über Integrationen → Hinzufügen        ║
║  Kein configuration.yaml nötig.                                 ║
╚══════════════════════════════════════════════════════════════════╝
"""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

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
        "hippocampus_decay": 0.997,     # Langsamer vergessen
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


class KontinuumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für KONTINUUM."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Erster Schritt: Persönlichkeit wählen."""
        if user_input is not None:
            # Nur eine Instanz erlauben
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            preset_key = user_input["preset"]
            preset = PRESETS[preset_key]

            # Weiter zum Dashboard-Schritt
            self._preset_key = preset_key
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
    """Options Flow – Persönlichkeit nachträglich ändern."""

    async def async_step_init(self, user_input=None):
        """Options-Formular."""
        if user_input is not None:
            preset_key = user_input["preset"]
            preset = PRESETS[preset_key]

            # Config Entry updaten
            new_data = {
                **self.config_entry.data,
                "preset": preset_key,
                "enable_dashboard": user_input.get("enable_dashboard", True),
                "enable_cortex": user_input.get("enable_cortex", False),
                **{k: v for k, v in preset.items() if k != "label"},
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            return self.async_create_entry(title="", data={})

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
