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
║  v0.13.0 – N-Gram Regeln: 2-gram und 3-gram Sequenzen         ║
║  → Kontextreichere Muster (z.B. motion+door → light)           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import time
from collections import deque

_LOGGER = logging.getLogger(__name__)


class CerebellumRule:
    """Eine gelernte Routine."""
    def __init__(self, trigger: int, target: int, confidence: float,
                 avg_delay: float = 0, ngram_order: int = 1,
                 trigger_sequence: tuple = None):
        self.trigger = trigger  # Letztes Token der Sequenz (für check())
        self.target = target
        self.confidence = confidence
        self.avg_delay = avg_delay
        self.ngram_order = ngram_order  # 1, 2, 3 oder 4
        self.trigger_sequence = trigger_sequence or (trigger,)  # Volle Sequenz
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
    MIN_DELAY = 2.0  # Sekunden – darunter = Hardware-Kopplung, kein Verhalten

    # v0.13.0: Confidence-Schwellen pro N-Gram Ordnung
    # Höhere N-Grams sind kontextreicher → niedrigere Schwelle nötig
    NGRAM_CONF_THRESHOLDS = {1: None, 2: 0.60, 3: 0.45, 4: 0.35}  # None = self.MIN_CONFIDENCE

    def __init__(self):
        self.rules = {}  # "trigger_target" → CerebellumRule
        self._recent_buffer = deque(maxlen=15)  # Letzte Token für Sequenz-Check
        self.stats = {"total_fired": 0}

    def compile_rules(self, hippocampus):
        """
        Extrahiert Routinen aus dem Hippocampus-Gedächtnis.

        v0.13.0: Unterstützt 1-gram, 2-gram und 3-gram Regeln.
        - 1-gram: A → B (wie bisher, conf >= 75%)
        - 2-gram: (A, B) → C (kontextreicher, conf >= 60%)
        - 3-gram: (A, B, C) → D (sehr spezifisch, conf >= 45%)
        """
        candidates = {}

        for bucket in hippocampus.transitions:
            for ngram, targets in hippocampus.transitions[bucket].items():
                n = len(ngram)
                if n not in (1, 2, 3, 4):
                    continue

                # Letztes Token der Sequenz als Trigger
                trigger = ngram[-1]
                total = hippocampus.totals[bucket][ngram]

                if total < self.MIN_OBSERVATIONS:
                    continue

                # Confidence-Schwelle abhängig von N-Gram Ordnung
                min_conf = self.NGRAM_CONF_THRESHOLDS.get(n, self.MIN_CONFIDENCE)
                if min_conf is None:
                    min_conf = self.MIN_CONFIDENCE

                for target, count in targets.items():
                    # Self-Loop filtern
                    if trigger == target:
                        continue

                    conf = count / total
                    if conf < min_conf:
                        continue

                    # Key: für N-gram Regeln die ganze Sequenz kodieren
                    if n == 1:
                        key = f"{trigger}_{target}"
                    else:
                        seq_str = ",".join(str(t) for t in ngram)
                        key = f"seq:{seq_str}_{target}"

                    # N-gram Bonus: Höhere N-grams = kontextreicher = besser
                    ngram_bonus = 1.0 + (n - 1) * 0.15  # 2-gram: 1.15, 3-gram: 1.3
                    effective_score = conf * count * ngram_bonus

                    if key not in candidates or effective_score > candidates[key][0] * candidates[key][1] * candidates[key][6]:
                        # Delay berechnen (immer vom letzten Token zum Target)
                        dur_key = f"{trigger}_{target}"
                        durs = hippocampus.durations.get(dur_key, [])
                        avg_delay = sorted(durs)[len(durs) // 2] if len(durs) >= 3 else 60

                        # Unter MIN_DELAY = Hardware-Kopplung
                        if avg_delay < self.MIN_DELAY:
                            continue

                        candidates[key] = (conf, count, trigger, target, avg_delay, n, ngram_bonus, ngram)

        sorted_rules = sorted(candidates.items(),
                               key=lambda x: x[1][0] * x[1][1] * x[1][6], reverse=True)
        sorted_rules = sorted_rules[:self.MAX_RULES]

        new_rules = {}
        for key, (conf, count, trigger, target, avg_delay, n, _, ngram) in sorted_rules:
            rule = CerebellumRule(trigger, target, conf, avg_delay,
                                  ngram_order=n, trigger_sequence=ngram)
            if key in self.rules:
                rule.successes = self.rules[key].successes
                rule.failures = self.rules[key].failures
            new_rules[key] = rule

        self.rules = new_rules
        n_by_order = {1: 0, 2: 0, 3: 0, 4: 0}
        for r in self.rules.values():
            n_by_order[r.ngram_order] = n_by_order.get(r.ngram_order, 0) + 1
        _LOGGER.info(
            "Cerebellum: %d Routinen kompiliert (1=%d, 2=%d, 3=%d, 4=%d)",
            len(self.rules), n_by_order[1], n_by_order[2], n_by_order[3], n_by_order[4],
        )
    
    def check(self, token_id: int):
        """
        Prüft ob ein Token eine Routine triggert.

        v0.13.0: Unterstützt Sequenz-Matching für 2-gram und 3-gram Regeln.
        """
        self._recent_buffer.append(token_id)
        now = time.time()
        best_rule = None
        best_order = 0

        for key, rule in self.rules.items():
            if rule.trigger != token_id:
                continue
            if (now - rule.last_fired) < self.RULE_COOLDOWN:
                continue

            # Sequenz-Match für N-gram > 1
            if rule.ngram_order > 1:
                seq = rule.trigger_sequence
                buf = list(self._recent_buffer)
                if len(buf) < len(seq):
                    continue
                # Prüfe ob die letzten N Token mit der Sequenz übereinstimmen
                if tuple(buf[-len(seq):]) != seq:
                    continue

            # Höhere N-grams bevorzugen (kontextreicher)
            if rule.ngram_order > best_order:
                best_rule = rule
                best_order = rule.ngram_order

        return best_rule
    
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
                "ngram_order": rule.ngram_order,
                "trigger_sequence": list(rule.trigger_sequence),
            }
        return {"rules": rules_data}

    def from_dict(self, data: dict):
        for key, rd in data.get("rules", {}).items():
            seq = tuple(rd.get("trigger_sequence", [rd["trigger"]]))
            self.rules[key] = CerebellumRule(
                rd["trigger"], rd["target"], rd["confidence"],
                rd.get("avg_delay", 60),
                ngram_order=rd.get("ngram_order", 1),
                trigger_sequence=seq,
            )
            self.rules[key].successes = rd.get("successes", 0)
            self.rules[key].failures = rd.get("failures", 0)
    
    @property
    def stats(self) -> dict:
        total_fires = sum(r.successes + r.failures for r in self.rules.values())
        total_success = sum(r.successes for r in self.rules.values())
        n_by_order = {1: 0, 2: 0, 3: 0, 4: 0}
        for r in self.rules.values():
            n_by_order[r.ngram_order] = n_by_order.get(r.ngram_order, 0) + 1
        return {
            "rules_count": len(self.rules),
            "rules_1gram": n_by_order[1],
            "rules_2gram": n_by_order[2],
            "rules_3gram": n_by_order[3],
            "rules_4gram": n_by_order[4],
            "total_fires": total_fires,
            "success_rate": f"{total_success / max(1, total_fires):.0%}",
            "top_rules": [
                {"key": k, "conf": round(r.confidence, 2),
                 "fires": r.successes + r.failures, "order": r.ngram_order}
                for k, r in sorted(self.rules.items(),
                                    key=lambda x: x[1].confidence, reverse=True)[:5]
            ],
        }
