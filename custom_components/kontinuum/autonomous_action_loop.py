"""First Autonomous Action Loop (Prediction → Action → Feedback → Learning)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from .action_engine import ActionEngine
from .feedback_monitor import FeedbackMonitor
from .prefrontal import PrefrontalCortex

_LOGGER = logging.getLogger(__name__)


@dataclass
class Prediction:
    next_event: str
    confidence: float
    expected_seconds: float


class AutonomousActionLoop:
    def __init__(self, hass, hippocampus, spatial_cortex, insula, basal_ganglia, accumbens=None):
        self.hass = hass
        self.hippocampus = hippocampus
        self.spatial_cortex = spatial_cortex
        self.insula = insula
        self.basal_ganglia = basal_ganglia
        self.accumbens = accumbens
        self.prefrontal = PrefrontalCortex()
        self.action_engine = ActionEngine(hass)
        self.feedback_monitor = FeedbackMonitor(hass)
        self._watchdog_timer = None
        self._watchdog_interval = 60
        self._last_run_ts = 0.0

    def run(self, sequence: list[str]):
        self._last_run_ts = time.time()
        prediction = get_prediction(sequence, self.hippocampus)
        if prediction is None:
            return None

        action = map_token_to_action(prediction.next_event)
        if action is None:
            return None

        state = self._build_state()
        action_key = prediction.next_event
        q_value = self.basal_ganglia.get_q_value(state, action_key)

        should_execute = self.prefrontal.decide(prediction.confidence, q_value)
        reward = 0.0

        if should_execute:
            self.action_engine.execute_action(action, prediction.expected_seconds)
            expected_state = prediction.next_event.split(".")[-1]
            reward = self.feedback_monitor.monitor_feedback(
                action["entity_id"],
                expected_state=expected_state,
                timeout=10.0,
            )
            self.basal_ganglia.update_q_value(state, action_key, reward)
            if hasattr(self.basal_ganglia, "process_outcome"):
                self.basal_ganglia.process_outcome(
                    action["entity_id"],
                    positive=reward > 0,
                )
            if self.accumbens is not None:
                self.accumbens.reinforce(state, action_key, reward)

        updated_q = self.basal_ganglia.get_q_value(state, action_key)

        log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sequence": sequence,
            "prediction": prediction.next_event,
            "confidence": prediction.confidence,
            "delay": prediction.expected_seconds,
            "executed": should_execute,
            "reward": reward,
            "q_value": updated_q,
        }
        _LOGGER.info("FAL loop", extra={"fal": log})
        return log

    def start_watchdog(self):
        """Starts a 60-second watchdog that restarts stale loop state."""
        self.stop_watchdog()
        self._watchdog_timer = threading.Timer(self._watchdog_interval, self._watchdog_check)
        self._watchdog_timer.daemon = True
        self._watchdog_timer.start()

    def stop_watchdog(self):
        if self._watchdog_timer:
            self._watchdog_timer.cancel()
            self._watchdog_timer = None

    def _watchdog_check(self):
        now = time.time()
        if self._last_run_ts and (now - self._last_run_ts) > self._watchdog_interval:
            _LOGGER.warning("FAL watchdog: loop stale (>60s), resetting monitor/engine")
            self.action_engine = ActionEngine(self.hass)
            self.feedback_monitor = FeedbackMonitor(self.hass)
        self.start_watchdog()

    def _build_state(self) -> str:
        room = getattr(self.spatial_cortex, "current_room", "unknown") or "unknown"
        mode = getattr(self.insula, "current_mode", "active") or "active"
        time_bucket = datetime.now(timezone.utc).hour
        return f"{room}|{mode}|{time_bucket}"


def _mean(values: list[float]) -> float:
    if not values:
        return 1.0
    return float(sum(values)) / len(values)


def get_prediction(sequence: list[str], hippocampus) -> Prediction | None:
    if not sequence:
        return None

    last_token = sequence[-1]
    transitions = getattr(hippocampus, "transitions", {})
    durations = getattr(hippocampus, "durations", {})

    next_candidates = transitions.get(last_token, {})
    if not next_candidates:
        return None

    next_event, confidence = max(next_candidates.items(), key=lambda item: item[1])

    duration_values = durations.get((last_token, next_event), [])
    expected_seconds = _mean(duration_values)

    return Prediction(
        next_event=next_event,
        confidence=float(confidence),
        expected_seconds=expected_seconds,
    )


def map_token_to_action(token: str) -> dict | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None

    room, domain, state = parts
    service = {
        "on": "turn_on",
        "off": "turn_off",
        "open": "open_cover",
        "closed": "close_cover",
    }.get(state)
    if not service:
        return None

    return {
        "domain": domain,
        "service": service,
        "entity_id": f"{domain}.{room}",
    }
