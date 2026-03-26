"""Entorhinal Cortex: lightweight room-transition map."""

from __future__ import annotations

from collections import defaultdict


class EntorhinalCortex:
    def __init__(self):
        self.transitions = defaultdict(lambda: defaultdict(int))

    def observe_transition(self, from_room: str, to_room: str):
        if not from_room or not to_room or from_room == to_room:
            return
        self.transitions[from_room][to_room] += 1

    def predict_next_room(self, room: str) -> str | None:
        options = self.transitions.get(room, {})
        if not options:
            return None
        return max(options.items(), key=lambda x: x[1])[0]

    def to_dict(self) -> dict:
        return {"transitions": {k: dict(v) for k, v in self.transitions.items()}}

    def from_dict(self, data: dict):
        self.transitions = defaultdict(lambda: defaultdict(int))
        for k, v in data.get("transitions", {}).items():
            self.transitions[k] = defaultdict(int, v)
