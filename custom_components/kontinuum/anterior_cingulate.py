"""
Anterior Cingulate Cortex (ACC) – Konfliktmonitor & Fehlerüberwachung.

Biologisches Vorbild: Der ACC erkennt Konflikte zwischen konkurrierenden
Handlungsoptionen und signalisiert wenn die Unsicherheit zu hoch ist.
Er moduliert die Entscheidungsschwelle: bei vielen Konflikten wird
vorsichtiger entschieden, bei Klarheit schneller.

Funktionen:
- Erkennt Konflikte zwischen Modulen (z.B. Hippocampus vs Amygdala)
- Trackt Vorhersage-Fehler (Erwartung vs Realität)
- Passt Konfidenz-Schwellen dynamisch an
- Signalisiert "cognitive control" bei hoher Unsicherheit

Performance: Nur Arithmetik, kein I/O, kein ML. ~0 ms pro Event.
"""

import logging
import time
from collections import deque

_LOGGER = logging.getLogger(__name__)

# Wie viele Entscheidungen im Fenster behalten
HISTORY_SIZE = 200
# EMA-Faktor für Konfliktrate
EMA_ALPHA = 0.05
# Schwellwerte für Konfliktniveau
CONFLICT_LOW = 0.2
CONFLICT_HIGH = 0.6


class AnteriorCingulateCortex:
    """Überwacht Konflikte zwischen Modulen und passt Entscheidungsschwellen an."""

    def __init__(self):
        # Konfliktverlauf
        self._conflict_history = deque(maxlen=HISTORY_SIZE)
        self._error_history = deque(maxlen=HISTORY_SIZE)

        # EMA-Werte
        self.conflict_level = 0.0      # 0.0 = kein Konflikt, 1.0 = maximaler Konflikt
        self.error_rate = 0.0          # Wie oft lag die Vorhersage falsch
        self.cognitive_control = 0.0   # Wie stark soll gebremst werden

        # Statistiken
        self.total_conflicts = 0
        self.total_agreements = 0
        self.total_errors = 0
        self.total_correct = 0
        self.threshold_adjustments = 0

        # Angepasste Schwelle (0.0 = leichtgläubig, 1.0 = maximale Vorsicht)
        self.confidence_threshold = 0.5  # Startwert
        self._last_update_ts = 0.0

    def observe_decision(self, proposals: list[dict]) -> float:
        """
        Beobachtet eine Entscheidungsrunde und misst den Konflikt.

        proposals: Liste von Modul-Vorschlägen, z.B.:
          [{"source": "hippocampus", "action": "light.on", "confidence": 0.8},
           {"source": "amygdala", "action": "veto", "confidence": 0.6}]

        Returns: Konfliktwert 0.0-1.0
        """
        if not proposals or len(proposals) < 2:
            self._conflict_history.append(0.0)
            self._update_ema()
            self.total_agreements += 1
            return 0.0

        # Konflikt = wie unterschiedlich sind die Aktionen?
        actions = [p.get("action", "") for p in proposals]
        unique_actions = set(actions)

        # Basaler Konflikt: Anteil unterschiedlicher Aktionen
        disagreement = (len(unique_actions) - 1) / max(1, len(actions) - 1)

        # Veto erhöht Konflikt stark
        has_veto = any(p.get("action") == "veto" or p.get("veto", False) for p in proposals)
        if has_veto:
            disagreement = min(1.0, disagreement + 0.3)

        # Konfidenz-Spread: Hohe Varianz = mehr Unsicherheit
        confidences = [p.get("confidence", 0.5) for p in proposals]
        if len(confidences) > 1:
            mean_conf = sum(confidences) / len(confidences)
            variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)
            disagreement = min(1.0, disagreement + variance * 0.5)

        self._conflict_history.append(disagreement)
        self._update_ema()

        if disagreement > CONFLICT_LOW:
            self.total_conflicts += 1
        else:
            self.total_agreements += 1

        return disagreement

    def observe_outcome(self, was_correct: bool):
        """Beobachtet ob die letzte Aktion korrekt war."""
        self._error_history.append(0.0 if was_correct else 1.0)

        if was_correct:
            self.total_correct += 1
        else:
            self.total_errors += 1

        # Error-Rate EMA
        self.error_rate = (
            EMA_ALPHA * (0.0 if was_correct else 1.0)
            + (1.0 - EMA_ALPHA) * self.error_rate
        )

        # Schwelle anpassen basierend auf Fehlern
        self._adjust_threshold()

    def get_adjusted_threshold(self, base_confidence: float = 0.5) -> float:
        """
        Gibt eine angepasste Konfidenz-Schwelle zurück.
        Bei hohem Konfliktniveau wird die Schwelle erhöht (vorsichtiger).
        Bei niedrigem Konfliktniveau wird sie gesenkt (schneller handeln).
        """
        return max(0.2, min(0.95, base_confidence + self.cognitive_control * 0.3))

    def should_defer_to_cortex(self) -> bool:
        """
        Gibt True zurück wenn die Unsicherheit so hoch ist,
        dass der Cortex (LLM) konsultiert werden sollte.
        """
        return self.conflict_level > CONFLICT_HIGH or self.error_rate > 0.4

    def _update_ema(self):
        """Aktualisiert EMA des Konfliktlevels."""
        if self._conflict_history:
            latest = self._conflict_history[-1]
            self.conflict_level = (
                EMA_ALPHA * latest + (1.0 - EMA_ALPHA) * self.conflict_level
            )

        # Cognitive control: Kombination aus Konflikt und Fehlerrate
        self.cognitive_control = min(1.0, self.conflict_level * 0.6 + self.error_rate * 0.4)

    def _adjust_threshold(self):
        """Passt die Konfidenz-Schwelle basierend auf Error-Rate an."""
        old = self.confidence_threshold

        if self.error_rate > 0.3:
            # Viele Fehler → vorsichtiger werden
            self.confidence_threshold = min(0.9, self.confidence_threshold + 0.02)
        elif self.error_rate < 0.1 and self.conflict_level < CONFLICT_LOW:
            # Wenig Fehler + wenig Konflikte → mutiger werden
            self.confidence_threshold = max(0.3, self.confidence_threshold - 0.01)

        if abs(old - self.confidence_threshold) > 0.001:
            self.threshold_adjustments += 1

    @property
    def stats(self) -> dict:
        return {
            "conflict_level": round(self.conflict_level, 3),
            "error_rate": round(self.error_rate, 3),
            "cognitive_control": round(self.cognitive_control, 3),
            "confidence_threshold": round(self.confidence_threshold, 3),
            "total_conflicts": self.total_conflicts,
            "total_agreements": self.total_agreements,
            "total_errors": self.total_errors,
            "total_correct": self.total_correct,
            "threshold_adjustments": self.threshold_adjustments,
        }

    def to_dict(self) -> dict:
        return {
            "conflict_level": self.conflict_level,
            "error_rate": self.error_rate,
            "cognitive_control": self.cognitive_control,
            "confidence_threshold": self.confidence_threshold,
            "total_conflicts": self.total_conflicts,
            "total_agreements": self.total_agreements,
            "total_errors": self.total_errors,
            "total_correct": self.total_correct,
            "threshold_adjustments": self.threshold_adjustments,
        }

    def from_dict(self, data: dict):
        self.conflict_level = data.get("conflict_level", 0.0)
        self.error_rate = data.get("error_rate", 0.0)
        self.cognitive_control = data.get("cognitive_control", 0.0)
        self.confidence_threshold = data.get("confidence_threshold", 0.5)
        self.total_conflicts = data.get("total_conflicts", 0)
        self.total_agreements = data.get("total_agreements", 0)
        self.total_errors = data.get("total_errors", 0)
        self.total_correct = data.get("total_correct", 0)
        self.threshold_adjustments = data.get("threshold_adjustments", 0)
