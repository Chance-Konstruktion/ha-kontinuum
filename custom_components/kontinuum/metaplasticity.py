"""MetaPlasticity – HA wrapper around kontinuum_core.MetaPlasticity.

Keeps the same external API as the previous HA-native implementation
so __init__.py needs no changes:

    MetaPlasticity(hass)
    await metaplasticity.async_load()
    await metaplasticity.async_start(interval_hours=24)
    await metaplasticity.async_stop()
    await metaplasticity.async_save()

Internally it delegates to the HA-free core implementation, wired
via HAScheduler (Scheduler Protocol) and a lazy brain-module proxy
that reads from hass.data[DOMAIN] at call time.
"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from kontinuum_core.metaplasticity import MetaPlasticity as _CoreMetaPlasticity

from .const import DOMAIN, STORAGE_PATH
from .ha_scheduler import HAScheduler

_LOGGER = logging.getLogger(__name__)


class _LazyBrainModules:
    """Proxy that reads hass.data[DOMAIN] on every access.

    This avoids a chicken-and-egg problem: MetaPlasticity is created
    before the full brain dict is assembled in async_setup_entry.
    By the time _collect_metrics() is first called (24 h later),
    hass.data[DOMAIN] is fully populated.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    def get(self, key: str, default=None):
        return self._hass.data.get(DOMAIN, {}).get(key, default)


class MetaPlasticity:
    """HA wrapper around kontinuum_core.MetaPlasticity."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        storage_path = hass.config.path(STORAGE_PATH)
        self._scheduler = HAScheduler(hass)
        self._core = _CoreMetaPlasticity(
            storage_path=storage_path,
            scheduler=self._scheduler,
            brain_modules=_LazyBrainModules(hass),
            event_callback=self._fire_event,
        )

    # ---- Lifecycle ---------------------------------------------------

    async def async_load(self) -> None:
        await self.hass.async_add_executor_job(self._core.load)

    async def async_save(self) -> None:
        await self.hass.async_add_executor_job(self._core.save)

    async def async_start(self, interval_hours: int = 24) -> None:
        self._core.start(interval_hours)

    async def async_stop(self) -> None:
        self._scheduler.cancel_all()

    # ---- Params API (unchanged) -------------------------------------

    def get_params(self, module_name: str) -> dict:
        return self._core.get_params(module_name)

    def set_params(self, module_name: str, new_values: dict) -> None:
        self._core.set_params(module_name, new_values)

    # ---- HA event bridge --------------------------------------------

    def _fire_event(self, event_type: str, data: dict) -> None:
        self.hass.bus.async_fire(event_type, data)

    # ---- Pass-through to raw data dict (for diagnostics) -----------

    @property
    def data(self) -> dict:
        return self._core.data
