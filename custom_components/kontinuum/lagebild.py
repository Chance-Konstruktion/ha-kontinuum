"""Stufe 3 in Home Assistant: Lagebild und Vorhersage-Börse.

Kommt aus kontinuum-core 0.7.0 (Leit-Ticket kontinuum-core#2):

* **Lagebild** (``AssociationCortex``): jede Zustandsänderung, auch
  ``unavailable`` — Reifendrucksensoren, die mit dem Auto wegfahren, sind
  dann ``weg`` statt verworfen. Daraus lernt es, welche Lage zu „Person ist
  da“ passt, und schließt zurück, wenn das Handy schweigt; dazu die
  Paar-Tafel „wenn A, dann B“.
* **Börse** (``Claustrum``): mischt Sequenz, Uhrzeit, Lage, Hippocampus und
  Reflex nach dem, was tatsächlich eintrat. Gemessen auf fünf CASAS-Häusern
  +9 bis +14 Punkte Top-1 über der besten dummen Regel; die alte Kette
  verlor gegen eine 1-Gramm-Kette.

Hier steht nur Leim, ohne Home-Assistant-Importe, damit er sich ohne Home
Assistant prüfen lässt. Mit einem älteren Kern ist ``STUFE3`` falsch, und
die Integration läuft wie bisher.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set, Tuple

try:  # kontinuum-core >= 0.7.0
    from kontinuum_core.association_cortex import AssociationCortex, lage_setzen
    from kontinuum_core.claustrum import Claustrum, boersen_liste
except ImportError:  # älterer Kern: kein Lagebild, keine Börse
    AssociationCortex = None
    Claustrum = None
    lage_setzen = None
    boersen_liste = None

STUFE3 = AssociationCortex is not None

#: So viele Vorhersagen trägt die Liste der Börse (wie die Engine).
TOP = 5


def baue(ziel_tracker: Set[str]) -> Tuple[Any, Any]:
    """Lagebild und Börse — oder (None, None) mit einem älteren Kern.

    Ziele der Anwesenheit sind ``person.*`` und die Tracker in
    ``ziel_tracker`` (eine lebende Menge: die Tracker, die einer Person
    gehören). Alle anderen Tracker — eine Router-Integration legt einen je
    Gerät im Netz an — bleiben Indizien der Lage: Der Tracker des PCs sagt
    etwas darüber, wer da ist, er ist aber niemand."""
    if not STUFE3:
        return None, None
    kortex = AssociationCortex(
        ziel=lambda eid: eid.startswith("person.") or eid in ziel_tracker)
    return kortex, Claustrum(lage=kortex)


def ist_eigene(entity_id: str) -> bool:
    """KONTINUUMs eigene Entitäten — sonst lernte das Lagebild sich selbst."""
    return entity_id.split(".", 1)[-1].startswith("kontinuum_")


def fuettern(kortex: Any, thalamus: Any, entity_id: str, zustand: Any, zeit: Any) -> None:
    """Eine Zustandsänderung ins Lagebild (vor jedem Filter aufzurufen)."""
    if kortex is None or not entity_id or ist_eigene(entity_id):
        return
    lage_setzen(kortex, thalamus, entity_id, zustand, zeit)


def ziel_tracker_aus(personen: Iterable[Tuple[str, Dict[str, Any]]]) -> Set[str]:
    """Die Tracker, die einer Person gehören (Attribut ``device_trackers``
    der ``person``-Entitäten)."""
    aus: Set[str] = set()
    for _, attribute in personen:
        for tracker in (attribute or {}).get("device_trackers") or []:
            if isinstance(tracker, str):
                aus.add(tracker)
    return aus


def vorhersage(claustrum: Any, token_id: int, zeit: Any, semantik: Optional[str],
               roh: Any, fired_rule: Any, faellig: Optional[int]) -> list:
    """Ein Token an die Börse; zurück kommt ihre Vorhersage im Listenformat
    ``(token_id, p, konfidenz, quelle, belege)``. Hippocampus und ein sicherer
    Reflex sind Stimmen im Rat; die überfällige Kadenz (``faellig``) und ein
    Reflex, den die Börse nicht ohnehin führt, bekommen höchstens den
    letzten Platz."""
    reflex = None
    if fired_rule is not None and fired_rule.confidence >= 0.7:
        reflex = (fired_rule.target, fired_rule.confidence, fired_rule.successes + 50)
    return boersen_liste(claustrum, token_id, zeit, semantik, hippocampus=roh,
                         reflex=reflex, faellig=faellig, top=TOP)


def auskunft(kortex: Any, jetzt: Any = None,
             zusammenhaenge: bool = True) -> Dict[str, Any]:
    """Was die Sensoren zeigen: Anwesenheit je Ziel (mit Belegen), die
    stärksten Zusammenhänge und den Lernumfang. ``jetzt`` schiebt die Uhr
    des Lagebilds vor — Zeit vergeht auch ohne Ereignis.

    Die Zusammenhänge lesen die ganze Paar-Tafel (quadratisch); auf einem
    Pi rechnet man sie seltener (``zusammenhaenge=False`` lässt sie weg)."""
    if kortex is None:
        return {}
    if jetzt is not None:
        kortex.tick(jetzt)
    anwesenheit: Dict[str, Any] = {}
    for ziel in list(kortex.ziele):
        a = kortex.anwesenheit(ziel)
        if a.get("zuhause") is None:
            continue  # noch nichts gelernt
        anwesenheit[ziel] = {
            "zuhause": round(a["zuhause"], 3),
            "wahrscheinlichster": a["wahrscheinlichster"],
            "meldet": kortex.zustand.get(ziel),
            "belege": [[m, round(b, 1)] for m, b in a["belege"]],
            "uhrzeit": a["uhrzeit"],
            "takte": a["takte"],
        }
    daten = {"anwesenheit": anwesenheit, "stats": kortex.stats}
    if zusammenhaenge:
        daten["zusammenhaenge"] = kortex.zusammenhaenge(top=10)
    return daten
