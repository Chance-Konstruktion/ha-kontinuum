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
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import time

_LOGGER = logging.getLogger(__name__)

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
    EXECUTE = "EXECUTE"
    
    def __init__(self):
        self.token = ""
        self.token_id = 0
        self.entity_id = ""
        self.confidence = 0.0
        self.utility = 0.0
        self.risk = 0.0
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
    
    def __init__(self, amygdala):
        self.amygdala = amygdala
        self.shadow_mode = True
        self.total_decisions = 0
        self.overrides_detected = 0
        self.own_actions = {}
        self.utility_weights = {}
        self._feedback_log = []
    
    def evaluate(self, predictions: list, thalamus) -> Decision:
        """Bewertet Predictions und trifft eine Entscheidung."""
        best_decision = None
        best_utility = -1
        
        for token_id, prob, conf, source in predictions:
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
            utility = conf * weight - risk * 0.5
            
            if utility > best_utility:
                best_utility = utility
                d = Decision()
                d.token = token
                d.token_id = token_id
                d.confidence = conf
                d.utility = utility
                d.risk = risk
                d.source = source
                d.reasons = assessment["reasons"]
                
                if self.shadow_mode:
                    d.stage = Decision.OBSERVE
                elif utility >= self.UTILITY_THRESHOLD_EXECUTE:
                    d.stage = Decision.EXECUTE
                elif utility >= self.UTILITY_THRESHOLD_SUGGEST:
                    d.stage = Decision.SUGGEST
                else:
                    d.stage = Decision.OBSERVE
                
                best_decision = d
        
        if best_decision:
            self.total_decisions += 1
        
        return best_decision
    
    def get_service_call(self, decision: Decision) -> dict:
        """Erzeugt einen HA Service-Call aus einer Entscheidung."""
        parts = decision.token.split(".")
        if len(parts) != 3:
            return None
        room, semantic, state = parts
        
        services = STATE_TO_SERVICE.get(semantic, {})
        service = services.get(state)
        if not service:
            return None
        
        return {
            "domain": semantic,
            "service": service,
            "entity_id": decision.entity_id,
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
    
    def to_dict(self) -> dict:
        return {
            "shadow_mode": self.shadow_mode,
            "total_decisions": self.total_decisions,
            "overrides_detected": self.overrides_detected,
            "utility_weights": self.utility_weights,
            "feedback_log": self._feedback_log[-20:],
        }
    
    def from_dict(self, data: dict):
        self.shadow_mode = data.get("shadow_mode", True)
        self.total_decisions = data.get("total_decisions", 0)
        self.overrides_detected = data.get("overrides_detected", 0)
        self.utility_weights = data.get("utility_weights", {})
        self._feedback_log = data.get("feedback_log", [])
    
    @property
    def stats(self) -> dict:
        return {
            "shadow_mode": self.shadow_mode,
            "total_decisions": self.total_decisions,
            "overrides_detected": self.overrides_detected,
            "utility_weights": self.utility_weights,
            "override_rate": f"{self.overrides_detected / max(1, self.total_decisions):.1%}",
        }
