"""Action execution layer for the First Autonomous Action Loop (FAL)."""

from __future__ import annotations

import logging
import time

_LOGGER = logging.getLogger(__name__)


class ActionEngine:
    def __init__(self, hass):
        self.hass = hass

    def execute_action(self, action: dict, delay: float):
        wait_seconds = max(float(delay) - 1.0, 0.0)
        if wait_seconds > 0:
            time.sleep(wait_seconds)

        domain = action["domain"]
        service = action["service"]
        entity_id = action["entity_id"]

        self.hass.services.call(domain, service, {"entity_id": entity_id})
        _LOGGER.info(
            "FAL action executed",
            extra={
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "wait_seconds": round(wait_seconds, 3),
            },
        )
