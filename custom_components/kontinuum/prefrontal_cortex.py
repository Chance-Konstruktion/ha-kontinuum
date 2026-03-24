"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Präfrontaler Kortex                                ║
║  Entscheidungsinstanz: Soll ich handeln?                        ║
║                                                                  ║
║  Biologisches Vorbild:                                           ║
║  Der PFC wägt ab, plant und entscheidet. Er integriert alle    ║
║  Informationen und bestimmt die optimale Handlung.              ║
║  Er lernt auch aus implizitem Feedback: Wenn der User eine     ║
║  KONTINUUM-Aktion innerhalb von 60s rückgängig macht, ist      ║
║  das negatives Feedback.                                         ║
║                                                                  ║
║  v0.18.0 – Betriebsmodi:                                       ║
║  • shadow  = Nur beobachten, nichts ausführen                   ║
║  • confirm = Bestätigung anfordern vor Ausführung               ║
║  • active  = Selbständig schalten (freigeschaltete Semantiken) ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import time

_LOGGER = logging.getLogger(__name__)

# ── Betriebsmodi ─────────────────────────────────────────────
MODE_SHADOW = "shadow"    # Nur beobachten
MODE_CONFIRM = "confirm"  # Bestätigung anfordern
MODE_ACTIVE = "active"    # Selbständig schalten
VALID_MODES = {MODE_SHADOW, MODE_CONFIRM, MODE_ACTIVE}

ACTIONABLE_SEMANTICS = {
    "light", "switch", "fan", "cover", "climate",
    "media", "automation", "vacuum",
}

STATE_TO_SERVICE = {
    "light": {"on": "turn_on", "off": "turn_off"},
    "switch": {"on": "turn_on", "off": "turn_off"},
    "fan": {"on": "turn_on", "off": "turn_off"},
    "media": {"playing": "media_play", "paused": "media_pause", "off": "turn_off"},
    "cover": {"open": "open_cover", "closed": "close_cover"},
    "climate": {"heating": "set_hvac_mode", "cooling": "set_hvac_mode", "off": "turn_off"},
    "automation": {"on": "turn_on"},
    "vacuum": {"on": "start", "off": "return_to_base"},
}


class Decision:
    """Eine Entscheidung des PFC."""
    OBSERVE = "OBSERVE"
    PREPARE = "PREPARE"
    SUGGEST = "SUGGEST"
    CONFIRM = "CONFIRM"   # v0.18.0: Bestätigung anfordern
    EXECUTE = "EXECUTE"
    
    def __init__(self):
        self.token = ""
        self.token_id = 0
        self.entity_id = ""
        self.confidence = 0.0
        self.utility = 0.0
        self.risk = 0.0
        self.n_obs = 0
        self.stage = self.OBSERVE
        self.source = ""
        self.reasons = []

    def to_dict(self):
        return {
            "token": self.token,
            "entity_id": self.entity_id,
            "confidence": self.confidence,
            "utility": self.utility,
            "risk": self.risk,
            "n_obs": self.n_obs,
            "stage": self.stage,
            "source": self.source,
            "reasons": self.reasons,
        }


class PrefrontalCortex:
    """Entscheidungsinstanz von KONTINUUM."""

    UTILITY_THRESHOLD_SUGGEST = 0.4
    UTILITY_THRESHOLD_EXECUTE = 0.6
    OVERRIDE_WINDOW = 60
    IMPLICIT_POSITIVE_DELAY = 300
    # Minimum Beobachtungen bevor ein Pattern handeln darf
    MIN_OBS_SUGGEST = 20   # n >= 20 für Vorschläge
    MIN_OBS_EXECUTE = 100  # n >= 100 für autonome Aktionen
    
    def __init__(self, amygdala):
        self.amygdala = amygdala
        self.shadow_mode = True
        # v0.18.0: Betriebsmodus (shadow / confirm / active)
        self.operation_mode = MODE_SHADOW
        self.total_decisions = 0
        self.total_executions = 0
        self.total_confirms = 0
        self.overrides_detected = 0
        self.own_actions = {}
        self.utility_weights = {}
        self._feedback_log = []
        # v0.14.3: FAL – freigeschaltete Semantiken für autonome Ausführung
        self.activated_semantics = set()  # z.B. {"light", "switch"}
        # v0.18.0: Warteschlange für Bestätigungs-Aktionen
        self._pending_confirms = {}  # decision_id → Decision

    def evaluate(self, predictions: list, thalamus,
                 basal_ganglia=None, bucket: int = 0) -> Decision:
        """
        Bewertet Predictions und trifft eine Entscheidung.

        Predictions: [(token_id, prob, conf, source, n_obs), ...]

        Doppeltes Gating:
        1. n_obs gatet die Entscheidungsebene (Stichprobengröße)
        2. activated_semantics gatet welche Typen EXECUTE dürfen
        3. Q-Value aus BasalGanglia fließt in Utility ein
        """
        best_decision = None
        best_utility = -1

        for prediction in predictions:
            token_id, prob, conf, source = prediction[:4]
            n_obs = prediction[4] if len(prediction) > 4 else 0

            token = thalamus.decode_token(token_id)
            parts = token.split(".")
            if len(parts) != 3:
                continue

            room, semantic, state = parts
            if semantic not in ACTIONABLE_SEMANTICS:
                continue

            # Amygdala fragen
            assessment = self.amygdala.assess(
                token, semantic, room, state, conf)

            if assessment["decision"] == "VETO":
                continue

            risk = assessment["risk"]
            weight = self.utility_weights.get(semantic, 1.0)

            # Q-Value Boost aus Basalganglien (±0.2 Einfluss)
            q_boost = 0.0
            if basal_ganglia:
                q_boost = basal_ganglia.get_action_priority(token_id, bucket) * 0.2

            utility = conf * weight - risk * 0.5 + q_boost

            if utility > best_utility:
                best_utility = utility
                d = Decision()
                d.token = token
                d.token_id = token_id
                d.confidence = conf
                d.utility = utility
                d.risk = risk
                d.source = source
                d.n_obs = n_obs
                d.reasons = assessment["reasons"]

                # Entity-ID per Reverse-Lookup auflösen
                candidates = thalamus.resolve_entities(token)
                d.entity_id = candidates[0] if candidates else ""

                # Stage bestimmen – v0.18.0 Betriebsmodus-Gating:
                # 1. Zu wenig Beobachtungen → OBSERVE (immer)
                # 2. Shadow-Modus → OBSERVE (immer)
                # 3. Confirm-Modus → CONFIRM statt EXECUTE
                # 4. Active-Modus → EXECUTE wenn freigeschaltet
                if n_obs < self.MIN_OBS_SUGGEST:
                    d.stage = Decision.OBSERVE
                    d.reasons = d.reasons + [f"n={n_obs} < {self.MIN_OBS_SUGGEST} (zu wenig Daten)"]
                elif self.operation_mode == MODE_SHADOW:
                    d.stage = Decision.OBSERVE
                elif (semantic in self.activated_semantics
                      and utility >= self.UTILITY_THRESHOLD_EXECUTE
                      and n_obs >= self.MIN_OBS_EXECUTE):
                    if self.operation_mode == MODE_CONFIRM:
                        d.stage = Decision.CONFIRM
                    else:
                        d.stage = Decision.EXECUTE
                elif utility >= self.UTILITY_THRESHOLD_SUGGEST:
                    d.stage = Decision.SUGGEST
                else:
                    d.stage = Decision.OBSERVE

                best_decision = d

        if best_decision:
            self.total_decisions += 1
            if best_decision.stage == Decision.EXECUTE:
                self.total_executions += 1
            elif best_decision.stage == Decision.CONFIRM:
                self.total_confirms += 1

        return best_decision
    
    def get_service_call(self, decision: Decision) -> dict:
        """Erzeugt einen HA Service-Call aus einer Entscheidung.

        v0.18.0: Liefert auch `data`-Parameter für climate/media.
        """
        parts = decision.token.split(".")
        if len(parts) != 3:
            return None
        room, semantic, state = parts

        services = STATE_TO_SERVICE.get(semantic, {})
        service = services.get(state)
        if not service:
            return None

        data = {"entity_id": decision.entity_id}

        # Climate: hvac_mode mitliefern wenn nicht "off"
        if semantic == "climate" and state != "off":
            data["hvac_mode"] = state

        return {
            "domain": semantic,
            "service": service,
            "entity_id": decision.entity_id,
            "data": data,
        }
    
    def is_own_action(self, entity_id: str) -> bool:
        """Prüft ob eine Entity kürzlich von KONTINUUM gesteuert wurde."""
        action = self.own_actions.get(entity_id)
        if not action:
            return False
        return (time.time() - action["time"]) < 10
    
    def mark_own_action(self, entity_id: str, token: str = "",
                        semantic: str = ""):
        """Markiert eine Entity als von KONTINUUM gesteuert."""
        self.own_actions[entity_id] = {
            "time": time.time(),
            "token": token,
            "semantic": semantic,
        }
    
    def check_override(self, entity_id: str, new_state: str,
                       amygdala=None) -> bool:
        """
        Prüft ob der User eine KONTINUUM-Aktion überschrieben hat.
        Returns True wenn Override erkannt.
        """
        action = self.own_actions.get(entity_id)
        if not action:
            return False
        
        elapsed = time.time() - action["time"]
        if elapsed > self.OVERRIDE_WINDOW:
            return False
        
        if elapsed < 2:
            return False
        
        self.overrides_detected += 1
        token = action.get("token", "")
        
        _LOGGER.info("Override erkannt: %s (nach %.0fs) – negatives Feedback", entity_id, elapsed)
        
        if amygdala and token:
            amygdala.learn_from_feedback(token, "negative")
        
        self._feedback_log.append({
            "time": time.time(),
            "entity_id": entity_id,
            "token": token,
            "feedback": "negative",
            "delay": elapsed,
        })
        if len(self._feedback_log) > 100:
            self._feedback_log = self._feedback_log[-100:]
        
        semantic = action.get("semantic", "")
        if semantic:
            current = self.utility_weights.get(semantic, 1.0)
            self.utility_weights[semantic] = max(0.1, current - 0.05)
        
        del self.own_actions[entity_id]
        return True
    
    def check_implicit_positives(self, amygdala):
        """
        Prüft ob KONTINUUM-Aktionen stillschweigend akzeptiert wurden.
        Returns: Liste der akzeptierten entity_ids (für Basalganglien).
        """
        now = time.time()
        to_remove = []

        for entity_id, action in list(self.own_actions.items()):
            elapsed = now - action["time"]

            if elapsed > self.IMPLICIT_POSITIVE_DELAY:
                token = action.get("token", "")
                if token and amygdala:
                    amygdala.learn_from_feedback(token, "positive")

                semantic = action.get("semantic", "")
                if semantic:
                    current = self.utility_weights.get(semantic, 1.0)
                    self.utility_weights[semantic] = min(2.0, current + 0.01)

                to_remove.append(entity_id)

        for eid in to_remove:
            del self.own_actions[eid]

        return to_remove if to_remove else None
    
    def learn_from_feedback(self, semantic: str, positive: bool):
        """Direkte Feedback-Verarbeitung."""
        if positive:
            current = self.utility_weights.get(semantic, 1.0)
            self.utility_weights[semantic] = min(2.0, current + 0.02)
        else:
            current = self.utility_weights.get(semantic, 1.0)
            self.utility_weights[semantic] = max(0.1, current - 0.05)

    # ── v0.18.0: Betriebsmodus-Steuerung ─────────────────────

    def set_operation_mode(self, mode: str):
        """Setzt den Betriebsmodus (shadow / confirm / active)."""
        if mode not in VALID_MODES:
            _LOGGER.warning("Ungültiger Modus: '%s'. Erlaubt: %s", mode, VALID_MODES)
            return False
        old = self.operation_mode
        self.operation_mode = mode
        # shadow_mode Kompatibilität
        self.shadow_mode = (mode == MODE_SHADOW)
        _LOGGER.info("Betriebsmodus: %s → %s", old, mode)
        return True

    def queue_confirm(self, decision: Decision) -> str:
        """Speichert eine Entscheidung zur Bestätigung. Returns: confirm_id."""
        confirm_id = f"c_{int(time.time())}_{decision.token_id}"
        self._pending_confirms[confirm_id] = {
            "decision": decision,
            "timestamp": time.time(),
        }
        self.total_confirms += 1
        # Alte Confirms aufräumen (> 10 min)
        cutoff = time.time() - 600
        self._pending_confirms = {
            k: v for k, v in self._pending_confirms.items()
            if v["timestamp"] > cutoff
        }
        return confirm_id

    def get_pending_confirm(self, confirm_id: str):
        """Gibt eine wartende Bestätigungs-Entscheidung zurück."""
        entry = self._pending_confirms.pop(confirm_id, None)
        if entry:
            return entry["decision"]
        return None

    def get_all_pending_confirms(self) -> list:
        """Gibt alle wartenden Bestätigungen zurück."""
        now = time.time()
        return [
            {"id": k, "token": v["decision"].token,
             "entity_id": v["decision"].entity_id,
             "confidence": v["decision"].confidence,
             "age_s": int(now - v["timestamp"])}
            for k, v in self._pending_confirms.items()
        ]

    def to_dict(self) -> dict:
        return {
            "shadow_mode": self.shadow_mode,
            "operation_mode": self.operation_mode,
            "total_decisions": self.total_decisions,
            "total_executions": self.total_executions,
            "total_confirms": self.total_confirms,
            "overrides_detected": self.overrides_detected,
            "utility_weights": self.utility_weights,
            "activated_semantics": list(self.activated_semantics),
            "feedback_log": self._feedback_log[-20:],
        }

    def from_dict(self, data: dict):
        self.operation_mode = data.get("operation_mode", MODE_SHADOW)
        self.shadow_mode = data.get("shadow_mode", self.operation_mode == MODE_SHADOW)
        self.total_decisions = data.get("total_decisions", 0)
        self.total_executions = data.get("total_executions", 0)
        self.total_confirms = data.get("total_confirms", 0)
        self.overrides_detected = data.get("overrides_detected", 0)
        self.utility_weights = data.get("utility_weights", {})
        self.activated_semantics = set(data.get("activated_semantics", []))
        self._feedback_log = data.get("feedback_log", [])

    @property
    def stats(self) -> dict:
        return {
            "shadow_mode": self.shadow_mode,
            "operation_mode": self.operation_mode,
            "total_decisions": self.total_decisions,
            "total_executions": self.total_executions,
            "total_confirms": self.total_confirms,
            "overrides_detected": self.overrides_detected,
            "activated_semantics": list(self.activated_semantics),
            "utility_weights": self.utility_weights,
            "override_rate": f"{self.overrides_detected / max(1, self.total_decisions):.1%}",
            "pending_confirms": len(self._pending_confirms),
        }
