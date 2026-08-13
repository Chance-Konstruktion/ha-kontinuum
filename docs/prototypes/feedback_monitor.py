"""Feedback monitor for the First Autonomous Action Loop (FAL)."""

from __future__ import annotations

import time


class FeedbackMonitor:
    def __init__(self, hass):
        self.hass = hass

    def monitor_feedback(self, entity_id: str, expected_state: str, timeout: float = 10.0) -> float:
        start_state_obj = self.hass.states.get(entity_id)
        start_state = start_state_obj.state if start_state_obj else None
        deadline = time.time() + timeout

        while time.time() < deadline:
            state_obj = self.hass.states.get(entity_id)
            current_state = state_obj.state if state_obj else None

            if current_state is None:
                time.sleep(0.25)
                continue

            if current_state != expected_state and current_state != start_state:
                return -1.0

            if current_state == expected_state and current_state != start_state:
                return 1.0

            time.sleep(0.25)

        return 0.5
