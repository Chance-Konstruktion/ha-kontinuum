"""Optional network source normalization for KONTINUUM."""

from __future__ import annotations

from datetime import datetime, timezone


class NetworkMonitor:
    """Transforms infrastructure/network metrics into normalized tokens."""

    def process_router_clients(self, connected_clients: int, room: str = "house") -> dict:
        if connected_clients <= 4:
            state = "low"
        elif connected_clients <= 12:
            state = "medium"
        else:
            state = "high"
        return self._signal(room, "network", state, "network.router.clients")

    def process_server_cpu(self, host: str, cpu_load: float, room: str = "utility") -> dict:
        if cpu_load < 35:
            state = "low"
        elif cpu_load < 70:
            state = "medium"
        else:
            state = "high"
        return self._signal(room, "cpu", state, f"network.{host}.cpu")

    def _signal(self, room: str, semantic: str, state: str, entity_id: str) -> dict:
        return {
            "token": f"{room}.{semantic}.{state}",
            "room": room,
            "semantic": semantic,
            "state": state,
            "entity_id": entity_id,
            "timestamp": datetime.now(timezone.utc),
        }
