"""Stufe 3 (Lagebild + Börse, kontinuum-core >= 0.7) — der Leim.

``lagebild.py`` hat keine Home-Assistant-Importe; geladen wird es direkt
über den Pfad, damit diese Tests auch ohne Home Assistant laufen. Mit einem
Kern < 0.7 ist ``STUFE3`` falsch: Dann prüft nur der erste Test, dass alles
still bleibt — die übrigen überspringen sich MIT Grund (``-rs``).
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

PFAD = (Path(__file__).resolve().parents[1]
        / "custom_components" / "kontinuum" / "lagebild.py")
_spec = importlib.util.spec_from_file_location("kontinuum_lagebild", PFAD)
lagebild = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lagebild)

stufe3 = pytest.mark.skipif(
    not lagebild.STUFE3, reason="kontinuum-core < 0.7: kein Lagebild, keine Börse")

ORTSZEIT = timezone(timedelta(hours=2))
START = datetime(2026, 10, 5, 0, 0, tzinfo=ORTSZEIT)  # ein Montag


def _thalamus():
    from kontinuum_core.thalamus import Thalamus
    t = Thalamus()
    t.register_entity("light.wohnzimmer", ha_area="wohnzimmer", domain="light")
    t.register_entity("media_player.fernseher", ha_area="wohnzimmer",
                      domain="media_player")
    t.register_entity("device_tracker.pc", ha_area="buero", domain="device_tracker")
    return t


def test_ohne_stufe3_bleibt_alles_still():
    kortex, claustrum = lagebild.baue(set())
    if not lagebild.STUFE3:
        assert kortex is None and claustrum is None
        lagebild.fuettern(None, None, "light.x", "on", START)  # kein Fehler
        assert lagebild.auskunft(None) == {}
    else:
        assert kortex is not None and claustrum is not None
        assert claustrum.lage is kortex


def test_ziel_tracker_aus_personen():
    personen = [
        ("person.a", {"device_trackers": ["device_tracker.a_handy", "device_tracker.a_uhr"]}),
        ("person.b", {}),
        ("person.c", {"device_trackers": None}),
    ]
    assert lagebild.ziel_tracker_aus(personen) == {
        "device_tracker.a_handy", "device_tracker.a_uhr"}


def test_eigene_entitaeten_erkennt_er():
    assert lagebild.ist_eigene("sensor.kontinuum_lagebild")
    assert lagebild.ist_eigene("binary_sensor.kontinuum_anomalie")
    assert not lagebild.ist_eigene("sensor.fernseher_leistung")


@stufe3
def test_ziele_sind_personen_und_ihre_tracker():
    """Der Tracker des PCs (Router) ist Indiz, kein Ziel; KONTINUUMs
    eigene Sensoren lernt das Lagebild nie."""
    besitz = {"device_tracker.a_handy"}
    kortex, _ = lagebild.baue(besitz)
    thalamus = _thalamus()
    for eid, zustand in (("person.a", "home"), ("device_tracker.a_handy", "home"),
                         ("device_tracker.pc", "home"),
                         ("sensor.kontinuum_lagebild", "1")):
        lagebild.fuettern(kortex, thalamus, eid, zustand, START)
    assert kortex.ziele == ["person.a", "device_tracker.a_handy"]
    assert "device_tracker.pc" in kortex.im_blick
    assert "sensor.kontinuum_lagebild" not in kortex.zustand


@stufe3
def test_unavailable_wird_weg():
    kortex, _ = lagebild.baue(set())
    thalamus = _thalamus()
    lagebild.fuettern(kortex, thalamus, "light.wohnzimmer", "on", START)
    lagebild.fuettern(kortex, thalamus, "light.wohnzimmer", "unavailable", START)
    assert kortex.zustand["light.wohnzimmer"] == "weg"


@stufe3
def test_auskunft_nennt_anwesenheit_mit_belegen():
    """Drei Tage: abends daheim (Licht, Fernseher, PC), tagsüber weg. Danach
    nennt das Lagebild die Anwesenheit samt Belegen — und der Sensor
    bekommt alles, was er zeigt."""
    kortex, _ = lagebild.baue(set())
    thalamus = _thalamus()
    for tag in range(4):
        for stunde in range(24):
            t = START + timedelta(days=tag, hours=stunde)
            daheim = stunde >= 18 or stunde < 8
            an = "on" if daheim else "off"
            lagebild.fuettern(kortex, thalamus, "person.a",
                              "home" if daheim else "not_home", t)
            lagebild.fuettern(kortex, thalamus, "light.wohnzimmer", an, t)
            lagebild.fuettern(kortex, thalamus, "device_tracker.pc",
                              "home" if daheim else "not_home", t)
            lagebild.auskunft(kortex, t + timedelta(minutes=30))
    daten = lagebild.auskunft(kortex, START + timedelta(days=4, hours=20))
    a = daten["anwesenheit"]["person.a"]
    assert 0.0 <= a["zuhause"] <= 1.0
    assert a["wahrscheinlichster"] in ("home", "not_home")
    assert a["meldet"] == "home"
    assert a["belege"] and all(len(b) == 2 for b in a["belege"])
    assert a["takte"] > 0
    assert "zusammenhaenge" in daten and "stats" in daten


@stufe3
def test_boerse_liefert_das_listenformat_und_den_letzten_platz():
    """Die Liste der Börse hat das Format der Engine. Ein sicherer Reflex,
    den die Börse nicht ohnehin unter ihren besten fünf führt, steht auf
    dem LETZTEN Platz — er drängelt sich nicht mehr vor."""
    import random
    _, claustrum = lagebild.baue(set())
    wuerfel = random.Random(5)
    t = START
    for _ in range(300):
        t += timedelta(minutes=2)
        liste = lagebild.vorhersage(claustrum, wuerfel.randint(1, 8), t,
                                    "light", None, None, None)
    assert len(liste) == lagebild.TOP
    assert all(e[3] == "claustrum" and 0.0 <= e[1] <= 1.0 for e in liste)
    reflex = SimpleNamespace(target=999, confidence=0.9, successes=3)
    t += timedelta(minutes=2)
    liste = lagebild.vorhersage(claustrum, 1, t, "light", None, reflex, None)
    assert liste[-1][0] == 999 and liste[-1][3] == "cerebellum" and liste[-1][4] == 53
    assert all(e[3] == "claustrum" for e in liste[:-1])
