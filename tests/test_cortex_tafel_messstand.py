"""Der Anschluss an den Kern-Messstand (ha-kontinuum #3).

Diese Tests brauchen einen kontinuum-core-Checkout (derselbe Stand, aus dem
Engine UND Messstand kommen — „ein Strom, ein Stand"). Ohne ihn sagen sie
das mit Namen und laufen nicht: der Kern kommt sonst von PyPI, und die
Messstand-Module `benchmarks.spur.*` sind nicht Teil des Pakets.

    KONTINUUM_KERN=/pfad/zu/kontinuum-core python -m pytest tests/test_cortex_tafel_messstand.py

Was gepinnt wird:

- Das Testfenster ist das des Messstands (dieselbe Zahl Testereignisse).
- Die Engine-Zeile der Tafel ist ZAHLENGLEICH mit der Engine-Zeile des
  Kern-Messstands auf derselben Spur (die Schleife ist die des Messstands;
  die Beratung hängt daneben, nicht darin).
- Der echte Anlass (`anlass` aus dem Organ) feuert in der klassischen
  Simulation und liefert Menüs — die Beratung ist dort keine Nullmenge.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
KERN = Path(os.environ.get("KONTINUUM_KERN", str(WURZEL.parent / "kontinuum-core")))
FEHLT = not (KERN / "benchmarks" / "spur" / "messstand.py").exists()

pytestmark = pytest.mark.skipif(
    FEHLT, reason=f"Kern-Checkout fehlt (KONTINUUM_KERN setzen): {KERN}")

if str(KERN) not in sys.path:
    sys.path.insert(0, str(KERN / "src"))
    sys.path.insert(0, str(KERN))
if str(WURZEL) not in sys.path:
    sys.path.insert(0, str(WURZEL))

# Der Kern-Import gehoert IN die Tests: beim Sammeln gibt es hier keinen
# Checkout (der skip greift erst beim Ausfuehren), und ein Import auf
# Modulebene machte die ganze Suite rot — genau das ist am 23.10. in der
# Pipeline passiert und wird hier geheilt.
from werkzeug.cortex_berater import SkriptBerater                     # noqa: E402


def _kern():
    """Die zwei Kern-Stücke, erst zur Laufzeit geholt."""
    from benchmarks.spur.messstand import messe_ursprung as kern_messung
    from werkzeug.cortex_tafel import aufbau_sim, messe_ursprung
    return kern_messung, aufbau_sim, messe_ursprung


def test_sim_traegt_das_testfenster_des_messstands():
    kern_messung, aufbau_sim, messe_ursprung = _kern()
    aufbau = aufbau_sim("klassisch", saat=1, tage=56, train_wochen=4, kern=KERN)
    tafel = messe_ursprung(
        aufbau.ereignisse, aufbau.ziele, 4, SkriptBerater([1] * 200),
        engine=aufbau.engine, gegner_schar=aufbau.gegner,
        uhr=aufbau.uhr, quelle=f"sim-klassisch-s1",
        haus_typ="klassisch")
    kern = kern_messung(aufbau.spur, 4)
    assert tafel.test_ereignisse == kern.test_ereignisse

    # Die Engine-Zeile ist die des Messstands — die Beratung färbt nicht ab.
    meine = tafel.systeme["Engine"]
    seine = kern.systeme["Engine"]
    assert (meine.gesamt, meine.top1, meine.top3) == \
        (seine.gesamt, seine.top1, seine.top3)


def test_echter_anlass_berät_in_der_klassischen_sim():
    _, aufbau_sim, messe_ursprung = _kern()
    aufbau = aufbau_sim("klassisch", saat=1, tage=56, train_wochen=4, kern=KERN)
    tafel = messe_ursprung(
        aufbau.ereignisse, aufbau.ziele, 4, SkriptBerater([1] * 200),
        engine=aufbau.engine, gegner_schar=aufbau.gegner,
        uhr=aufbau.uhr, quelle="sim-klassisch-s1",
        haus_typ="klassisch")
    assert len(tafel.beratungen) >= 1, "die klassische Sim muss Anlässe tragen"
    for beratung in tafel.beratungen:
        assert len(beratung.menue) >= 2
        assert all(o["id"] == 0 or o.get("entity_id") for o in beratung.menue)
        assert beratung.wahl in {o["id"] for o in beratung.menue}


def test_geraete_sim_ohne_handelbare_tokens():
    """Das Geräte-Haus trägt Leistung/PV — für das Organ meist kein Menü."""
    _, aufbau_sim, messe_ursprung = _kern()
    aufbau = aufbau_sim("geraete", saat=1, tage=56, train_wochen=4, kern=KERN)
    tafel = messe_ursprung(
        aufbau.ereignisse, aufbau.ziele, 4, SkriptBerater([1] * 200),
        engine=aufbau.engine, gegner_schar=aufbau.gegner,
        uhr=aufbau.uhr, quelle="sim-geraete-s1",
        haus_typ="geraete")
    assert tafel.menues.get("leer", 0) > 0, "das Geräte-Haus hat leere Menüs"
