"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Cortex (Multi-Agent LLM Layer)                     ║
║  Bewusstes Denken: Wenn das Unterbewusste unsicher ist          ║
║                                                                  ║
║  Biologisches Vorbild:                                           ║
║  Der Neokortex ist die Schicht für bewusstes Denken,            ║
║  Planen und komplexe Entscheidungen. Er wird nur aktiviert      ║
║  wenn Reflexe (Cerebellum) und Gewohnheiten (Basalganglien)     ║
║  nicht ausreichen.                                               ║
║                                                                  ║
║  Architektur:                                                    ║
║  Bis zu 3 LLM-Agents mit eigenen Rollen und System-Prompts.    ║
║  Provider: Ollama (lokal) oder Cloud (Gemini/OpenAI/Claude/Grok)║
║  Alle nutzen pure HTTP (aiohttp) – keine SDK-Dependencies.      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import logging
import time

import aiohttp

_LOGGER = logging.getLogger(__name__)

# ── Provider Konfiguration ──────────────────────────────────────

PROVIDERS = {
    "ollama": {
        "label": "Ollama (Lokal)",
        "default_url": "http://localhost:11434",
        "needs_key": False,
        "default_model": "llama3.2",
    },
    "openai": {
        "label": "OpenAI (ChatGPT)",
        "default_url": "https://api.openai.com",
        "needs_key": True,
        "default_model": "gpt-4o-mini",
    },
    "claude": {
        "label": "Anthropic (Claude)",
        "default_url": "https://api.anthropic.com",
        "needs_key": True,
        "default_model": "claude-sonnet-4-20250514",
    },
    "gemini": {
        "label": "Google (Gemini)",
        "default_url": "https://generativelanguage.googleapis.com",
        "needs_key": True,
        "default_model": "gemini-2.0-flash",
    },
    "grok": {
        "label": "xAI (Grok)",
        "default_url": "https://api.x.ai",
        "needs_key": True,
        "default_model": "grok-3-mini",
    },
}

# ── Default System-Prompts ──────────────────────────────────────

DEFAULT_PROMPTS = {
    "comfort": (
        "Du bist der Comfort-Agent im KONTINUUM Haus-Gehirn. "
        "Dein Ziel: Maximaler Komfort für die Bewohner. "
        "Du bewertest Beleuchtung, Temperatur, Modus und Stimmung. "
        "Antworte NUR mit JSON: "
        '{"action": "service.call oder null", "entity_id": "entity oder null", '
        '"reason": "kurze Begründung", "priority": 0-100}'
    ),
    "energy": (
        "Du bist der Energy-Agent im KONTINUUM Haus-Gehirn. "
        "Dein Ziel: Energieeffizienz optimieren. "
        "Du bewertest Solarproduktion, Strompreise, Batterie und Verbrauch. "
        "Schlage Verschiebungen vor wenn Solarpeak kommt. "
        "Antworte NUR mit JSON: "
        '{"action": "service.call oder null", "entity_id": "entity oder null", '
        '"reason": "kurze Begründung", "priority": 0-100}'
    ),
    "safety": (
        "Du bist der Safety-Agent im KONTINUUM Haus-Gehirn. "
        "Dein Ziel: Sicherheit der Bewohner. "
        "Du bewertest Risiken, Anomalien und Amygdala-Warnungen. "
        "Du hast VETO-Recht über alle anderen Agents. "
        "Antworte NUR mit JSON: "
        '{"action": "service.call oder null", "entity_id": "entity oder null", '
        '"reason": "kurze Begründung", "priority": 0-100, "veto": false}'
    ),
}


# ══════════════════════════════════════════════════════════════════
# LLM Provider – Pure HTTP, keine SDKs
# ══════════════════════════════════════════════════════════════════

async def _call_ollama(session, url, model, system_prompt, user_msg):
    """Ollama /api/chat endpoint."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "format": "json",
    }
    async with session.post(
        f"{url.rstrip('/')}/api/chat", json=payload, timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"Ollama {resp.status}: {text[:200]}")
        data = await resp.json()
        return data["message"]["content"]


async def _call_openai(session, url, api_key, model, system_prompt, user_msg):
    """OpenAI-kompatible API (auch für Grok, da xAI OpenAI-Format nutzt)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with session.post(
        f"{url.rstrip('/')}/v1/chat/completions", json=payload,
        headers=headers, timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"OpenAI {resp.status}: {text[:200]}")
        data = await resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_claude(session, url, api_key, model, system_prompt, user_msg):
    """Anthropic Messages API."""
    payload = {
        "model": model,
        "max_tokens": 512,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_msg}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    async with session.post(
        f"{url.rstrip('/')}/v1/messages", json=payload,
        headers=headers, timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"Claude {resp.status}: {text[:200]}")
        data = await resp.json()
        return data["content"][0]["text"]


async def _call_gemini(session, url, api_key, model, system_prompt, user_msg):
    """Google Gemini generateContent API."""
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    endpoint = (
        f"{url.rstrip('/')}/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    async with session.post(
        endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"Gemini {resp.status}: {text[:200]}")
        data = await resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


# ══════════════════════════════════════════════════════════════════
# Agent-Klasse
# ══════════════════════════════════════════════════════════════════

class CortexAgent:
    """Ein einzelner LLM-Agent mit Rolle und Provider."""

    def __init__(self, name: str, provider: str, model: str,
                 url: str, api_key: str, system_prompt: str):
        self.name = name
        self.provider = provider
        self.model = model
        self.url = url
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.total_calls = 0
        self.total_errors = 0
        self.last_response = None
        self.last_call_time = 0

    async def think(self, context: dict, session: aiohttp.ClientSession) -> dict:
        """
        Ruft das LLM mit dem KONTINUUM-Kontext auf.
        Returns: Parsed JSON-Response oder Error-Dict.
        """
        user_msg = (
            f"Aktueller Zustand des Hauses:\n"
            f"- Modus: {context.get('mode', '?')}\n"
            f"- Raum: {context.get('room', '?')}\n"
            f"- Vorhersage: {context.get('prediction', '?')} "
            f"(Confidence: {context.get('confidence', 0):.0%})\n"
            f"- Energie: {context.get('energy', '?')}\n"
            f"- Risiko: {context.get('risk', 0):.2f}\n"
            f"- Personen: {context.get('persons_home', '?')}\n"
            f"- Events: {context.get('events', 0)}\n"
            f"- Accuracy: {context.get('accuracy', '?')}\n"
            f"- Letztes Event: {context.get('last_event', '?')}\n"
            f"- Aktive Habits: {context.get('habits', 0)}\n"
            f"- Dopamin: {context.get('dopamine', 0):.3f}\n"
            f"\nWas schlägst du vor?"
        )

        self.last_call_time = time.time()
        self.total_calls += 1

        try:
            if self.provider == "ollama":
                raw = await _call_ollama(
                    session, self.url, self.model,
                    self.system_prompt, user_msg)
            elif self.provider in ("openai", "grok"):
                raw = await _call_openai(
                    session, self.url, self.api_key, self.model,
                    self.system_prompt, user_msg)
            elif self.provider == "claude":
                raw = await _call_claude(
                    session, self.url, self.api_key, self.model,
                    self.system_prompt, user_msg)
            elif self.provider == "gemini":
                raw = await _call_gemini(
                    session, self.url, self.api_key, self.model,
                    self.system_prompt, user_msg)
            else:
                raise RuntimeError(f"Unbekannter Provider: {self.provider}")

            # Parse JSON response
            result = json.loads(raw) if isinstance(raw, str) else raw
            result["agent"] = self.name
            self.last_response = result
            return result

        except json.JSONDecodeError:
            self.total_errors += 1
            _LOGGER.warning("Cortex %s: Kein valides JSON: %s", self.name, raw[:200])
            return {"agent": self.name, "action": None,
                    "reason": f"JSON-Parse-Fehler: {raw[:100]}", "priority": 0}
        except Exception as e:
            self.total_errors += 1
            _LOGGER.error("Cortex %s Fehler: %s", self.name, e)
            return {"agent": self.name, "action": None,
                    "reason": str(e)[:100], "priority": 0}

    @property
    def stats(self) -> dict:
        return {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "total_calls": self.total_calls,
            "total_errors": self.total_errors,
            "error_rate": f"{self.total_errors / max(1, self.total_calls):.0%}",
        }


# ══════════════════════════════════════════════════════════════════
# Cortex – Orchestrator
# ══════════════════════════════════════════════════════════════════

class Cortex:
    """
    Multi-Agent Orchestrator.

    Verwaltet bis zu 3 LLM-Agents, lässt sie parallel denken,
    und gibt eine gewichtete Konsens-Entscheidung zurück.
    """

    # Cooldown: Mindestens 30s zwischen Cortex-Aufrufen
    MIN_INTERVAL = 30

    def __init__(self):
        self.agents: list[CortexAgent] = []
        self.enabled = False
        self.last_run = 0
        self.total_consultations = 0
        self.last_consensus = None
        self._session = None

    def configure(self, agent_configs: list):
        """
        Konfiguriert Agents aus Config-Daten.
        agent_configs: [{"name": "comfort", "provider": "ollama", ...}, ...]
        """
        self.agents.clear()
        for cfg in agent_configs:
            if not cfg.get("provider"):
                continue
            provider_info = PROVIDERS.get(cfg["provider"], {})
            agent = CortexAgent(
                name=cfg.get("name", "agent"),
                provider=cfg["provider"],
                model=cfg.get("model", provider_info.get("default_model", "")),
                url=cfg.get("url", provider_info.get("default_url", "")),
                api_key=cfg.get("api_key", ""),
                system_prompt=cfg.get("system_prompt",
                                      DEFAULT_PROMPTS.get(cfg.get("name", ""), "")),
            )
            self.agents.append(agent)

        self.enabled = len(self.agents) > 0
        _LOGGER.info("Cortex konfiguriert: %d Agents (%s)",
                     len(self.agents),
                     ", ".join(a.name for a in self.agents))

    async def consult(self, brain: dict) -> dict:
        """
        Befragt alle Agents parallel und gibt Konsens zurück.

        Returns: {
            "consensus_action": str or None,
            "consensus_entity": str or None,
            "consensus_reason": str,
            "proposals": [agent responses],
            "vetoed": bool,
        }
        """
        now = time.time()
        if now - self.last_run < self.MIN_INTERVAL:
            return None

        if not self.agents:
            return None

        self.last_run = now
        self.total_consultations += 1

        # Kontext aus Brain sammeln
        context = self._build_context(brain)

        # Alle Agents parallel befragen
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()

        tasks = [agent.think(context, self._session) for agent in self.agents]
        proposals = await asyncio.gather(*tasks)

        # Konsens bilden
        consensus = self._resolve_consensus(proposals)
        self.last_consensus = consensus

        _LOGGER.info(
            "Cortex Konsens: action=%s, reason=%s, vetoed=%s",
            consensus.get("consensus_action"),
            consensus.get("consensus_reason", "")[:80],
            consensus.get("vetoed", False),
        )

        return consensus

    def _build_context(self, brain: dict) -> dict:
        """Baut den Kontext-Dict aus dem Brain für die Agents."""
        hippocampus = brain["hippocampus"]
        thalamus = brain["thalamus"]
        insula = brain["insula"]
        spatial = brain["spatial"]
        hypothalamus = brain["hypothalamus"]
        amygdala = brain["amygdala"]
        basal_ganglia = brain["basal_ganglia"]
        prefrontal = brain["prefrontal"]

        return {
            "mode": insula.current_mode,
            "room": spatial.get_current_location(),
            "prediction": "?",  # Wird vom Caller gesetzt wenn verfügbar
            "confidence": 0,
            "energy": hypothalamus.get_energy_summary().get("battery", "?"),
            "risk": amygdala.stats.get("last_risk", 0),
            "persons_home": "?",
            "events": hippocampus.total_events,
            "accuracy": f"{hippocampus.accuracy:.1%}",
            "last_event": "?",
            "habits": basal_ganglia.total_habits,
            "dopamine": basal_ganglia.dopamine_signal,
        }

    def _resolve_consensus(self, proposals: list) -> dict:
        """
        Einfacher Konsens-Algorithmus:
        1. Safety-Veto hat Vorrang
        2. Höchste Priorität gewinnt
        3. Bei Gleichstand: Mehrheitsentscheidung
        """
        result = {
            "consensus_action": None,
            "consensus_entity": None,
            "consensus_reason": "Kein Vorschlag",
            "proposals": proposals,
            "vetoed": False,
        }

        # 1. Safety-Veto prüfen
        for p in proposals:
            if p.get("veto", False):
                result["vetoed"] = True
                result["consensus_reason"] = f"VETO von {p.get('agent', '?')}: {p.get('reason', '')}"
                _LOGGER.warning("Cortex VETO: %s", result["consensus_reason"])
                return result

        # 2. Nach Priorität sortieren (höchste zuerst)
        actionable = [
            p for p in proposals
            if p.get("action") and p.get("priority", 0) > 0
        ]

        if not actionable:
            result["consensus_reason"] = "Alle Agents: keine Aktion nötig"
            return result

        actionable.sort(key=lambda x: x.get("priority", 0), reverse=True)
        winner = actionable[0]

        result["consensus_action"] = winner.get("action")
        result["consensus_entity"] = winner.get("entity_id")
        result["consensus_reason"] = (
            f"{winner.get('agent', '?')}: {winner.get('reason', '')}"
        )

        return result

    async def close(self):
        """Session schließen."""
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "agents": [a.stats for a in self.agents],
            "total_consultations": self.total_consultations,
            "last_consensus": self.last_consensus,
        }

    def to_dict(self) -> dict:
        return {
            "total_consultations": self.total_consultations,
            "agent_stats": [a.stats for a in self.agents],
        }

    def from_dict(self, data: dict):
        self.total_consultations = data.get("total_consultations", 0)
