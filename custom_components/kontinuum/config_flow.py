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
║  - Ollama: Automatische URL-Normalisierung + Modell-Discovery   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .cortex import PROVIDERS, DEFAULT_PROMPTS

_LOGGER = logging.getLogger(__name__)

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
    "coordinator": "Coordinator – Leitet die anderen Agents, trifft finale Entscheidung",
    "custom": "Custom – Eigene Rolle mit eigenem Prompt",
}


# ══════════════════════════════════════════════════════════════════
# Helper: URL-Normalisierung + Ollama Model Discovery
# ══════════════════════════════════════════════════════════════════

def _normalize_url(url: str, provider: str = "ollama") -> str:
    """
    Normalisiert eine URL: Fügt http:// und Standardport hinzu.

    Beispiele:
        "localhost"           → "http://localhost:11434"
        "192.168.1.100"       → "http://192.168.1.100:11434"
        "192.168.1.100:11434" → "http://192.168.1.100:11434"
        "http://myhost:8080"  → "http://myhost:8080"  (unverändert)
        ""                    → default_url des Providers
    """
    if not url or not url.strip():
        return PROVIDERS.get(provider, {}).get("default_url", "")

    url = url.strip().rstrip("/")

    # Schema hinzufügen wenn fehlend
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"

    # Port hinzufügen für Ollama wenn keiner angegeben
    if provider == "ollama":
        # Prüfe ob ein Port vorhanden ist (nach dem Host)
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.port:
            url = f"{url}:11434"

    return url


async def _fetch_ollama_models(url: str, timeout: int = 5) -> list[str]:
    """
    Fragt Ollama nach verfügbaren Modellen ab.

    Returns: Sortierte Liste von Modell-Namen, oder leere Liste bei Fehler.
    """
    tags_url = f"{url.rstrip('/')}/api/tags"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(tags_url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Ollama %s returned %d", tags_url, resp.status)
                    return []
                data = await resp.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    if name:
                        models.append(name)
                models.sort()
                return models
    except (aiohttp.ClientError, TimeoutError, Exception) as e:
        _LOGGER.debug("Ollama model fetch failed (%s): %s", tags_url, e)
        return []


async def _test_ollama_connection(url: str) -> tuple[bool, str]:
    """
    Testet die Verbindung zu Ollama.

    Returns: (success, message)
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url.rstrip("/"),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    if "Ollama" in text:
                        return True, "Ollama erreichbar"
                    return True, f"Server erreichbar (Status {resp.status})"
                return False, f"HTTP {resp.status}"
    except (aiohttp.ClientError, TimeoutError) as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════
# Config Flow (Ersteinrichtung)
# ══════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════
# Options Flow (Nachträgliche Konfiguration)
# ══════════════════════════════════════════════════════════════════

class KontinuumOptionsFlow(config_entries.OptionsFlow):
    """
    Options Flow – Mehrstufige Konfiguration.

    Schritt 1 (init):          Persönlichkeit + Cortex aktivieren
    Schritt 2 (agent_1_setup): Provider + URL + Verbindungstest
    Schritt 3 (agent_1_model): Modell wählen (Dropdown bei Ollama)
    ... (wiederholt für Agent 2+3)
    """

    def __init__(self):
        """Init."""
        self._data = {}
        self._agents = {}
        # Temporäre Daten für den aktuellen Agent-Schritt
        self._current_provider = ""
        self._current_url = ""
        self._current_api_key = ""
        self._current_role = ""
        self._discovered_models = []

    async def async_step_init(self, user_input=None):
        """Schritt 1: Grundeinstellungen."""
        if user_input is not None:
            self._data = user_input
            # Wenn Cortex aktiviert → Cortex-Optionen
            if user_input.get("enable_cortex", False):
                return await self.async_step_cortex_options()
            # Sonst direkt speichern
            return await self._save_and_finish()

        current = self.config_entry.data.get("preset", "ausgeglichen")
        current_dashboard = self.config_entry.data.get("enable_dashboard", True)
        current_cortex = self.config_entry.data.get("enable_cortex", False)
        current_home_only = self.config_entry.data.get("home_only_mode", False)
        preset_options = {k: v["label"] for k, v in PRESETS.items()}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("preset", default=current): vol.In(
                    preset_options
                ),
                vol.Required("enable_dashboard", default=current_dashboard): bool,
                vol.Required("home_only_mode", default=current_home_only): bool,
                vol.Required("enable_cortex", default=current_cortex): bool,
            }),
        )

    # ── Cortex Optionen (Sequential, Runden) ─────────────────────

    async def async_step_cortex_options(self, user_input=None):
        """Cortex-Optionen: Sequential Mode, Diskussionsrunden."""
        if user_input is not None:
            self._data["sequential_mode"] = user_input.get("sequential_mode", False)
            self._data["discussion_rounds"] = user_input.get("discussion_rounds", 2)
            return await self.async_step_agent_1_setup()

        current_seq = self.config_entry.data.get("sequential_mode", False)
        current_rounds = self.config_entry.data.get("discussion_rounds", 2)

        return self.async_show_form(
            step_id="cortex_options",
            data_schema=vol.Schema({
                vol.Required("sequential_mode", default=current_seq): bool,
                vol.Required(
                    "discussion_rounds", default=current_rounds,
                ): vol.In({1: "1 Runde", 2: "2 Runden", 3: "3 Runden"}),
            }),
        )

    # ── Agent 1: Setup (Provider + URL) ──────────────────────────

    async def async_step_agent_1_setup(self, user_input=None):
        """Agent 1: Provider, Rolle und URL wählen."""
        return await self._handle_agent_setup(
            user_input, slot=1, next_step="agent_1_model",
            step_id="agent_1_setup",
        )

    async def async_step_agent_1_model(self, user_input=None):
        """Agent 1: Modell wählen + Verbindungsstatus."""
        return await self._handle_agent_model(
            user_input, slot=1,
            next_step="agent_2_setup", step_id="agent_1_model",
            show_add_more=True,
        )

    # ── Agent 2: Setup + Model ───────────────────────────────────

    async def async_step_agent_2_setup(self, user_input=None):
        """Agent 2: Provider, Rolle und URL wählen."""
        return await self._handle_agent_setup(
            user_input, slot=2, next_step="agent_2_model",
            step_id="agent_2_setup",
        )

    async def async_step_agent_2_model(self, user_input=None):
        """Agent 2: Modell wählen."""
        return await self._handle_agent_model(
            user_input, slot=2,
            next_step="agent_3_setup", step_id="agent_2_model",
            show_add_more=True,
        )

    # ── Agent 3: Setup + Model ───────────────────────────────────

    async def async_step_agent_3_setup(self, user_input=None):
        """Agent 3: Provider, Rolle und URL wählen."""
        return await self._handle_agent_setup(
            user_input, slot=3, next_step="agent_3_model",
            step_id="agent_3_setup",
        )

    async def async_step_agent_3_model(self, user_input=None):
        """Agent 3: Modell wählen."""
        return await self._handle_agent_model(
            user_input, slot=3,
            next_step="agent_4_setup", step_id="agent_3_model",
            show_add_more=True,
        )

    # ── Agent 4: Setup + Model (Coordinator) ─────────────────────

    async def async_step_agent_4_setup(self, user_input=None):
        """Agent 4: Provider, Rolle und URL wählen."""
        return await self._handle_agent_setup(
            user_input, slot=4, next_step="agent_4_model",
            step_id="agent_4_setup",
        )

    async def async_step_agent_4_model(self, user_input=None):
        """Agent 4: Modell wählen."""
        return await self._handle_agent_model(
            user_input, slot=4,
            next_step=None, step_id="agent_4_model",
            show_add_more=False,
        )

    # ── Generischer Handler: Agent Setup (Provider + URL) ────────

    async def _handle_agent_setup(self, user_input, slot, next_step, step_id):
        """Generischer Setup-Schritt: Provider, Rolle, URL, API-Key."""
        errors = {}

        if user_input is not None:
            provider = user_input.get("provider", "ollama")
            raw_url = user_input.get("url", "")
            url = _normalize_url(raw_url, provider)

            self._current_provider = provider
            self._current_url = url
            self._current_api_key = user_input.get("api_key", "")
            self._current_role = user_input.get("role", "comfort")

            # Verbindungstest bei Ollama
            if provider == "ollama":
                connected, msg = await _test_ollama_connection(url)
                if not connected:
                    errors["url"] = "ollama_unreachable"
                    _LOGGER.warning(
                        "Ollama nicht erreichbar unter %s: %s", url, msg)
                else:
                    # Modelle vorab laden
                    self._discovered_models = await _fetch_ollama_models(url)

            if not errors:
                return await getattr(self, f"async_step_{next_step}")()

        # Bestehende Werte laden
        existing = self.config_entry.data.get(
            "cortex_agents", {}
        ).get(str(slot), {})

        slot_defaults = {1: "comfort", 2: "energy", 3: "safety", 4: "coordinator"}
        default_role = existing.get(
            "name",
            slot_defaults.get(slot, "custom"),
        )

        schema_dict = {
            vol.Required(
                "role", default=default_role,
            ): vol.In(AGENT_ROLES),
            vol.Required(
                "provider",
                default=existing.get("provider", "ollama"),
            ): vol.In(PROVIDER_OPTIONS),
            vol.Optional(
                "url",
                description={"suggested_value": existing.get("url", "")},
            ): str,
            vol.Optional(
                "api_key",
                description={"suggested_value": existing.get("api_key", "")},
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    # ── Generischer Handler: Agent Model ─────────────────────────

    async def _handle_agent_model(self, user_input, slot, next_step,
                                  step_id, show_add_more):
        """Generischer Modell-Schritt: Modell wählen + System-Prompt."""
        if user_input is not None:
            # Agent zusammenbauen
            provider = self._current_provider
            provider_info = PROVIDERS.get(provider, {})
            role = self._current_role

            model = user_input.get("model", "")
            # Bei Ollama-Dropdown kann das Model-Feld der Key sein
            if not model:
                model = provider_info.get("default_model", "")

            self._agents[str(slot)] = {
                "name": role if role != "custom" else "custom",
                "provider": provider,
                "model": model,
                "url": self._current_url,
                "api_key": self._current_api_key,
                "system_prompt": (user_input.get("system_prompt")
                                  or DEFAULT_PROMPTS.get(role, "")),
            }

            # Weiter oder fertig?
            if show_add_more and user_input.get("add_more", False):
                return await getattr(self, f"async_step_{next_step}")()
            return await self._save_and_finish()

        # ── Formular bauen ──
        existing = self.config_entry.data.get(
            "cortex_agents", {}
        ).get(str(slot), {})

        # Bei Ollama: Modelle als Dropdown anzeigen
        if self._current_provider == "ollama" and self._discovered_models:
            # Dropdown mit entdeckten Modellen
            model_options = {m: m for m in self._discovered_models}
            default_model = existing.get("model", "")
            if default_model not in model_options:
                # Default auf erstes verfügbares Modell
                default_model = self._discovered_models[0]

            schema_dict = {
                vol.Required(
                    "model", default=default_model,
                ): vol.In(model_options),
            }
            description_placeholders = {
                "status": f"Verbunden – {len(self._discovered_models)} Modelle gefunden",
                "provider": "Ollama",
                "url": self._current_url,
            }
        else:
            # Freitextfeld für Cloud-Provider oder wenn keine Modelle gefunden
            provider_info = PROVIDERS.get(self._current_provider, {})
            schema_dict = {
                vol.Optional(
                    "model",
                    description={
                        "suggested_value": existing.get(
                            "model",
                            provider_info.get("default_model", ""),
                        ),
                    },
                ): str,
            }
            if self._current_provider == "ollama":
                description_placeholders = {
                    "status": "Verbunden – keine Modelle gefunden. Installiere mit: ollama pull llama3.2",
                    "provider": "Ollama",
                    "url": self._current_url,
                }
            else:
                provider_label = PROVIDERS.get(
                    self._current_provider, {},
                ).get("label", self._current_provider)
                description_placeholders = {
                    "status": f"Provider: {provider_label}",
                    "provider": provider_label,
                    "url": self._current_url,
                }

        # System-Prompt
        schema_dict[vol.Optional(
            "system_prompt",
            description={
                "suggested_value": existing.get("system_prompt", ""),
            },
        )] = str

        # "Weiteren Agent hinzufügen?"
        if show_add_more:
            schema_dict[vol.Required("add_more", default=False)] = bool

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema_dict),
            description_placeholders=description_placeholders,
        )

    # ── Speichern ───────────────────────────────────────────────

    async def _save_and_finish(self):
        """Speichert alle Einstellungen und lädt die Integration neu."""
        preset_key = self._data.get(
            "preset",
            self.config_entry.data.get("preset", "ausgeglichen"),
        )
        preset = PRESETS.get(preset_key, PRESETS["ausgeglichen"])

        new_data = {
            **self.config_entry.data,
            "preset": preset_key,
            "enable_dashboard": self._data.get("enable_dashboard", True),
            "home_only_mode": self._data.get("home_only_mode", False),
            "enable_cortex": self._data.get("enable_cortex", False),
            "sequential_mode": self._data.get("sequential_mode", False),
            "discussion_rounds": self._data.get("discussion_rounds", 2),
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

        # Integration neu laden damit neue Entitäten erstellt werden
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)

        return self.async_create_entry(title="", data={})
