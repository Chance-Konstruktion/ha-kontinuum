"""Optional wearable preprocessing for KONTINUUM context enrichment."""

from __future__ import annotations

from datetime import datetime, timezone


class WearableProcessor:
    """Converts smartwatch/mobile metrics into normalized KONTINUUM tokens."""

    def __init__(self, thalamus):
        self.thalamus = thalamus

    def process_steps(self, person: str, steps: float, room: str = "house") -> dict:
        state = self.thalamus._bucket_value("steps", str(steps))
        return self._signal(room, "steps", state, f"wearable.{person}.steps")

    def process_heartrate(self, person: str, bpm: float, room: str = "house") -> dict:
        state = self.thalamus._bucket_value("heartrate", str(bpm))
        return self._signal(room, "heartrate", state, f"wearable.{person}.heartrate")

    def process_sleep_phase(self, person: str, phase: str, room: str = "bedroom") -> dict:
        phase_state = (phase or "unknown").lower()
        if phase_state in ("deep", "rem", "light", "awake"):
            state = phase_state
        else:
            state = "unknown"
        return self._signal(room, "sleep", state, f"wearable.{person}.sleep")

    def _signal(self, room: str, semantic: str, state: str, entity_id: str) -> dict:
        return {
            "token": f"{room}.{semantic}.{state}",
            "room": room,
            "semantic": semantic,
            "state": state,
            "entity_id": entity_id,
            "timestamp": datetime.now(timezone.utc),
        }
