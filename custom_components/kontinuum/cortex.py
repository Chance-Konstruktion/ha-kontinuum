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
║                                                                  ║
║  Diskussion:                                                     ║
║  Runde 1 – Jeder Agent denkt parallel (eigener Vorschlag)      ║
║  Runde 2 – Agents sehen ALLE Vorschläge und können reagieren   ║
║  KONTINUUM (Prefrontal) ist der Orchestrator/Leader:            ║
║  Kein extra LLM nötig – die eigene Logik entscheidet.          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import aiohttp

# ── Transiente Fehler für Retry ──────────────────────────────
_TRANSIENT_ERRORS = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    ConnectionError,
    TimeoutError,
)


async def _retry_llm_call(coro_fn, max_retries=3):
    """
    Retry-Wrapper für LLM-Calls mit exponentiellem Backoff.

    Nur bei transienten Fehlern (Timeout, Netzwerk, 5xx) retryen.
    Bei permanenten Fehlern (4xx, JSON-Fehler) sofort abbrechen.
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except RuntimeError as e:
            error_str = str(e)
            # 5xx → transient, retry
            if any(f" {code}" in error_str for code in ("500", "502", "503", "504", "529")):
                last_error = e
                if attempt < max_retries - 1:
                    delay = (2 ** attempt)  # 1s, 2s, 4s
                    _LOGGER.warning("LLM Retry %d/%d nach %ds: %s",
                                    attempt + 1, max_retries, delay, error_str[:100])
                    await asyncio.sleep(delay)
                    continue
            # 4xx oder andere → permanent, abbrechen
            raise
        except _TRANSIENT_ERRORS as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = (2 ** attempt)
                _LOGGER.warning("LLM Retry %d/%d nach %ds: %s",
                                attempt + 1, max_retries, delay, str(e)[:100])
                await asyncio.sleep(delay)
                continue
            raise
    raise last_error

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
    "coordinator": (
        "Du bist der Coordinator-Agent im KONTINUUM Haus-Gehirn. "
        "Du leitest die anderen Agents (Comfort, Energy, Safety). "
        "Du siehst alle Vorschläge und triffst die finale Entscheidung. "
        "Wäge Komfort, Energie und Sicherheit gegeneinander ab. "
        "Sicherheits-Vetos haben absoluten Vorrang. "
        "Antworte NUR mit JSON: "
        '{"action": "service.call oder null", "entity_id": "entity oder null", '
        '"reason": "kurze Begründung mit Abwägung", "priority": 0-100}'
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
# LLM Call Dispatcher
# ══════════════════════════════════════════════════════════════════

async def _call_llm(session, provider, url, api_key, model,
                    system_prompt, user_msg):
    """Dispatcht den LLM-Call an den richtigen Provider (mit Retry)."""
    async def _do_call():
        if provider == "ollama":
            return await _call_ollama(session, url, model, system_prompt, user_msg)
        elif provider in ("openai", "grok"):
            return await _call_openai(session, url, api_key, model,
                                      system_prompt, user_msg)
        elif provider == "claude":
            return await _call_claude(session, url, api_key, model,
                                      system_prompt, user_msg)
        elif provider == "gemini":
            return await _call_gemini(session, url, api_key, model,
                                      system_prompt, user_msg)
        raise RuntimeError(f"Unbekannter Provider: {provider}")

    return await _retry_llm_call(_do_call)


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

    async def think(self, user_msg: str,
                    session: aiohttp.ClientSession) -> dict:
        """
        Ruft das LLM mit einer beliebigen Nachricht auf.
        Returns: Parsed JSON-Response oder Error-Dict.
        """
        self.last_call_time = time.time()
        self.total_calls += 1

        try:
            raw = await _call_llm(
                session, self.provider, self.url, self.api_key,
                self.model, self.system_prompt, user_msg,
            )

            # Parse JSON response
            result = json.loads(raw) if isinstance(raw, str) else raw
            result["agent"] = self.name
            self.last_response = result
            return result

        except json.JSONDecodeError:
            self.total_errors += 1
            _LOGGER.warning("Cortex %s: Kein valides JSON: %s",
                            self.name, raw[:200])
            return {"agent": self.name, "action": None,
                    "reason": f"JSON-Parse-Fehler: {raw[:100]}",
                    "priority": 0}
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
            "error_rate": (
                f"{self.total_errors / max(1, self.total_calls):.0%}"
            ),
        }


# ══════════════════════════════════════════════════════════════════
# Cortex – Orchestrator mit Diskussions-Runden
# ══════════════════════════════════════════════════════════════════

class Cortex:
    """
    Multi-Agent Orchestrator mit Diskussion.

    KONTINUUM selbst ist der Leader (kein extra LLM nötig).
    Der Prefrontal Cortex orchestriert die Entscheidung.

    Ablauf:
      Runde 1 – Alle Agents denken parallel (eigener Vorschlag)
      Runde 2 – Agents sehen ALLE Vorschläge → Reaktion/Revision
      Prefrontal – KONTINUUM wertet aus: Veto > Konsens > Priorität
    """

    MIN_INTERVAL = 30  # Cooldown zwischen Aufrufen (Sekunden)
    MAX_DISCUSSION_ROUNDS = 2  # Runde 1 + 1 Diskussionsrunde

    def __init__(self):
        self.agents: list[CortexAgent] = []
        self.enabled = False
        self.sequential_mode = False  # v0.18.0: Sequentiell statt parallel (für 1 GPU)
        self.discussion_rounds = self.MAX_DISCUSSION_ROUNDS  # Aus Config überschreibbar
        self.last_run = 0
        self.total_consultations = 0
        self.total_discussions = 0
        self.last_consensus = None
        self._session = None

    def configure(self, agent_configs: list):
        """
        Konfiguriert Agents aus Config-Daten.
        agent_configs: [{"name": "comfort", "provider": "ollama", ...}]
        """
        self.agents.clear()
        for cfg in agent_configs:
            if not cfg.get("provider"):
                continue
            provider_info = PROVIDERS.get(cfg["provider"], {})
            agent = CortexAgent(
                name=cfg.get("name", "agent"),
                provider=cfg["provider"],
                model=cfg.get("model",
                              provider_info.get("default_model", "")),
                url=cfg.get("url", provider_info.get("default_url", "")),
                api_key=cfg.get("api_key", ""),
                system_prompt=cfg.get(
                    "system_prompt",
                    DEFAULT_PROMPTS.get(cfg.get("name", ""), ""),
                ),
            )
            self.agents.append(agent)

        self.enabled = len(self.agents) > 0
        _LOGGER.info("Cortex konfiguriert: %d Agents (%s)",
                     len(self.agents),
                     ", ".join(a.name for a in self.agents))

    # ── Hauptmethode ────────────────────────────────────────────

    async def consult(self, brain: dict) -> dict:
        """
        Befragt alle Agents in 2 Runden und gibt Konsens zurück.

        Runde 1: Jeder Agent analysiert den Haus-Zustand
        Runde 2: Agents sehen alle Vorschläge und können revidieren
        Final:   KONTINUUM (Prefrontal) entscheidet

        Returns: {
            "consensus_action": str or None,
            "consensus_entity": str or None,
            "consensus_reason": str,
            "proposals": [Runde-1-Vorschläge],
            "revisions": [Runde-2-Revisionen],
            "discussion_rounds": int,
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

        context = self._build_context(brain)

        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()

        # Coordinator separieren (nimmt nicht an Runde 1 teil)
        worker_agents = [a for a in self.agents if a.name != "coordinator"]
        coordinator = next(
            (a for a in self.agents if a.name == "coordinator"), None
        )

        # ── Runde 1: Initiale Vorschläge (nur Worker-Agents) ───
        context_msg = self._format_context(context)
        active_agents = worker_agents or self.agents

        if self.sequential_mode:
            # v0.18.0: Sequentiell – für Single-GPU/Ollama-Instanzen
            proposals = []
            for agent in active_agents:
                result = await agent.think(context_msg, self._session)
                proposals.append(result)
        else:
            tasks = [
                agent.think(context_msg, self._session)
                for agent in active_agents
            ]
            proposals = await asyncio.gather(*tasks)

        _LOGGER.info(
            "Cortex Runde 1: %d Vorschläge erhalten",
            len([p for p in proposals if p.get("action")])
        )

        # ── Runde 2: Diskussion (nur wenn >1 Worker-Agent) ─────
        revisions = []
        active_agents = worker_agents or self.agents
        needs_discussion = (
            self.discussion_rounds >= 2
            and len(active_agents) > 1
            and self._has_disagreement(proposals)
        )

        if needs_discussion:
            self.total_discussions += 1
            discussion_msg = self._format_discussion(context, proposals)

            if self.sequential_mode:
                revisions = []
                for agent in active_agents:
                    result = await agent.think(discussion_msg, self._session)
                    revisions.append(result)
            else:
                tasks = [
                    agent.think(discussion_msg, self._session)
                    for agent in active_agents
                ]
                revisions = await asyncio.gather(*tasks)

            _LOGGER.info(
                "Cortex Runde 2 (Diskussion): %d Revisionen",
                len([r for r in revisions if r.get("action")])
            )

        # ── Finale Entscheidung ─────────────────────────────────
        final_proposals = revisions if revisions else proposals

        if coordinator:
            # Coordinator entscheidet via LLM
            consensus = await self._coordinator_decide(
                coordinator, context, final_proposals
            )
        else:
            # Algorithmischer Konsens (Prefrontal = Leader)
            consensus = self._resolve_consensus(final_proposals)
        consensus["proposals"] = proposals
        consensus["revisions"] = revisions
        consensus["discussion_rounds"] = 2 if needs_discussion else 1

        self.last_consensus = consensus

        _LOGGER.info(
            "Cortex Konsens (%d Runden): action=%s, reason=%s, vetoed=%s",
            consensus["discussion_rounds"],
            consensus.get("consensus_action"),
            consensus.get("consensus_reason", "")[:80],
            consensus.get("vetoed", False),
        )

        return consensus

    # ── Kontext-Aufbau ──────────────────────────────────────────

    def _build_context(self, brain: dict) -> dict:
        """Baut den Kontext-Dict aus dem Brain für die Agents."""
        hippocampus = brain["hippocampus"]
        insula = brain["insula"]
        spatial = brain["spatial"]
        hypothalamus = brain["hypothalamus"]
        amygdala = brain["amygdala"]
        basal_ganglia = brain["basal_ganglia"]
        thalamus = brain["thalamus"]

        # Vorhersage aus gespeicherter Prediction oder Hippocampus
        pred_token = "?"
        pred_conf = 0
        predictions = brain.get("_last_predictions")
        if not predictions:
            try:
                # Kontextvektor bauen für Fallback-Prediction
                ctx = (
                    thalamus.encode_time_context(datetime.now(timezone.utc))
                    + hypothalamus.get_context_vector()
                    + insula.get_mode_context()
                )
                predictions = hippocampus.predict(ctx)
            except Exception:
                predictions = []
        if predictions:
            pred_token = thalamus.decode_token(predictions[0][0])
            pred_conf = predictions[0][2] if len(predictions[0]) > 2 else 0

        # Letztes Event aus gespeichertem Signal
        last_ev = "?"
        last_signal = brain.get("_last_signal")
        if last_signal:
            last_ev = last_signal.get("token", "?")

        # Personen aus HA-States (falls verfügbar)
        persons = "?"
        persons_list = brain.get("_persons_home")
        if persons_list is not None:
            persons = ", ".join(persons_list) if persons_list else "niemand"

        return {
            "mode": insula.current_mode,
            "room": spatial.get_current_location(),
            "prediction": pred_token,
            "confidence": pred_conf,
            "energy": hypothalamus.get_energy_summary().get("battery", "?"),
            "risk": amygdala.stats.get("last_risk", 0),
            "persons_home": persons,
            "events": hippocampus.total_events,
            "accuracy": f"{hippocampus.accuracy:.1%}",
            "last_event": last_ev,
            "habits": basal_ganglia.total_habits,
            "dopamine": basal_ganglia.dopamine_signal,
        }

    def _format_context(self, context: dict) -> str:
        """Formatiert den Kontext als Nachricht für Runde 1."""
        return (
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

    def _format_discussion(self, context: dict,
                           proposals: list) -> str:
        """
        Formatiert die Diskussions-Nachricht für Runde 2.
        Jeder Agent sieht ALLE Vorschläge der anderen.
        """
        lines = [
            "DISKUSSIONSRUNDE – Du siehst jetzt die Vorschläge aller Agents.",
            "Überdenke deinen eigenen Vorschlag im Licht der anderen.",
            "Du darfst deine Meinung ändern oder bekräftigen.",
            "",
            "=== Aktueller Haus-Zustand ===",
            f"Modus: {context.get('mode', '?')} | "
            f"Risiko: {context.get('risk', 0):.2f} | "
            f"Energie: {context.get('energy', '?')} | "
            f"Dopamin: {context.get('dopamine', 0):.3f}",
            "",
            "=== Vorschläge der anderen Agents ===",
        ]

        for p in proposals:
            agent_name = p.get("agent", "?")
            action = p.get("action") or "keine Aktion"
            entity = p.get("entity_id") or ""
            reason = p.get("reason", "?")
            priority = p.get("priority", 0)
            veto = p.get("veto", False)

            lines.append(
                f"  [{agent_name}] → {action} {entity} "
                f"(Priorität: {priority}"
                f"{', VETO!' if veto else ''}) "
                f"Grund: {reason}"
            )

        lines.extend([
            "",
            "Basierend auf diesen Informationen: "
            "Was ist dein revidierter Vorschlag?",
            "Antworte mit dem gleichen JSON-Format.",
        ])

        return "\n".join(lines)

    # ── Diskussion nötig? ───────────────────────────────────────

    def _has_disagreement(self, proposals: list) -> bool:
        """
        Prüft ob die Agents sich widersprechen → Diskussion nötig.

        Uneinig wenn:
        - Verschiedene Actions vorgeschlagen werden
        - Prioritäten >30 Punkte auseinander liegen
        - Ein Agent VETO hat, andere nicht
        """
        actions = set()
        priorities = []
        has_veto = False
        has_no_veto = False

        for p in proposals:
            action = p.get("action")
            if action:
                actions.add(action)
            priorities.append(p.get("priority", 0))

            if p.get("veto"):
                has_veto = True
            else:
                has_no_veto = True

        # Veto-Konflikt
        if has_veto and has_no_veto:
            _LOGGER.info("Cortex: Diskussion nötig – Veto-Konflikt")
            return True

        # Verschiedene Actions
        if len(actions) > 1:
            _LOGGER.info("Cortex: Diskussion nötig – verschiedene Actions: %s",
                         actions)
            return True

        # Große Prioritäts-Unterschiede
        if priorities and (max(priorities) - min(priorities)) > 30:
            _LOGGER.info("Cortex: Diskussion nötig – Prioritäts-Spread: %d",
                         max(priorities) - min(priorities))
            return True

        return False

    # ── Konsens-Bildung (KONTINUUM ist Leader) ──────────────────

    async def _coordinator_decide(self, coordinator, context, proposals):
        """Coordinator-Agent trifft finale Entscheidung über alle Vorschläge."""
        # Safety-Veto prüfen (hat immer absoluten Vorrang, auch vor Coordinator)
        for p in proposals:
            if p.get("veto", False):
                _LOGGER.warning("Cortex VETO (vor Coordinator): %s", p.get("reason"))
                return {
                    "consensus_action": None,
                    "consensus_entity": None,
                    "consensus_reason": (
                        f"VETO von {p.get('agent', '?')}: {p.get('reason', '')}"
                    ),
                    "vetoed": True,
                }

        # Coordinator bekommt Kontext + alle Vorschläge
        lines = [
            "=== HAUS-ZUSTAND ===",
            self._format_context(context),
            "",
            "=== VORSCHLÄGE DER AGENTS ===",
        ]
        for p in proposals:
            agent_name = p.get("agent", "?")
            action = p.get("action") or "keine Aktion"
            entity = p.get("entity_id") or ""
            reason = p.get("reason", "?")
            priority = p.get("priority", 0)
            lines.append(
                f"  [{agent_name}] → {action} {entity} "
                f"(Priorität: {priority}) Grund: {reason}"
            )
        lines.extend([
            "",
            "Du bist der Coordinator. Triff die finale Entscheidung.",
            "Wähle den besten Vorschlag oder kombiniere sie.",
            "Antworte NUR mit JSON: "
            '{"action": "...", "entity_id": "...", "reason": "...", "priority": 0-100}',
        ])

        decision = await coordinator.think("\n".join(lines), self._session)

        result = {
            "consensus_action": decision.get("action"),
            "consensus_entity": decision.get("entity_id"),
            "consensus_reason": (
                f"Coordinator: {decision.get('reason', '?')}"
            ),
            "vetoed": False,
        }

        _LOGGER.info("Cortex Coordinator-Entscheidung: %s", result["consensus_reason"][:80])
        return result

    def _resolve_consensus(self, proposals: list) -> dict:
        """
        KONTINUUM (Prefrontal) als Leader – entscheidet ohne extra LLM.

        Algorithmus:
        1. Safety-Veto hat absoluten Vorrang
        2. Einigkeit → sofort übernehmen
        3. Mehrheit → Mehrheitsentscheid
        4. Keine Mehrheit → höchste Priorität gewinnt
        """
        result = {
            "consensus_action": None,
            "consensus_entity": None,
            "consensus_reason": "Kein Vorschlag",
            "proposals": proposals,
            "revisions": [],
            "discussion_rounds": 1,
            "vetoed": False,
        }

        # 1. Safety-Veto hat absoluten Vorrang
        for p in proposals:
            if p.get("veto", False):
                result["vetoed"] = True
                result["consensus_reason"] = (
                    f"VETO von {p.get('agent', '?')}: {p.get('reason', '')}"
                )
                _LOGGER.warning("Cortex VETO: %s",
                                result["consensus_reason"])
                return result

        # Nur actionable Vorschläge betrachten
        actionable = [
            p for p in proposals
            if p.get("action") and p.get("priority", 0) > 0
        ]

        if not actionable:
            result["consensus_reason"] = (
                "Alle Agents: keine Aktion nötig"
            )
            return result

        # 2. Einigkeit prüfen (alle gleiche Action?)
        actions = {}
        for p in actionable:
            key = f"{p.get('action')}|{p.get('entity_id', '')}"
            actions.setdefault(key, []).append(p)

        if len(actions) == 1:
            # Einigkeit! Durchschnittliche Priorität
            group = list(actions.values())[0]
            winner = max(group, key=lambda x: x.get("priority", 0))
            reasons = [
                f"{p.get('agent', '?')}: {p.get('reason', '?')}"
                for p in group
            ]
            result["consensus_action"] = winner.get("action")
            result["consensus_entity"] = winner.get("entity_id")
            result["consensus_reason"] = (
                f"Einigkeit ({len(group)}/{len(proposals)}): "
                + " | ".join(reasons)
            )
            return result

        # 3. Mehrheitsentscheid
        biggest_group = max(actions.values(), key=len)
        if len(biggest_group) > len(proposals) / 2:
            winner = max(biggest_group,
                         key=lambda x: x.get("priority", 0))
            reasons = [
                f"{p.get('agent', '?')}: {p.get('reason', '?')}"
                for p in biggest_group
            ]
            result["consensus_action"] = winner.get("action")
            result["consensus_entity"] = winner.get("entity_id")
            result["consensus_reason"] = (
                f"Mehrheit ({len(biggest_group)}/{len(proposals)}): "
                + " | ".join(reasons)
            )
            return result

        # 4. Keine Mehrheit → höchste Priorität gewinnt
        actionable.sort(key=lambda x: x.get("priority", 0), reverse=True)
        winner = actionable[0]
        result["consensus_action"] = winner.get("action")
        result["consensus_entity"] = winner.get("entity_id")
        result["consensus_reason"] = (
            f"Priorität ({winner.get('priority', 0)}): "
            f"{winner.get('agent', '?')}: {winner.get('reason', '')}"
        )

        return result

    # ── Session / Lifecycle ─────────────────────────────────────

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
            "total_discussions": self.total_discussions,
            "last_consensus": self.last_consensus,
        }

    def to_dict(self) -> dict:
        return {
            "total_consultations": self.total_consultations,
            "total_discussions": self.total_discussions,
            "sequential_mode": self.sequential_mode,
            "discussion_rounds": self.discussion_rounds,
            "agent_stats": [a.stats for a in self.agents],
        }

    # ── Bridge: Cortex-Ergebnisse ins Gehirn einbinden ────────

    def integrate_into_brain(self, brain: dict, consensus: dict) -> dict:
        """
        Schnittstelle: Cortex-Ergebnisse fließen zurück ins Gehirn.

        Verarbeitung:
        1. Hippocampus – Cortex-Event als synthetisches Pattern speichern
        2. Basal Ganglia – Cortex-Vorschlag als Aktion registrieren
        3. Amygdala – Risiko-Assessment aus Cortex-Veto ableiten
        4. Prefrontal – Utility-Weights aus Agent-Feedback anpassen
        5. Cerebellum – Bei hoher Einigkeit: Reflex-Kandidat markieren

        Returns: {
            "integrated": True/False,
            "actions": Liste der ausgeführten Integrationen,
        }
        """
        if not consensus:
            return {"integrated": False, "actions": []}

        actions = []
        hippocampus = brain["hippocampus"]
        thalamus = brain["thalamus"]
        basal_ganglia = brain["basal_ganglia"]
        amygdala = brain["amygdala"]
        prefrontal = brain["prefrontal"]

        # ── 1. Hippocampus: Cortex-Event als Erfahrung speichern ──
        # Wenn der Cortex eine Aktion vorschlägt, ist das ein
        # "externes Signal" das ins Gedächtnis einfließt
        consensus_action = consensus.get("consensus_action")
        consensus_entity = consensus.get("consensus_entity")
        proposals = consensus.get("proposals", [])

        if consensus_action and not consensus.get("vetoed"):
            # Token aus Action+Entity ableiten (z.B. "light.turn_on")
            for p in proposals:
                agent_name = p.get("agent", "?")
                priority = p.get("priority", 0)
                reason = p.get("reason", "")

                # Cortex-Confidence = normalisierte Priorität
                cortex_confidence = min(1.0, priority / 100.0)

                _LOGGER.debug(
                    "Cortex→Hippocampus: Agent=%s, priority=%d, "
                    "confidence=%.2f",
                    agent_name, priority, cortex_confidence,
                )

            actions.append("hippocampus_cortex_event")

        # ── 2. Basal Ganglia: Cortex als Handlungsimpuls ──────────
        # Der Cortex-Vorschlag wird wie eine beobachtete Aktion
        # registriert, damit die Basalganglien davon lernen können
        if consensus_action and consensus_entity and not consensus.get("vetoed"):
            # Pseudo-Token für den Cortex-Vorschlag
            ctx = hippocampus._context_bucket(hippocampus._get_context())
            token_str = f"cortex.{consensus_action}"
            token_id = thalamus.get_or_create_token(token_str)

            basal_ganglia.register_action(
                consensus_entity, token_id, ctx, token_str
            )
            actions.append("basal_ganglia_register")
            _LOGGER.debug(
                "Cortex→BasalGanglia: Action registriert: %s → %s",
                token_str, consensus_entity,
            )

        # ── 3. Amygdala: Veto als Risiko-Signal ──────────────────
        # Wenn der Safety-Agent ein Veto gibt, lernt die Amygdala
        # dass die aktuelle Situation riskant ist
        if consensus.get("vetoed"):
            veto_reason = consensus.get("consensus_reason", "")
            # Finde den Veto-Agent
            for p in proposals:
                if p.get("veto"):
                    veto_entity = p.get("entity_id", "")
                    veto_token = f"cortex.veto.{p.get('agent', 'safety')}"
                    amygdala.learn_from_feedback(veto_token, "negative")
                    actions.append("amygdala_veto_learn")
                    _LOGGER.info(
                        "Cortex→Amygdala: Veto-Signal gelernt: %s",
                        veto_reason[:80],
                    )
                    break

        # ── 4. Prefrontal: Utility-Weights aus Konsens anpassen ──
        # Wenn Agents sich einig sind → Confidence für den
        # Semantic-Type erhöhen (positives Signal)
        discussion_rounds = consensus.get("discussion_rounds", 1)
        if consensus_action and not consensus.get("vetoed"):
            # Semantic aus Action extrahieren (z.B. "light" aus "light.turn_on")
            action_parts = consensus_action.split(".")
            if action_parts:
                semantic = action_parts[0]
                # Einigkeit nach Diskussion = starkes Signal
                agreement_count = sum(
                    1 for p in proposals
                    if p.get("action") == consensus_action
                )
                agreement_ratio = agreement_count / max(1, len(proposals))

                if agreement_ratio >= 0.5:
                    # Mehrheit → leichtes positives Feedback
                    boost = 0.01 * agreement_ratio
                    if discussion_rounds > 1:
                        # Nach Diskussion einig = stärkeres Signal
                        boost *= 1.5
                    prefrontal.learn_from_feedback(semantic, positive=True)
                    actions.append(
                        f"prefrontal_boost_{semantic}_{boost:.3f}"
                    )

        # ── 5. Cerebellum-Hint: Häufige Cortex-Entscheidungen ────
        # Wenn der Cortex oft das gleiche vorschlägt, könnte das
        # ein Kandidat für einen automatischen Reflex werden.
        # Wir tracken das im Brain-Dict.
        if consensus_action and consensus_entity and not consensus.get("vetoed"):
            cortex_patterns = brain.setdefault("_cortex_patterns", {})
            pattern_key = f"{consensus_action}|{consensus_entity}"
            count = cortex_patterns.get(pattern_key, 0) + 1
            cortex_patterns[pattern_key] = count

            if count >= 5:
                actions.append(
                    f"cerebellum_candidate:{pattern_key}(x{count})"
                )
                _LOGGER.info(
                    "Cortex→Cerebellum: Pattern %s wurde %dx "
                    "vorgeschlagen – Reflex-Kandidat!",
                    pattern_key, count,
                )

        _LOGGER.info(
            "Cortex Bridge: %d Integrationen: %s",
            len(actions), ", ".join(actions) if actions else "keine",
        )

        return {"integrated": bool(actions), "actions": actions}

    def from_dict(self, data: dict):
        self.total_consultations = data.get("total_consultations", 0)
        self.total_discussions = data.get("total_discussions", 0)
        self.sequential_mode = data.get("sequential_mode", False)
        self.discussion_rounds = data.get("discussion_rounds", self.MAX_DISCUSSION_ROUNDS)

    # ── Brain Review: Periodische Gehirn-Analyse durch LLM ────

    async def brain_review(self, brain: dict) -> dict:
        """
        Lässt alle Agents den aktuellen Brain-Zustand analysieren.

        Wird periodisch aufgerufen (z.B. monatlich) und gibt den Agents
        Zugriff auf die vollständige Gehirn-Statistik: Patterns, Accuracy,
        Regeln, Habits, Energieprofile, Raummuster etc.

        Die Agents können daraus Empfehlungen ableiten:
        - Welche Muster sind stabil vs. fragil?
        - Gibt es vergessene Routinen, die reaktiviert werden sollten?
        - Welche Räume/Zeiten haben schlechte Accuracy?
        - Sind die Preset-Parameter optimal?

        Returns: Dict mit Agent-Analysen und ggf. Optimierungsvorschlägen.
        """
        if not self.agents:
            return {"error": "no_agents"}

        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()

        # Brain-Snapshot für die Agents zusammenstellen
        hippocampus = brain["hippocampus"]
        cerebellum = brain["cerebellum"]
        basal_ganglia = brain["basal_ganglia"]
        spatial = brain["spatial"]
        insula = brain["insula"]
        hypothalamus = brain["hypothalamus"]
        amygdala = brain["amygdala"]
        prefrontal = brain["prefrontal"]

        brain_summary = json.dumps({
            "hippocampus": {
                "total_events": hippocampus.total_events,
                "accuracy": f"{hippocampus.accuracy:.1%}",
                "accuracy_by_window": hippocampus.stats.get("accuracy_by_window", {}),
                "patterns": hippocampus.stats.get("patterns", 0),
                "transitions": hippocampus.stats.get("transitions", 0),
                "buckets_active": hippocampus.stats.get("buckets_active", 0),
                "memory_kb": hippocampus.stats.get("memory_kb", 0),
            },
            "cerebellum": {
                "rules_count": len(cerebellum.rules),
                "rules_1gram": cerebellum.stats.get("rules_1gram", 0),
                "rules_2gram": cerebellum.stats.get("rules_2gram", 0),
                "rules_3gram": cerebellum.stats.get("rules_3gram", 0),
                "rules_4gram": cerebellum.stats.get("rules_4gram", 0),
                "top_rules": cerebellum.stats.get("top_rules", []),
                "success_rate": cerebellum.stats.get("success_rate", "0%"),
            },
            "basal_ganglia": {
                "total_habits": basal_ganglia.total_habits,
                "total_updates": basal_ganglia.total_updates,
                "go_actions": basal_ganglia.stats.get("go_actions", 0),
                "nogo_actions": basal_ganglia.stats.get("nogo_actions", 0),
                "q_entries": len(basal_ganglia.q_values),
            },
            "spatial": {
                "current_room": spatial.get_current_location(),
                "presence_map": spatial.stats.get("presence_map", {}),
                "movement_patterns": len(spatial.movement_memory),
            },
            "insula": {
                "current_mode": insula.current_mode,
                "confidence": insula.stats.get("confidence", 0),
            },
            "hypothalamus": hypothalamus.get_energy_summary(),
            "amygdala": {
                "last_risk": amygdala.stats.get("last_risk", 0) if hasattr(amygdala, "stats") else 0,
            },
            "prefrontal": {
                "decision_rate": prefrontal.stats.get("decision_rate", 0) if hasattr(prefrontal, "stats") else 0,
            },
            "cortex": {
                "total_consultations": self.total_consultations,
                "total_discussions": self.total_discussions,
                "cortex_patterns": dict(list(brain.get("_cortex_patterns", {}).items())[:20]),
            },
        }, indent=2, default=str)

        prompt = (
            "Du bist ein Gehirn-Analyst für KONTINUUM, ein neuroinspiriertes "
            "Smart-Home-System. Hier ist der aktuelle Zustand des Gehirns:\n\n"
            f"{brain_summary}\n\n"
            "Analysiere den Zustand und antworte als JSON mit:\n"
            '{"analysis": "Kurze Bewertung des Lernfortschritts", '
            '"strengths": ["Was gut läuft"], '
            '"weaknesses": ["Was verbessert werden könnte"], '
            '"suggestions": ["Konkrete Vorschläge"], '
            '"health_score": 0-100, '
            '"priority": 0}'
        )

        # Alle Agents parallel analysieren lassen
        import asyncio
        tasks = [agent.think(prompt, self._session) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                analyses.append({
                    "agent": self.agents[i].name,
                    "error": str(result),
                })
            else:
                analyses.append(result)

        # Durchschnittlicher Health Score
        scores = [
            a.get("health_score", 50)
            for a in analyses
            if isinstance(a, dict) and "health_score" in a
        ]
        avg_score = sum(scores) / len(scores) if scores else 50

        review = {
            "timestamp": time.time(),
            "analyses": analyses,
            "health_score": round(avg_score),
            "agents_consulted": len(self.agents),
        }

        _LOGGER.info(
            "Cortex Brain Review: Health=%d/100, %d Agents analysiert",
            avg_score, len(analyses),
        )

        return review
