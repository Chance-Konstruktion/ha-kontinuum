"""Reticular Formation (RAS): lightweight attention and burst filter."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class ReticularFormation:
    BURST_WINDOW = 2.0
    BURST_LIMIT = 8
    COOLDOWN_SECONDS = 5.0

    def __init__(self):
        self.event_times = defaultdict(lambda: deque(maxlen=30))
        self.cooldown_until = {}
        self.filtered_events = 0

    def should_process(self, entity_id: str, domain: str = "") -> bool:
        now = time.time()
        cooldown = self.cooldown_until.get(entity_id, 0.0)
        if cooldown > now:
            self.filtered_events += 1
            return False

        dq = self.event_times[entity_id]
        dq.append(now)
        recent = [t for t in dq if now - t <= self.BURST_WINDOW]

        domain_factor = 1
        if domain == "sensor":
            domain_factor = 0
        threshold = self.BURST_LIMIT + domain_factor

        if len(recent) >= threshold:
            self.cooldown_until[entity_id] = now + self.COOLDOWN_SECONDS
            self.filtered_events += 1
            return False

        return True

    def get_priority(self, entity_id: str) -> float:
        now = time.time()
        dq = self.event_times.get(entity_id, [])
        if not dq:
            return 0.5
        recent = sum(1 for t in dq if now - t <= 30)
        if recent <= 2:
            return 1.0
        if recent <= 6:
            return 0.7
        return 0.3

    def get_global_priority(self) -> float:
        if not self.event_times:
            return 0.5
        vals = [self.get_priority(eid) for eid in list(self.event_times.keys())[-50:]]
        return sum(vals) / max(1, len(vals))

    def to_dict(self) -> dict:
        return {
            "event_times": {eid: list(times) for eid, times in self.event_times.items()},
            "cooldown_until": self.cooldown_until,
            "filtered_events": self.filtered_events,
        }

    def from_dict(self, data: dict):
        self.event_times = defaultdict(lambda: deque(maxlen=30))
        for eid, times in data.get("event_times", {}).items():
            self.event_times[eid] = deque(times[-30:], maxlen=30)
        self.cooldown_until = data.get("cooldown_until", {})
        self.filtered_events = data.get("filtered_events", 0)
