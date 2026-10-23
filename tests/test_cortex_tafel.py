"""Tests für die Cortex-Tafel (ha-kontinuum #3): der Messanschluss des Organs.

Die Frage des Tickets: Bringt der Cortex (LLM-Agenten) messbar etwas gegen
„Cortex aus"? Gemessen wird am Messstand des Kerns (Spuren, Saaten,
Ereigniszeit), das Organ selbst wird gemessen, wie es ist — `baue_menue`,
`anlass`, `lies_wahl`, `entscheide`, `Nachhall` kommen aus
`custom_components.kontinuum.cortex_organ`, der Ollama-Aufruf läuft über den
ECHTEN `CortexAgent.waehle`/`_call_ollama`-Weg (kein zweiter Transport).

Was diese Tests festnageln:

- Die Frage, die das Werkzeug stellt, ist WÖRTLICH die des Organs (gepinnt
  gegen `Cortex.consult` mit gestopfter Uhr).
- Die Nutzlast des Aufrufs ist die des echten Wegs (format=antwort_schema,
  think=False, stream=False, gleiches Modell).
- Bei leerem Menü (< 2 Optionen) wird KEIN Modell gerufen — genau wie
  `Cortex.consult`. Das ist der CASAS-Befund als Test.
- Das Veto streicht nur der safety-Agent (wörtlich wie `CortexAgent.waehle`).
- Der Zufallsgegner (Abschaltprobe) zieht nur aus dem Menü und ist gesät.
- Die Überlagerung („die Wahl ist die Vorhersage") setzt das gewählte
  Token nach vorn, ohne die Engine-Zeile anzufassen.
- Die Zählung (Änderungen, Treffer, Vetos) wird im Test unabhängig
  nachgerechnet — nie geglaubt.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from kontinuum_core import KontinuumEngine

KERN = __import__("pathlib").Path(__file__).resolve().parent.parent
if str(KERN) not in sys.path:
    sys.path.insert(0, str(KERN))

from custom_components.kontinuum import cortex as cortex_mod          # noqa: E402
from custom_components.kontinuum.cortex import Cortex                 # noqa: E402
from custom_components.kontinuum.cortex_organ import (                # noqa: E402
    NICHTS,
    antwort_schema,
    baue_menue,
)
from werkzeug.cortex_berater import (                                 # noqa: E402
    Beratung,
    KostenSpion,
    OrganBerater,
    SkriptBerater,
    ZufallsBerater,
    frage_fuer,
)
from werkzeug.cortex_tafel import (                                   # noqa: E402
    FensterWaage,
    messe_ursprung,
    tafel_json,
    ueberlagere,
)

ZEIT = datetime(2026, 3, 2, 8, 0, tzinfo=timezone(timedelta(hours=2)))


# ---------------------------------------------------------------------------
# Ein Fake-Ollama: fängt die Nutzlast, antwortet aus dem Drehbuch
# ---------------------------------------------------------------------------

class FakeAntwort:
    def __init__(self, nutzlast, inhalt, extra=None):
        self._nutzlast = nutzlast
        self._inhalt = inhalt
        self._extra = extra or {}

    @property
    def status(self):
        return 200

    async def json(self):
        daten = {"message": {"content": self._inhalt},
                 "eval_count": self._extra.get("eval_count", 7),
                 "prompt_eval_count": self._extra.get("prompt_eval_count", 120),
                 "total_duration": self._extra.get("total_duration", 9e9),
                 "load_duration": self._extra.get("load_duration", 3e9)}
        return daten

    async def text(self):
        return self._inhalt


class _FakePost:
    def __init__(self, sitzung, url, nutzlast):
        self._sitzung, self._url, self._nutzlast = sitzung, url, nutzlast

    async def __aenter__(self):
        self._sitzung.nutzlasten.append(self._nutzlast)
        inhalt = self._sitzung.antworten.pop(0) if self._sitzung.antworten \
            else '{"wahl": 0, "grund": "leer", "sicherheit": 0}'
        return FakeAntwort(self._nutzlast, inhalt, self._sitzung.extra)

    async def __aexit__(self, *args):
        return False


class FakeSitzung:
    """Ersetzt aiohttp.ClientSession — fängt jeden POST, kein Netz."""

    def __init__(self, antworten=None, extra=None):
        self.antworten = list(antworten or [])
        self.extra = dict(extra or {})
        self.nutzlasten = []
        self.closed = False
        self.aufrufe = 0

    def post(self, url, json=None, timeout=None):        # noqa: A002
        self.aufrufe += 1
        return _FakePost(self, url, json)

    async def close(self):
        self.closed = True


def in_faden(coro):
    """Fährt eine Koroutine in eigenem Faden+Loop (schließt NICHT den
    Haupt-Loop — die Lehre aus test_cortex_organ, siehe Modul-Docstring)."""
    ergebnis, fehler = {}, {}

    def lauf():
        try:
            ergebnis["wert"] = asyncio.run(coro)
        except BaseException as problem:   # noqa: BLE001
            fehler["problem"] = problem

    faden = threading.Thread(target=lauf)
    faden.start()
    faden.join(timeout=60)
    if fehler:
        raise fehler["problem"]
    return ergebnis.get("wert")


# ---------------------------------------------------------------------------
# Ein kleines Haus: echte Engine, echte Thalamus-Regeln, Licht an/aus
# ---------------------------------------------------------------------------

def baue_haus(bereich="kueche", liga=("light",)):
    """Engine mit zwei bis drei Lichtern; definierte Tokens."""
    engine = KontinuumEngine()
    engine.sleep_consolidation._rng = random.Random(0)
    for raum in ("bad", "kueche", "wohnzimmer", "schlafzimmer"):
        engine.register_entity(f"light.{raum}", ha_area=raum, domain="light")
        engine.register_entity(f"binary_sensor.{raum}_bewegung",
                               ha_area=raum, domain="binary_sensor")
    return engine


def strom(tokens_folge, start=ZEIT, abstand_min=200):
    """Baut Ereignisse zu Tokens wie 'kueche.light.on' (raum.semantik.zustand)."""
    ereignisse = []
    for i, token in enumerate(tokens_folge):
        raum, semantik, zustand = token.split(".", 2)
        entity = {"light": f"light.{raum}", "motion": f"binary_sensor.{raum}_bewegung"}[semantik]
        ereignisse.append(SimpleNamespace(
            ts=start + timedelta(minutes=abstand_min * i),
            entity=entity, zustand=zustand, alt=None, token=token))
    return ereignisse


def ziele_aus(engine, ereignisse):
    """Der Ziel-Strom kommt von der Engine selbst (dieselbe Vokabel).

    Ein Ereignis ohne Token (verworfen) ist ein Testfehler: die echte Spur
    ist ausgedünnt — jedes Ereignis IST ein Zustandswechsel.
    """
    ziele = []
    for e in ereignisse:
        schnapp = engine.observe({"entity_id": e.entity, "new_state": e.zustand,
                                  "old_state": e.alt, "timestamp": e.ts})
        assert schnapp.token, f"verworfenes Ereignis im Teststrom: {e.entity} {e.zustand}"
        ziele.append(schnapp.token)
    return ziele


def kurzer_strom(n=296):
    """Über sechs Wochen: Bewegung und — quer durch die ganze Spur —
    Lichtschaltungen (auch in der Testwoche, sonst gibt es dort kein Menü)."""
    folge = []
    letzter = {}          # je Entität: der Zustand wechselt IMMER
    for i in range(n):
        raum = ("bad", "kueche", "wohnzimmer", "schlafzimmer")[i % 4]
        if i % 7 == 3:
            entity, semantik = f"light.{raum}", "light"
        else:
            entity, semantik = f"binary_sensor.{raum}_bewegung", "motion"
        letzter[entity] = "off" if letzter.get(entity) == "on" else "on"
        folge.append(f"{raum}.{semantik}.{letzter[entity]}")
    return strom(folge)


# ---------------------------------------------------------------------------
# Der Frage-Pin: wörtlich wie Cortex.consult
# ---------------------------------------------------------------------------

def schnapp_mit_menue(engine):
    """Fährt die Spur, bis ein Schnappschuss ein echtes Menü trägt."""
    for e in kurzer_strom():
        schnapp = engine.observe({"entity_id": e.entity, "new_state": e.zustand,
                                  "old_state": e.alt, "timestamp": e.ts})
        menue = baue_menue(schnapp.predictions, engine.thalamus, None)
        if len(menue) >= 2:
            return schnapp, menue
    raise AssertionError("kein Menü in der Testspur — der Pin braucht eines")


def test_frage_ist_woertlich_die_des_organs(monkeypatch):
    engine = baue_haus()
    schnapp, menue = schnapp_mit_menue(engine)
    brain = {"thalamus": engine.thalamus,
             "_last_predictions": schnapp.predictions,
             "prefrontal": engine.prefrontal_cortex}

    # Die Uhr des Organs steht: MIN_INTERVAL (30 s) ist eingehalten.
    monkeypatch.setattr(cortex_mod.time, "time", lambda: 10_000.0)
    sitzung = FakeSitzung(antworten=['{"wahl": 1, "grund": "ok", "sicherheit": 60}'])
    cortex = Cortex()
    cortex.configure([{"name": "comfort", "provider": "ollama",
                       "model": "testmodell", "url": "http://fake:11434"}])
    cortex._session = sitzung
    ergebnis = in_faden(cortex.consult(brain, anlass="knapp"))
    assert ergebnis is not None, "consult hat nicht gefragt"
    gestellte_frage = sitzung.nutzlasten[0]["messages"][1]["content"]

    meine_frage = frage_fuer(brain, "knapp", menue)
    assert meine_frage == gestellte_frage


def test_berater_nutzlast_ist_die_des_echten_wegs():
    engine = baue_haus()
    schnapp, menue = schnapp_mit_menue(engine)

    # A) der echte Weg: CortexAgent.waehle über _call_ollama
    sitzung_a = FakeSitzung(antworten=['{"wahl": 1, "grund": "ok", "sicherheit": 60}'])
    agent = cortex_mod.CortexAgent("comfort", "ollama", "testmodell",
                                   "http://fake:11434", "", "SYSTEM")
    in_faden(agent.waehle("FRAGE", menue, sitzung_a, timeout=90))

    # B) der Messweg: derselbe Aufbau über die Tafel-Maschine
    berater = OrganBerater({"thalamus": engine.thalamus,
                            "_last_predictions": schnapp.predictions,
                            "prefrontal": engine.prefrontal_cortex},
                           agenten=("comfort",), modell="testmodell",
                           url="http://fake:11434",
                           sitzung_bauer=lambda: FakeSitzung(
                               antworten=['{"wahl": 1, "grund": "ok", "sicherheit": 60}']))
    beratung = berater.berate(jetzt_s=100.0, anlass="knapp", menue=menue)

    nutz_a = dict(sitzung_a.nutzlasten[0])
    # Der Messweg fragt dieselbe Maschine (die System-Prompt-Prüfung unten
    # deckt den Rest); Modell, format, stream, think müssen gleich sein.
    assert beratung.menue == menue
    assert nutz_a["stream"] is False
    assert nutz_a["think"] is False
    assert nutz_a["format"] == antwort_schema(menue, mit_veto=False)
    assert nutz_a["messages"][0]["role"] == "system"


def test_berater_liest_die_wahl_und_die_kosten():
    engine = baue_haus()
    schnapp = engine.observe({"entity_id": "light.kueche", "new_state": "on",
                              "old_state": "off", "timestamp": ZEIT})
    menue = [{"id": 0, "text": "nichts tun"},
             {"id": 1, "token": "kueche.light.on", "entity_id": "light.kueche",
              "zustand": "on", "text": "light.kueche → on"},
             {"id": 2, "token": "kueche.light.off", "entity_id": "light.kueche",
              "zustand": "off", "text": "light.kueche → off"}]
    sitzung = FakeSitzung(antworten=['{"wahl": 2, "grund": "aus", "sicherheit": 70}'],
                          extra={"eval_count": 11, "prompt_eval_count": 150,
                                 "total_duration": 8e9, "load_duration": 2e9})
    berater = OrganBerater({"thalamus": engine.thalamus, "_last_predictions": [],
                            "prefrontal": engine.prefrontal_cortex},
                           agenten=("comfort",), modell="testmodell",
                           url="http://fake:11434",
                           sitzung_bauer=lambda: sitzung)
    beratung = berater.berate(jetzt_s=100.0, anlass="knapp", menue=menue)

    assert beratung.wahl == 2
    assert beratung.wahl_token == "kueche.light.off"
    assert beratung.wahl_entity == "light.kueche"
    assert beratung.tokens_prompt == [150]
    assert beratung.tokens_antwort == [11]
    assert beratung.ladungen == [pytest.approx(2.0, abs=0.01)]
    assert beratung.dauer_s >= 0.0


def test_ungueltige_antwort_wird_nichts_tun():
    engine = baue_haus()
    menue = [{"id": 0, "text": "nichts tun"},
             {"id": 1, "token": "kueche.light.on", "entity_id": "light.kueche",
              "zustand": "on", "text": "x"}]
    sitzung = FakeSitzung(antworten=["kein json hier"])
    berater = OrganBerater({"thalamus": engine.thalamus, "_last_predictions": [],
                            "prefrontal": engine.prefrontal_cortex},
                           agenten=("comfort",), modell="testmodell",
                           url="http://fake:11434",
                           sitzung_bauer=lambda: sitzung)
    beratung = berater.berate(jetzt_s=1.0, anlass="anomalie", menue=menue)
    assert beratung.wahl == NICHTS
    assert beratung.stimmen[0]["gueltig"] is False


def test_leeres_menue_ruft_kein_modell():
    engine = baue_haus()
    sitzung = FakeSitzung(antworten=['{"wahl": 1, "grund": "x", "sicherheit": 9}'])
    berater = OrganBerater({"thalamus": engine.thalamus, "_last_predictions": [],
                            "prefrontal": engine.prefrontal_cortex},
                           agenten=("comfort",), modell="testmodell",
                           url="http://fake:11434", sitzung_bauer=lambda: sitzung)
    nur_nichts = [{"id": 0, "text": "nichts tun"}]
    beratung = berater.berate(jetzt_s=1.0, anlass="knapp", menue=nur_nichts)
    assert sitzung.aufrufe == 0, "leeres Menü darf kein Modell wecken"
    assert beratung.wahl == NICHTS
    assert "Menü" in beratung.entscheidung.get("grund", "")


def test_veto_streicht_nur_der_safety_agent():
    engine = baue_haus()
    menue = [{"id": 0, "text": "nichts tun"},
             {"id": 1, "token": "kueche.light.on", "entity_id": "light.kueche",
              "zustand": "on", "text": "x"},
             {"id": 2, "token": "kueche.light.off", "entity_id": "light.kueche",
              "zustand": "off", "text": "y"}]
    antwort = '{"wahl": 1, "grund": "an", "sicherheit": 55, "veto": [1]}'

    # comfort: das Veto fällt weg (wörtlich wie CortexAgent.waehle)
    sitzung = FakeSitzung(antworten=[antwort])
    berater = OrganBerater({"thalamus": engine.thalamus, "_last_predictions": [],
                            "prefrontal": engine.prefrontal_cortex},
                           agenten=("comfort",), modell="m", url="http://fake:11434",
                           sitzung_bauer=lambda: sitzung)
    beratung = berater.berate(jetzt_s=1.0, anlass="knapp", menue=menue)
    assert beratung.stimmen[0]["veto"] == []
    assert beratung.entscheidung["gestrichen"] == []

    # safety: das Veto zählt und streicht Option 1
    sitzung = FakeSitzung(antworten=[antwort])
    berater = OrganBerater({"thalamus": engine.thalamus, "_last_predictions": [],
                            "prefrontal": engine.prefrontal_cortex},
                           agenten=("safety",), modell="m", url="http://fake:11434",
                           sitzung_bauer=lambda: sitzung)
    beratung = berater.berate(jetzt_s=1.0, anlass="knapp", menue=menue)
    assert beratung.stimmen[0]["veto"] == [1]
    assert beratung.entscheidung["gestrichen"] == [1]
    assert beratung.wahl == NICHTS, "gestrichene Wahl wird zu nichts tun"


# ---------------------------------------------------------------------------
# Der Zufallsgegner (Abschaltprobe)
# ---------------------------------------------------------------------------

def test_zufallsgegner_gesaet_und_nur_aus_dem_menue():
    menue = [{"id": 0, "text": "nichts tun"},
             {"id": 1, "token": "a.b.on", "entity_id": "x", "zustand": "on",
              "text": "x → on"},
             {"id": 2, "token": "a.b.off", "entity_id": "x", "zustand": "off",
              "text": "x → off"},
             {"id": 3, "token": "a.b.on", "entity_id": "y", "zustand": "on",
              "text": "y → on"}]
    einer = ZufallsBerater(saat=7)
    anderer = ZufallsBerater(saat=7)
    folge_a = [einer.berate(jetzt_s=float(i), anlass="knapp", menue=menue).wahl
               for i in range(20)]
    folge_b = [anderer.berate(jetzt_s=float(i), anlass="knapp", menue=menue).wahl
               for i in range(20)]
    assert folge_a == folge_b, "gleiche Saat, gleiche Folge"
    assert all(w in {0, 1, 2, 3} for w in folge_a)
    assert len(set(folge_a)) > 1, "ein Gegner, der immer dasselbe wählt, ist keiner"


def test_skript_und_zufall_zaehlen_wie_das_organ():
    """Skript- und Zufallsberater laufen durch dieselbe entscheide-Logik."""
    menue = [{"id": 0, "text": "nichts tun"},
             {"id": 1, "token": "a.b.on", "entity_id": "x", "zustand": "on",
              "text": "x → on"}]
    beratung = SkriptBerater([1]).berate(jetzt_s=0.0, anlass="knapp", menue=menue)
    assert beratung.wahl == 1 and beratung.wahl_token == "a.b.on"
    leer = SkriptBerater([1]).berate(jetzt_s=0.0, anlass="knapp",
                                     menue=[{"id": 0, "text": "nichts tun"}])
    assert leer.wahl == NICHTS


# ---------------------------------------------------------------------------
# Die Überlagerung: die Wahl ist die Vorhersage
# ---------------------------------------------------------------------------

def test_ueberlagerung_setzt_das_gewaehlte_token_nach_vorn():
    engine_liste = [("a.b.on", 0.9), ("a.b.off", 0.5), ("c.d.on", 0.2)]
    gleich = ueberlagere(engine_liste, None)
    assert gleich == engine_liste, "ohne Wahl bleibt die Engine-Zeile unberührt"
    auch_gleich = ueberlagere(engine_liste, "a.b.on")
    assert [t for t, _ in auch_gleich] == ["a.b.on", "a.b.off", "c.d.on"], \
        "das eigene Top-1 ändert nichts"
    geaendert = ueberlagere(engine_liste, "c.d.on")
    assert [t for t, _ in geaendert] == ["c.d.on", "a.b.on", "a.b.off"]
    assert geaendert[0][1] == 0.2, "die Konfidenz bleibt die der Engine"


# ---------------------------------------------------------------------------
# Die Schleife: Zählung unabhängig nachgerechnet
# ---------------------------------------------------------------------------

def test_zaehlung_wird_nachgerechnet_nicht_geglaubt():
    engine = baue_haus()
    ereignisse = kurzer_strom()
    ziele = ziele_aus(engine, ereignisse)
    # Ein Anlass bei jedem 30. Ereignis (der echte Anlass ist in
    # test_cortex_organ geprüft; hier wird die Schleife gezielt gefüttert),
    # und besonders oft in der Testwoche.
    start = ereignisse[0].ts
    grenze = start + timedelta(days=4 * 7)
    test_ende = grenze + timedelta(days=7)
    im_test = [i for i, e in enumerate(ereignisse) if grenze <= e.ts < test_ende]
    assert len(im_test) > 10, "der Strom muss eine Testwoche tragen"

    def anlass_fn(i, predictions, anomalie, jetzt, letzte_beratung):
        if i in set(range(0, len(ereignisse), 3)) and jetzt - letzte_beratung >= 900:
            return "knapp" if i % 2 else "anomalie"
        return None

    engine_a = baue_haus()
    berater = SkriptBerater([2, 1, 2, 1, 0, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2])
    tafel = messe_ursprung(ereignisse, ziele, 4, berater,
                           engine=engine_a, anlass_fn=anlass_fn)
    assert tafel.test_ereignisse == len(im_test)
    assert len(tafel.beratungen) > 0
    assert sum(tafel.menues.values()) == sum(1 for _ in tafel.beratungen) + \
        tafel.menues.get("leer", 0)

    # Unabhängig nachrechnen: für jede Beratung das nächste bewertete
    # Ereignis suchen und die Treffer selbst zählen.
    aenderungen, richtig, vetos_falsch, vetos_richtig = 0, 0, 0, 0
    for b in tafel.beratungen:
        assert b.wahl in {o["id"] for o in b.menue}
        if b.wahl != 1:
            aenderungen += 1
        naechstes = next((e for e in ereignisse if e.ts > b.zeit_ts), None)
        if naechstes is not None and not (grenze <= naechstes.ts < test_ende):
            naechstes = None
        if b.wahl not in (NICHTS, 1) and naechstes is not None:
            option = next(o for o in b.menue if o["id"] == b.wahl)
            if option["entity_id"] == naechstes.entity and \
                    option["zustand"] == naechstes.zustand:
                richtig += 1
        for g in b.entscheidung.get("gestrichen", []):
            option = next(o for o in b.menue if o["id"] == g)
            if naechstes is not None and option["entity_id"] == naechstes.entity \
                    and option["zustand"] == naechstes.zustand:
                vetos_richtig += 1
            else:
                vetos_falsch += 1
    assert tafel.aenderungen == aenderungen
    assert tafel.aenderungen_richtig_sofort == richtig
    assert tafel.vetos_richtig_verhindert == vetos_richtig
    assert tafel.vetos_falsch_verhindert == vetos_falsch


def test_engine_zeile_bleibt_unberuehrt():
    """Die Überlagerung färbt nie auf die Engine-Zeile ab."""
    engine = baue_haus()
    ereignisse = kurzer_strom()
    ziele = ziele_aus(engine, ereignisse)
    start = ereignisse[0].ts
    grenze = start + timedelta(days=28)

    def anlass_fn(i, predictions, anomalie, jetzt, letzte_beratung):
        if grenze <= (start + timedelta(minutes=200 * i)) < grenze + timedelta(days=7) \
                and i % 4 == 0 and jetzt - letzte_beratung >= 900:
            return "knapp"
        return None

    stumm = SkriptBerater([1] * 40)          # bestätigt immer die Engine
    frech = SkriptBerater([2] * 40)          # ändert, sobald Option 2 da ist
    tafel_stumm = messe_ursprung(ereignisse, ziele, 4, stumm, engine=baue_haus(),
                                 anlass_fn=anlass_fn)
    tafel_frech = messe_ursprung(ereignisse, ziele, 4, frech, engine=baue_haus(),
                                 anlass_fn=anlass_fn)
    zeile_stumm = tafel_stumm.systeme["Engine"]
    zeile_frech = tafel_frech.systeme["Engine"]
    assert (zeile_stumm.gesamt, zeile_stumm.top1, zeile_stumm.top3) == \
        (zeile_frech.gesamt, zeile_frech.top1, zeile_frech.top3), \
        "die Engine-Zeile hängt nicht am Berater"
    assert sum(1 for b in tafel_frech.beratungen if b.wahl == 2) > 0


def test_tafel_ist_deterministisch():
    engine = baue_haus()
    ereignisse = kurzer_strom()
    ziele = ziele_aus(engine, ereignisse)
    start = ereignisse[0].ts
    grenze = start + timedelta(days=28)

    def anlass_fn(i, predictions, anomalie, jetzt, letzte_beratung):
        if grenze <= (start + timedelta(minutes=200 * i)) < grenze + timedelta(days=7) \
                and i % 5 == 0 and jetzt - letzte_beratung >= 900:
            return "knapp"
        return None

    def lauf():
        return messe_ursprung(ereignisse, ziele, 4, SkriptBerater([2, 1] * 20),
                              engine=baue_haus(), anlass_fn=anlass_fn)

    a, b = lauf(), lauf()
    assert tafel_json(a) == tafel_json(b)


def test_motion_strom_ohne_hebel_keine_beratung_kein_aufruf():
    """CASAS als Test: nur Bewegung ⇒ Menü leer ⇒ kein Modell, keine Beratung."""
    engine = baue_haus()
    folge = []
    letzter = {}
    for i in range(300):
        raum = ("bad", "kueche", "wohnzimmer", "schlafzimmer")[i % 4]
        entity = f"binary_sensor.{raum}_bewegung"
        letzter[entity] = "off" if letzter.get(entity) == "on" else "on"
        folge.append(f"{raum}.motion.{letzter[entity]}")
    ereignisse = strom(folge)
    ziele = ziele_aus(engine, ereignisse)
    sitzung = FakeSitzung()
    berater = OrganBerater({"thalamus": engine.thalamus, "_last_predictions": [],
                            "prefrontal": engine.prefrontal_cortex},
                           agenten=("comfort",), modell="m", url="http://fake:11434",
                           sitzung_bauer=lambda: sitzung)

    def immer_anlass(i, predictions, anomalie, jetzt, letzte_beratung):
        if jetzt - letzte_beratung >= 900:
            return "anomalie"
        return None

    tafel = messe_ursprung(ereignisse, ziele, 4, berater, engine=engine,
                           anlass_fn=immer_anlass)
    assert len(tafel.beratungen) == 0, "ohne handelbare Tokens gibt es keine Beratung"
    assert tafel.menues.get("leer", 0) > 0, "die Anlässe müssen gesehen worden sein"
    assert sitzung.aufrufe == 0, "kein Menü heißt: kein Modellaufruf"


def test_bericht_und_json_tragen_die_pflichtfelder():
    engine = baue_haus()
    ereignisse = kurzer_strom()
    ziele = ziele_aus(engine, ereignisse)
    start = ereignisse[0].ts
    grenze = start + timedelta(days=28)

    def anlass_fn(i, predictions, anomalie, jetzt, letzte_beratung):
        if grenze <= (start + timedelta(minutes=200 * i)) < grenze + timedelta(days=7) \
                and i % 6 == 0 and jetzt - letzte_beratung >= 900:
            return "knapp"
        return None

    class FakeGegner:
        """Die Gegner-Zeile des Messstands braucht nur vorhersage()."""
        name = "B2"

        def vorhersage(self, zeit, k):
            return [("kitchen.light.on", 0.4)]

        def beobachte(self, token, zeit=None):
            pass

    tafel = messe_ursprung(ereignisse, ziele, 4, SkriptBerater([1] * 20),
                           engine=baue_haus(), anlass_fn=anlass_fn,
                           gegner_schar={"B2": FakeGegner()},
                           quelle="sim-klassisch-s1", haus_typ="klassisch")
    daten = tafel_json(tafel)
    for schluessel in ("quelle", "haus_typ", "train_wochen", "test_ereignisse",
                       "systeme", "beratungen", "beratungen_je_1000",
                       "aenderungen", "aenderungen_richtig_sofort",
                       "vetos_richtig_verhindert", "vetos_falsch_verhindert",
                       "kosten", "menues", "anlaesse"):
        assert schluessel in daten, f"{schluessel} fehlt in der Tafel"
    assert "Engine" in daten["systeme"] and "Engine+Cortex" in daten["systeme"]
    assert "B2" in daten["systeme"]


# ---------------------------------------------------------------------------
# Die Fenster-Waage: die Grenze ist genau
# ---------------------------------------------------------------------------

MENUE = [{"id": 0, "text": "nichts tun"},
         {"id": 1, "token": "a.light.on", "entity_id": "light.a",
          "zustand": "on", "text": "a → on"},
         {"id": 2, "token": "a.light.off", "entity_id": "light.a",
          "zustand": "off", "text": "a → off"}]


def test_fensterwaage_grenze_900_zaehlt_900_1_nicht():
    # genau auf der Grenze: zählt
    waage = FensterWaage(fenster_s=900.0)
    waage.oeffne(0.0, MENUE, {"wer": 2}, [])
    waage.beobachte("light.a", "off", 900.0)
    geschlossen = waage.schliesse(901.0)
    assert len(geschlossen) == 1
    assert geschlossen[0]["wahrheit"] == 2
    assert waage.quoten["wer"] == [1, 1]

    # eine Zehntelsekunde zu spät: das Ereignis zählt NICHT mehr
    waage = FensterWaage(fenster_s=900.0)
    waage.oeffne(0.0, MENUE, {"wer": 2}, [])
    waage.beobachte("light.a", "off", 900.1)
    geschlossen = waage.schliesse(901.0)
    assert geschlossen[0]["wahrheit"] is None, \
        "das schließende Ereignis darf nicht als Wahrheit gelten"
    assert waage.quoten["wer"] == [0, 1]

    # nichts passiert: „nichts tun" (0) ist die Wahrheit
    waage = FensterWaage(fenster_s=900.0)
    waage.oeffne(0.0, MENUE, {"wer": 2}, [])
    waage.schliesse(1000.0)
    assert waage.quoten["wer"] == [0, 1]


def test_fensterwaage_wahrheit_ist_das_ERSTE_ereignis_im_fenster():
    waage = FensterWaage(fenster_s=900.0)
    waage.oeffne(0.0, MENUE, {"wer": 1, "nichts": 0}, [])
    waage.beobachte("light.a", "off", 100.0)     # Option 2 tritt ein ...
    waage.beobachte("light.a", "on", 200.0)      # ... danach Option 1
    waage.schliesse(1000.0)
    assert waage.quoten["wer"] == [0, 1], "die erste eintretende Option ist die Wahrheit"
    assert waage.quoten["nichts"] == [0, 1]


def test_fensterwaage_schliesst_je_beratung_einzeln():
    waage = FensterWaage(fenster_s=900.0)
    waage.oeffne(0.0, MENUE, {"wer": 1}, [])
    waage.oeffne(5000.0, MENUE, {"wer": 1}, [])
    waage.beobachte("light.a", "on", 5500.0)
    fertig = waage.schliesse(6000.0)
    assert len(fertig) == 2
    assert waage.quoten["wer"] == [1, 2]


def test_schleife_mit_fenster_eins_laesst_nichts_als_wahrheit():
    """Ein Fenster von 1 s kann kein Ereignis fassen (Takt 200 min):
    also muss jedes „nichts tun" richtig sein — die Grenze wirkt."""
    engine = baue_haus()
    ereignisse = kurzer_strom()
    ziele = ziele_aus(engine, ereignisse)
    start = ereignisse[0].ts
    grenze = start + timedelta(days=28)

    def anlass_fn(i, predictions, anomalie, jetzt, letzte_beratung):
        if grenze <= (start + timedelta(minutes=200 * i)) < grenze + timedelta(days=7) \
                and i % 5 == 0 and jetzt - letzte_beratung >= 900:
            return "knapp"
        return None

    tafel = messe_ursprung(ereignisse, ziele, 4, SkriptBerater([1] * 20),
                           engine=engine, anlass_fn=anlass_fn, fenster_s=1.0)
    treffer, n = tafel.fenster["nichts"]
    assert n == len(tafel.beratungen) > 0
    assert treffer == n, "bei 1 s Fenster ist nichts tun immer die Wahrheit"
