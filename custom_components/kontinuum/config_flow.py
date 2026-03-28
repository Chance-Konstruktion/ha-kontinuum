"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Config Flow                                        ║
║  Ein-Klick-Installation über Integrationen → Hinzufügen        ║
║  Kein configuration.yaml nötig.                                 ║
║                                                                  ║
║  Options Flow (v0.15.0 – Menu-basiert):                         ║
║  - Menu: Allgemein | Cortex Agents | Fertig                     ║
║  - Allgemein: Preset, Track-Mode, Dashboard, Home-Only          ║
║  - Cortex: Enable + Agents verwalten (ohne Datenverlust)        ║
║  - Agents bleiben erhalten bis explizit gelöscht                ║
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
    """Fragt Ollama nach verfügbaren Modellen ab."""
    tags_url = f"{url.rstrip('/')}/api/tags"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(tags_url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                models.sort()
                return models
    except (aiohttp.ClientError, TimeoutError, Exception):
        return []


async def _test_ollama_connection(url: str) -> tuple[bool, str]:
    """Testet die Verbindung zu Ollama."""
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
# Options Flow (Menu-basiert, v0.15.0)
# ══════════════════════════════════════════════════════════════════

class KontinuumOptionsFlow(config_entries.OptionsFlow):
    """
    Options Flow – Menu-basierte Konfiguration (v0.15.0).

    Menu:
      → Allgemein:     Preset, Track-Mode, Dashboard, Home-Only
      → Cortex Agents: Enable/Disable + bis zu 4 Agents verwalten
      → Fertig:        Speichern & neu laden

    Agents werden aus der bestehenden Config geladen und bleiben
    erhalten bis sie explizit entfernt werden. Kein Datenverlust
    durch vergessene Checkboxen.
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
        self._editing_slot = 0

    # ── Menu (Hauptnavigation) ────────────────────────────────────

    async def async_step_init(self, user_input=None):
        """Hauptmenü: Allgemein | Cortex Agents | Fertig."""
        # Beim ersten Aufruf: bestehende Agents laden
        if not self._data:
            self._data = dict(self.config_entry.data)
            self._agents = dict(self._data.get("cortex_agents", {}))

        return self.async_show_menu(
            step_id="init",
            menu_options=["general", "cortex", "finish"],
        )

    # ── Allgemeine Einstellungen ──────────────────────────────────

    async def async_step_general(self, user_input=None):
        """Allgemein: Preset, Track-Mode, Betriebsmodus, Dashboard, Home-Only."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_init()

        current = self._data
        preset_options = {k: v["label"] for k, v in PRESETS.items()}
        track_mode_options = {
            "standard": "Standard (all entities, opt-out)",
            "labeled": "Labeled only (opt-in: only 'kontinuum' label)",
            "auto": "Automatic (smart heuristic filter)",
        }
        operation_mode_options = {
            "shadow": "👁️ Shadow – Nur beobachten, keine Aktionen",
            "confirm": "✋ Confirm – Fragt vor jeder Aktion",
            "active": "⚡ Active – Handelt selbstständig",
        }

        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema({
                vol.Required("preset", default=current.get("preset", "ausgeglichen")): vol.In(
                    preset_options
                ),
                vol.Required("operation_mode", default=current.get("operation_mode", "shadow")): vol.In(
                    operation_mode_options
                ),
                vol.Required("track_mode", default=current.get("track_mode", "standard")): vol.In(
                    track_mode_options
                ),
                vol.Required("enable_dashboard", default=current.get("enable_dashboard", True)): bool,
                vol.Required("home_only_mode", default=current.get("home_only_mode", False)): bool,
            }),
        )

    # ── Cortex Einstellungen ──────────────────────────────────────

    async def async_step_cortex(self, user_input=None):
        """Cortex: Enable + Optionen + Agent-Übersicht."""
        if user_input is not None:
            self._data["enable_cortex"] = user_input.get("enable_cortex", False)
            self._data["sequential_mode"] = user_input.get("sequential_mode", False)
            self._data["discussion_rounds"] = user_input.get("discussion_rounds", 2)

            if not self._data["enable_cortex"]:
                return await self.async_step_init()

            # Cortex aktiv → Agent-Übersicht
            return await self.async_step_agents_overview()

        return self.async_show_form(
            step_id="cortex",
            data_schema=vol.Schema({
                vol.Required("enable_cortex", default=self._data.get("enable_cortex", False)): bool,
                vol.Required("sequential_mode", default=self._data.get("sequential_mode", False)): bool,
                vol.Required(
                    "discussion_rounds", default=self._data.get("discussion_rounds", 2),
                ): vol.In({1: "1 Runde", 2: "2 Runden", 3: "3 Runden"}),
            }),
        )

    # ── Agent-Übersicht (zeigt konfigurierte Agents) ─────────────

    async def async_step_agents_overview(self, user_input=None):
        """Zeigt konfigurierte Agents und bietet Edit/Add/Remove."""
        if user_input is not None:
            action = user_input.get("action", "back")

            if action == "back":
                return await self.async_step_init()
            elif action == "add":
                # Nächsten freien Slot finden (1-4)
                for slot in range(1, 5):
                    if str(slot) not in self._agents:
                        self._editing_slot = slot
                        return await self.async_step_agent_setup()
                # Alle Slots belegt
                return await self.async_step_agents_overview()
            elif action.startswith("edit_"):
                self._editing_slot = int(action.split("_")[1])
                return await self.async_step_agent_setup()
            elif action.startswith("remove_"):
                slot = action.split("_")[1]
                self._agents.pop(slot, None)
                return await self.async_step_agents_overview()

        # Aktionen-Dropdown bauen
        actions = {}

        # Bestehende Agents anzeigen
        for slot in sorted(self._agents.keys()):
            agent = self._agents[slot]
            name = agent.get("name", "custom")
            provider = PROVIDERS.get(agent.get("provider", ""), {}).get("label", agent.get("provider", "?"))
            model = agent.get("model", "?")
            actions[f"edit_{slot}"] = f"✏️ Agent {slot}: {name} ({provider} / {model})"

        # Entfernen-Optionen
        for slot in sorted(self._agents.keys()):
            agent = self._agents[slot]
            actions[f"remove_{slot}"] = f"🗑️ Agent {slot} entfernen ({agent.get('name', 'custom')})"

        # Neuen Agent hinzufügen (wenn Platz)
        if len(self._agents) < 4:
            actions["add"] = "➕ Neuen Agent hinzufügen"

        actions["back"] = "↩️ Zurück zum Hauptmenü"

        return self.async_show_form(
            step_id="agents_overview",
            data_schema=vol.Schema({
                vol.Required("action", default="back"): vol.In(actions),
            }),
        )

    # ── Agent Setup (Provider + URL) ─────────────────────────────

    async def async_step_agent_setup(self, user_input=None):
        """Agent konfigurieren: Provider, Rolle, URL, API-Key."""
        errors = {}
        slot = self._editing_slot

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
                    _LOGGER.warning("Ollama nicht erreichbar unter %s: %s", url, msg)
                else:
                    self._discovered_models = await _fetch_ollama_models(url)

            if not errors:
                return await self.async_step_agent_model()

        # Bestehende Werte laden
        existing = self._agents.get(str(slot), {})
        slot_defaults = {1: "comfort", 2: "energy", 3: "safety", 4: "coordinator"}

        return self.async_show_form(
            step_id="agent_setup",
            data_schema=vol.Schema({
                vol.Required(
                    "role", default=existing.get("name", slot_defaults.get(slot, "custom")),
                ): vol.In(AGENT_ROLES),
                vol.Required(
                    "provider", default=existing.get("provider", "ollama"),
                ): vol.In(PROVIDER_OPTIONS),
                vol.Optional(
                    "url",
                    description={"suggested_value": existing.get("url", "")},
                ): str,
                vol.Optional(
                    "api_key",
                    description={"suggested_value": existing.get("api_key", "")},
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            }),
            errors=errors,
            description_placeholders={"slot": str(slot)},
        )

    # ── Agent Model ──────────────────────────────────────────────

    async def async_step_agent_model(self, user_input=None):
        """Agent: Modell wählen + System-Prompt."""
        slot = self._editing_slot

        if user_input is not None:
            provider = self._current_provider
            provider_info = PROVIDERS.get(provider, {})
            role = self._current_role

            model = user_input.get("model", "")
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

            # Zurück zur Agent-Übersicht
            return await self.async_step_agents_overview()

        # ── Formular bauen ──
        existing = self._agents.get(str(slot), {})

        if self._current_provider == "ollama" and self._discovered_models:
            model_options = {m: m for m in self._discovered_models}
            default_model = existing.get("model", "")
            if default_model not in model_options:
                default_model = self._discovered_models[0]

            schema_dict = {
                vol.Required("model", default=default_model): vol.In(model_options),
            }
            description_placeholders = {
                "status": f"Verbunden – {len(self._discovered_models)} Modelle gefunden",
                "slot": str(slot),
            }
        else:
            provider_info = PROVIDERS.get(self._current_provider, {})
            schema_dict = {
                vol.Optional(
                    "model",
                    description={
                        "suggested_value": existing.get(
                            "model", provider_info.get("default_model", ""),
                        ),
                    },
                ): str,
            }
            if self._current_provider == "ollama":
                description_placeholders = {
                    "status": "Verbunden – keine Modelle gefunden. Installiere mit: ollama pull llama3.2",
                    "slot": str(slot),
                }
            else:
                provider_label = provider_info.get("label", self._current_provider)
                description_placeholders = {
                    "status": f"Provider: {provider_label}",
                    "slot": str(slot),
                }

        # System-Prompt
        schema_dict[vol.Optional(
            "system_prompt",
            description={
                "suggested_value": existing.get("system_prompt", ""),
            },
        )] = str

        return self.async_show_form(
            step_id="agent_model",
            data_schema=vol.Schema(schema_dict),
            description_placeholders=description_placeholders,
        )

    # ── Fertig (Speichern) ───────────────────────────────────────

    async def async_step_finish(self, user_input=None):
        """Speichert alle Einstellungen und lädt die Integration neu."""
        return await self._save_and_finish()

    async def _save_and_finish(self):
        """Speichert alle Einstellungen und lädt die Integration neu."""
        preset_key = self._data.get("preset", "ausgeglichen")
        preset = PRESETS.get(preset_key, PRESETS["ausgeglichen"])

        op_mode = self._data.get("operation_mode", "shadow")
        new_data = {
            **self.config_entry.data,
            "preset": preset_key,
            "operation_mode": op_mode,
            "shadow_mode": op_mode == "shadow",
            "track_mode": self._data.get("track_mode", "standard"),
            "enable_dashboard": self._data.get("enable_dashboard", True),
            "home_only_mode": self._data.get("home_only_mode", False),
            "enable_cortex": self._data.get("enable_cortex", False),
            "sequential_mode": self._data.get("sequential_mode", False),
            "discussion_rounds": self._data.get("discussion_rounds", 2),
            **{k: v for k, v in preset.items() if k != "label"},
        }

        # Agents: IMMER aus _agents übernehmen (nie stillschweigend löschen)
        if self._data.get("enable_cortex", False) and self._agents:
            new_data["cortex_agents"] = self._agents
        elif not self._data.get("enable_cortex", False):
            new_data.pop("cortex_agents", None)

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )

        await self.hass.config_entries.async_reload(self.config_entry.entry_id)

        return self.async_create_entry(title="", data={})
