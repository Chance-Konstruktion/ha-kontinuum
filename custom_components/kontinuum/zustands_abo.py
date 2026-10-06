"""Das WebSocket-Abonnement auf die KONTINUUM-Entitäten
(Durchsicht 04.10., ha-kontinuum #1, Punkt 7).

Der Befund: das Dashboard holte alle 3 s ALLE Zustände über
``/api/states`` — je offenem Tab. Bei zwei offenen Tabs liefen also
40 volle Zustandslisten pro Minute über den Draht, damit ein
Hirn-Panel seine acht Sensoren zeichnen kann.

Der Heil dreht den Fluss: der Client abonniert EINMAL über
``kontinuum/abonniere`` und bekommt

* als Startereignis (``art: "stand"``) den vollen Stand aller
  Kontinuum-Entitäten — die REST-Ausgangsrunde entfällt ganz, und
* danach jede Zustandsänderung (``art: "aenderung"``) NUR von
  Kontinuum-Entitäten — das Abo ist serverseitig gefiltert, auf dem
  Draht reisen nur unsere Ereignisse.

Was eine Kontinuum-Entität ist, sagt nicht das Dashboard (das raten
müsste — es kennt ja nur Spitznamen), sondern die Entity-Registry:
jede Entität, die diese Integration angelegt hat (``platform ==
DOMAIN``). Registry-lose Kontinuum-Zustände (Präfix ``sensor.kontinuum_``
bzw. ``binary_sensor.kontinuum_``) reisen ausnahmsweise mit — und wer
seine Entität umbenennt (``sensor.vorhersage`` statt des Standard-
Namens), bleibt erreicht: der Registry-Eintrag kennt den neuen Namen.

Die Abmeldung räumt den Bus-Listener ab — das Abonnement hinterlässt
kein Leck (Punkt 1 hat gelehrt, wie die aussehen).
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ABO_TYP = "kontinuum/abonniere"

# Der Schlüssel in hass.data — bewacht gegen Doppelregistrierung
# (async_setup läuft je HA-Start einmal, Unittests rufen ihn manchmal
# öfter — die Registrierung muss trotzdem idempotent bleiben).
_GUARD = f"{DOMAIN}_zustands_abo_registriert"

# Entitäten ohne Registry-Eintrag erkennen wir am Präfix — dieselbe
# Familie, die das Dashboard seit jeher kennt.
_KONTINUUM_PRAEFIXE = ("sensor.kontinuum_", "binary_sensor.kontinuum_")

SCHEMA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): ABO_TYP}
)


def _zustand_als_dict(state) -> dict | None:
    """Ein State-Objekt in die REST-Gestalt (/api/states) bringen.

    Das Dashboard und seine Entdeckung (``discoverSensors``) lesen
    ``entity_id``, ``state`` und ``attributes`` — dieselbe Form, die
    der alte REST-Weg lieferte, damit oben nichts umlernen muss.
    """
    if state is None:
        return None
    return {
        "entity_id": state.entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
    }


def _kontinuum_entitaeten(hass: HomeAssistant) -> list[str]:
    """Alle Entity-IDs der Plattform — Registry vor Präfix.

    Die Registry ist die Wahrheit: jede Entität mit ``platform ==
    DOMAIN`` gehört uns, egal wie sie heute heisst. Registry-lose
    Zustände mit Kontinuum-Präfix reisen ausnahmsweise mit.
    """
    ids: list[str] = []
    registry = er.async_get(hass)
    for eintrag in registry.entities.values():
        if eintrag.platform == DOMAIN:
            ids.append(eintrag.entity_id)
    for eid in hass.states.async_entity_ids():
        if eid.startswith(_KONTINUUM_PRAEFIXE) and eid not in ids:
            ids.append(eid)
    return ids


def _ist_kontinuum(entity_id: str, registry, bekannt: set[str]) -> bool:
    """Die Draht-Wache: gehört diese Entität ins Abo?"""
    if not entity_id:
        return False
    if entity_id in bekannt:
        return True
    if entity_id.startswith(_KONTINUUM_PRAEFIXE):
        return True
    eintrag = registry.async_get(entity_id)
    return eintrag is not None and eintrag.platform == DOMAIN


@websocket_api.async_response
async def _handle_abo(hass: HomeAssistant, connection, msg) -> None:
    """Ein Abonnement: erster Stand, dann nur noch unsere Änderungen.

    ``@async_response`` ist kein Schmuck: HA ruft die WebSocket-Handler
    SYNCHRON — ein nacktes ``async def`` würde eine Coroutine zurücklassen,
    die niemand je plant (beobachtet am 05.10.: der Draht blieb stumm).
    Der Wrapper setzt den Handler als Aufgabe auf die Schleife.
    """
    registry = er.async_get(hass)
    # Die bekannte Schar wächst im Lauf — jede weitergeleitete Entität
    # bleibt gemeldet, auch wenn die Registry sie später streicht (eine
    # entfernte Entität schickt ihr eigenes Abschiedsereignis: der
    # Registry-Eintrag ist dann schon weg, das Präfix greift nicht
    # mehr — ``bekannt`` trägt die Erinnerung).
    bekannt = set(_kontinuum_entitaeten(hass))

    @callback
    def _weiterleiten(event) -> None:
        entity_id = event.data.get(ATTR_ENTITY_ID, "")
        if not _ist_kontinuum(entity_id, registry, bekannt):
            return
        bekannt.add(entity_id)
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "art": "aenderung",
                    "entity_id": entity_id,
                    "neu": _zustand_als_dict(event.data.get("new_state")),
                    "alt": _zustand_als_dict(event.data.get("old_state")),
                },
            )
        )

    unsub = hass.bus.async_listen(EVENT_STATE_CHANGED, _weiterleiten)

    @callback
    def _abmelden() -> None:
        """Das Abonnement räumt seinen Bus-Listener ab."""
        unsub()

    connection.subscriptions[msg["id"]] = _abmelden
    connection.send_result(msg["id"])
    # Der erste Stand reist als Ereignis — das Dashboard füllt daraus
    # Cache und Zeichnung, bevor die erste Änderung ankommt.
    connection.send_message(
        websocket_api.event_message(
            msg["id"],
            {
                "art": "stand",
                "zustaende": [
                    _zustand_als_dict(hass.states.get(eid))
                    or {
                        "entity_id": eid,
                        "state": "unavailable",
                        "attributes": {},
                        "last_changed": None,
                        "last_updated": None,
                    }
                    for eid in sorted(bekannt)
                ],
            },
        )
    )
    _LOGGER.debug(
        "KONTINUUM-Abo %s: erster Stand mit %d Entitäten",
        msg["id"],
        len(bekannt),
    )


def async_register_zustands_abo(hass: HomeAssistant) -> None:
    """Den Befehl ``kontinuum/abonniere`` anmelden (idempotent).

    HA 2025.1 führt die Registrierung als (Typ, Handler, Schema) —
    die alte Dict-Form ist versorgt.
    """
    if hass.data.get(_GUARD):
        return
    hass.data[_GUARD] = True
    websocket_api.async_register_command(hass, ABO_TYP, _handle_abo, SCHEMA)
    _LOGGER.info("KONTINUUM WebSocket-Abonnement angemeldet: %s", ABO_TYP)
