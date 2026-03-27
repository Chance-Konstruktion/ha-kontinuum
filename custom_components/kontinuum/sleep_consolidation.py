"""
Sleep Consolidation – Hippocampaler Replay & Gedächtnis-Konsolidierung.

Biologisches Vorbild: Im Schlaf (oder bei Abwesenheit) werden Muster
des Tages "wiedergespielt" und konsolidiert. Starke Muster werden
verstärkt, schwache vergessen, neue Cerebellum-Regeln extrahiert.

Läuft in ruhigen Phasen (wenige Events) oder nachts automatisch.
Extrem ressourcenschonend: max 1x pro Stunde, nur wenn nötig.
"""

import logging
import time
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

# Konsolidierung läuft wenn:
# - Letzte Events > QUIET_THRESHOLD Sekunden her
# - Mindestens MIN_EVENTS seit letzter Konsolidierung
# - Max alle COOLDOWN_SECONDS
QUIET_THRESHOLD = 1800       # 30 Min ohne Events = "ruhig"
MIN_EVENTS_FOR_CONSOLIDATION = 50
COOLDOWN_SECONDS = 3600      # Max 1x pro Stunde
DECAY_BOOST_FACTOR = 1.5     # Schwache Muster stärker vergessen
REINFORCE_FACTOR = 1.08      # Starke Muster leicht verstärken


class SleepConsolidation:
    """Konsolidiert Muster in ruhigen Phasen."""

    def __init__(self):
        self.last_consolidation_ts = 0.0
        self.events_since_last = 0
        self.total_consolidations = 0
        self.last_patterns_pruned = 0
        self.last_patterns_reinforced = 0
        self.last_rules_extracted = 0

    def observe_event(self):
        """Zählt Events seit letzter Konsolidierung."""
        self.events_since_last += 1

    def should_consolidate(self, last_event_ts: float) -> bool:
        """Prüft ob konsolidiert werden soll."""
        now = time.time()

        # Cooldown einhalten
        if now - self.last_consolidation_ts < COOLDOWN_SECONDS:
            return False

        # Genug Events gesammelt?
        if self.events_since_last < MIN_EVENTS_FOR_CONSOLIDATION:
            return False

        # Ruhige Phase? (lang genug keine Events)
        if last_event_ts > 0 and (now - last_event_ts) < QUIET_THRESHOLD:
            return False

        return True

    def consolidate(self, hippocampus, cerebellum, basal_ganglia=None):
        """
        Führt die Konsolidierung durch:
        1. Hippocampus: Schwache Muster stärker vergessen, starke verstärken
        2. Cerebellum: Regeln neu extrahieren aus aktuellem Wissen
        3. Basalganglien: Q-Values leicht in Richtung Mittelwert ziehen

        Returns dict mit Statistiken.
        """
        now = time.time()
        self.last_consolidation_ts = now
        events_processed = self.events_since_last
        self.events_since_last = 0
        self.total_consolidations += 1

        stats = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "events_processed": events_processed,
            "patterns_pruned": 0,
            "patterns_reinforced": 0,
            "rules_extracted": 0,
            "q_values_smoothed": 0,
        }

        # ── Phase 1: Hippocampus Replay ──
        # Schwache N-Gramme stärker vergessen, starke leicht verstärken
        if hippocampus and hasattr(hippocampus, "ngram_counts"):
            pruned = 0
            reinforced = 0

            for size_key, bucket_dict in hippocampus.ngram_counts.items():
                for bucket, ngram_dict in bucket_dict.items():
                    to_remove = []
                    for ngram, count in ngram_dict.items():
                        if count < 1.5:
                            # Schwaches Muster → stärker vergessen
                            new_count = count * (1.0 / DECAY_BOOST_FACTOR)
                            if new_count < 0.3:
                                to_remove.append(ngram)
                                pruned += 1
                            else:
                                ngram_dict[ngram] = new_count
                        elif count > 5.0:
                            # Starkes Muster → leicht verstärken (Replay)
                            ngram_dict[ngram] = min(count * REINFORCE_FACTOR, count + 2.0)
                            reinforced += 1

                    for ngram in to_remove:
                        del ngram_dict[ngram]

            stats["patterns_pruned"] = pruned
            stats["patterns_reinforced"] = reinforced
            self.last_patterns_pruned = pruned
            self.last_patterns_reinforced = reinforced

        # ── Phase 2: Cerebellum Rule Re-Extraction ──
        # Bestehende Regeln updaten basierend auf aktuellem Hippocampus-Wissen
        if cerebellum and hippocampus:
            try:
                rules_before = len(getattr(cerebellum, "rules", {}))
                cerebellum.extract_rules(hippocampus)
                rules_after = len(getattr(cerebellum, "rules", {}))
                stats["rules_extracted"] = max(0, rules_after - rules_before)
                self.last_rules_extracted = stats["rules_extracted"]
            except Exception:
                _LOGGER.debug("Cerebellum rule extraction during consolidation failed", exc_info=True)

        # ── Phase 3: Basalganglien Q-Value Smoothing ──
        # Extreme Q-Values leicht in Richtung Mittelwert ziehen
        # (verhindert dass einzelne zufällige Belohnungen dominieren)
        if basal_ganglia and hasattr(basal_ganglia, "q_table"):
            smoothed = 0
            q_table = basal_ganglia.q_table
            if q_table:
                all_values = [v for actions in q_table.values()
                              for v in actions.values() if isinstance(v, (int, float))]
                if all_values:
                    mean_q = sum(all_values) / len(all_values)
                    smooth_rate = 0.05  # 5% Richtung Mittelwert

                    for state, actions in q_table.items():
                        for action, q_val in actions.items():
                            if isinstance(q_val, (int, float)):
                                new_val = q_val + smooth_rate * (mean_q - q_val)
                                if abs(new_val - q_val) > 0.001:
                                    actions[action] = round(new_val, 6)
                                    smoothed += 1

            stats["q_values_smoothed"] = smoothed

        _LOGGER.info(
            "Sleep consolidation complete: pruned=%d, reinforced=%d, rules=%d, q_smooth=%d",
            stats["patterns_pruned"], stats["patterns_reinforced"],
            stats["rules_extracted"], stats["q_values_smoothed"],
        )

        return stats

    def to_dict(self) -> dict:
        return {
            "last_consolidation_ts": self.last_consolidation_ts,
            "events_since_last": self.events_since_last,
            "total_consolidations": self.total_consolidations,
            "last_patterns_pruned": self.last_patterns_pruned,
            "last_patterns_reinforced": self.last_patterns_reinforced,
            "last_rules_extracted": self.last_rules_extracted,
        }

    def from_dict(self, data: dict):
        self.last_consolidation_ts = data.get("last_consolidation_ts", 0.0)
        self.events_since_last = data.get("events_since_last", 0)
        self.total_consolidations = data.get("total_consolidations", 0)
        self.last_patterns_pruned = data.get("last_patterns_pruned", 0)
        self.last_patterns_reinforced = data.get("last_patterns_reinforced", 0)
        self.last_rules_extracted = data.get("last_rules_extracted", 0)
