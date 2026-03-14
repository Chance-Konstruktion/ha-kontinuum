"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Cerebellum                                         ║
║  Routinen-Erkennung: Feste Reflexe aus dem Gedächtnis          ║
║                                                                  ║
║  Biologisches Vorbild:                                           ║
║  Das Cerebellum speichert eingeübte Bewegungsabläufe als        ║
║  automatische Reflexe. Hier extrahiert es hochfrequente         ║
║  Event-Paare als deterministische Regeln.                       ║
║                                                                  ║
║  v0.8.0 – Schwellen per Preset konfigurierbar                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import time

_LOGGER = logging.getLogger(__name__)


class CerebellumRule:
    """Eine gelernte Routine."""
    def __init__(self, trigger: int, target: int, confidence: float,
                 avg_delay: float = 0):
        self.trigger = trigger
        self.target = target
        self.confidence = confidence
        self.avg_delay = avg_delay
        self.successes = 0
        self.failures = 0
        self.last_fired = 0


class Cerebellum:
    """Routinen-Erkennung von KONTINUUM."""
    
    # Defaults für "ausgeglichen" – werden vom Config Flow überschrieben
    MIN_OBSERVATIONS = 5
    MIN_CONFIDENCE = 0.75
    MAX_RULES = 50
    RULE_COOLDOWN = 300
    
    def __init__(self):
        self.rules = {}  # "trigger_target" → CerebellumRule
    
    def compile_rules(self, hippocampus):
        """Extrahiert Routinen aus dem Hippocampus-Gedächtnis."""
        candidates = {}
        
        for bucket in hippocampus.transitions:
            for ngram, targets in hippocampus.transitions[bucket].items():
                if len(ngram) != 1:
                    continue
                trigger = ngram[0]
                total = hippocampus.totals[bucket][ngram]
                
                if total < self.MIN_OBSERVATIONS:
                    continue
                
                for target, count in targets.items():
                    # Self-Loop filtern (z.B. binary.off → binary.off)
                    if trigger == target:
                        continue
                    
                    conf = count / total
                    if conf < self.MIN_CONFIDENCE:
                        continue
                    
                    key = f"{trigger}_{target}"
                    if key not in candidates or conf > candidates[key][0]:
                        # Delay berechnen
                        dur_key = f"{trigger}_{target}"
                        durs = hippocampus.durations.get(dur_key, [])
                        avg_delay = sorted(durs)[len(durs) // 2] if len(durs) >= 3 else 60
                        
                        candidates[key] = (conf, count, trigger, target, avg_delay)
        
        sorted_rules = sorted(candidates.items(),
                               key=lambda x: x[1][0] * x[1][1], reverse=True)
        sorted_rules = sorted_rules[:self.MAX_RULES]
        
        new_rules = {}
        for key, (conf, count, trigger, target, avg_delay) in sorted_rules:
            rule = CerebellumRule(trigger, target, conf, avg_delay)
            if key in self.rules:
                rule.successes = self.rules[key].successes
                rule.failures = self.rules[key].failures
            new_rules[key] = rule
        
        self.rules = new_rules
        _LOGGER.info("Cerebellum: %d Routinen kompiliert (min_obs=%d, min_conf=%.0f%%)",
                     len(self.rules), self.MIN_OBSERVATIONS, self.MIN_CONFIDENCE * 100)
    
    def check(self, token_id: int):
        """Prüft ob ein Token eine Routine triggert."""
        now = time.time()
        for key, rule in self.rules.items():
            if rule.trigger == token_id:
                if (now - rule.last_fired) < self.RULE_COOLDOWN:
                    continue
                return rule
        return None
    
    def mark_fired(self, rule: CerebellumRule):
        """Markiert eine Regel als gefeuert."""
        rule.last_fired = time.time()
    
    def record_outcome(self, rule_key: str, success: bool):
        """Zeichnet Erfolg/Misserfolg einer Regel auf."""
        if rule_key in self.rules:
            if success:
                self.rules[rule_key].successes += 1
            else:
                self.rules[rule_key].failures += 1
                self.rules[rule_key].confidence *= 0.95
    
    def to_dict(self) -> dict:
        rules_data = {}
        for key, rule in self.rules.items():
            rules_data[key] = {
                "trigger": rule.trigger,
                "target": rule.target,
                "confidence": rule.confidence,
                "avg_delay": rule.avg_delay,
                "successes": rule.successes,
                "failures": rule.failures,
            }
        return {"rules": rules_data}
    
    def from_dict(self, data: dict):
        for key, rd in data.get("rules", {}).items():
            self.rules[key] = CerebellumRule(
                rd["trigger"], rd["target"], rd["confidence"],
                rd.get("avg_delay", 60)
            )
            self.rules[key].successes = rd.get("successes", 0)
            self.rules[key].failures = rd.get("failures", 0)
    
    @property
    def stats(self) -> dict:
        total_fires = sum(r.successes + r.failures for r in self.rules.values())
        total_success = sum(r.successes for r in self.rules.values())
        return {
            "rules_count": len(self.rules),
            "total_fires": total_fires,
            "success_rate": f"{total_success / max(1, total_fires):.0%}",
            "top_rules": [
                {"key": k, "conf": round(r.confidence, 2), "fires": r.successes + r.failures}
                for k, r in sorted(self.rules.items(),
                                    key=lambda x: x[1].confidence, reverse=True)[:5]
            ],
        }
