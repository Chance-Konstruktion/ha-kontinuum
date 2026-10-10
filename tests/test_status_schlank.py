"""Der Status-Sensor bleibt schlank, egal wie viele Entitäten das Haus hat.

Auf .247 trug ``sensor.kontinuum_status`` am 10.10.2026 1,4 MB Attribute,
fast alles ``reticular.event_times`` (die Speicherform). Das WebSocket-Abo
verschickt den Zustand bei jedem Ereignis, das Dashboard blieb leer.
"""

import json
import time
from unittest.mock import MagicMock

from kontinuum_core.locus_coeruleus import LocusCoeruleus
from kontinuum_core.reticular import ReticularFormation

from custom_components.kontinuum.sensor import KontinuumStatusSensor


def _hirn(reticular, locus):
    hirn = {name: MagicMock() for name in (
        "cerebellum", "hippocampus", "thalamus", "spatial", "insula",
        "amygdala", "prefrontal", "hypothalamus", "cortex")}
    hirn["cerebellum"].rules = {}
    hirn["thalamus"].entity_semantic = {}
    hirn["thalamus"].entity_room = {}
    for name in ("hippocampus", "spatial", "insula", "amygdala",
                 "prefrontal", "hypothalamus", "cortex"):
        hirn[name].stats = {}
    hirn["reticular"] = reticular
    hirn["locus"] = locus
    return hirn


def test_reticular_und_locus_nur_als_zaehler():
    reticular = ReticularFormation()
    jetzt = time.time()
    for i in range(1500):
        for k in range(30):
            reticular.event_times[f"sensor.x{i}"].append(jetzt + k)
    locus = LocusCoeruleus()
    for k in range(2000):
        locus.events.append(jetzt + k)

    sensor = KontinuumStatusSensor.__new__(KontinuumStatusSensor)
    sensor._brain = _hirn(reticular, locus)
    attrs = sensor.extra_state_attributes

    assert "event_times" not in attrs["reticular"]
    assert attrs["reticular"]["tracked_entities"] == 1500
    assert "events" in attrs["locus_coeruleus"]
    assert attrs["locus_coeruleus"]["events"] == 2000
    assert len(json.dumps(attrs["reticular"])) < 500
    assert len(json.dumps(attrs["locus_coeruleus"])) < 200
