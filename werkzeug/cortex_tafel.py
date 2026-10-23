"""Die Cortex-Tafel: der Messstand-Lauf mit dem Organ (ha-kontinuum #3).

Die Frage des Tickets: Bringt der Cortex (LLM-Agenten) messbar etwas gegen
„Cortex aus"? Diese Datei ist der Anschluss an den Kern-Messstand
(`kontinuum-core`, `benchmarks/spur`) — dieselben Spuren, dieselben
rollierenden Ursprünge, dieselbe Ereigniszeit. Was sie hinzufügt, hängt
NEBEN der Schleife, nicht darin:

* **Engine** — die Zeile des Messstands (wörtlich dieselbe Rechnung:
  predict-then-learn, Top-1/Top-3 gegen den Token-Strom, leere Listen
  zählen nicht).
* **Engine+Cortex** — dieselben Vorhersagen, aber nach einer Beratung
  zielt die erste Stelle auf das GEWÄHLTE Token („die Wahl ist die
  Vorhersage"; das Organ schreibt die Engine nicht zurück — die Identität
  ohne Beratung ist damit gemessen, nicht behauptet).
* **B2/B1/B0** — die dummen Gegner des Messstands auf denselben Testwochen.
* Dazu die Aktions-Ebene, die das Organ wirklich bedient: Änderungen der
  Engine-Wahl, ihre Treffer (sofort und im 900-s-Fenster des Nachhalls),
  Vetos (richtig/falsch verhindert) und die Kosten je Beratung.

Der Kern kommt als Checkout (``--kern``/``KONTINUUM_KERN``): Engine UND
Messstand aus EINEM Stand. Ohne Checkout sagt das Programm das mit Namen —
die Module `benchmarks.spur.*` sind nicht Teil des PyPI-Pakets.

Aufruf (Beispiele)::

    python -m werkzeug.cortex_tafel --kern ../kontinuum-core \\
        --sim klassisch --saaten 1 2 3 4 5 --ursprunge 4 5 6 7 \\
        --modell llama3.2:1b --agenten comfort --ziel build/cortex

    python -m werkzeug.cortex_tafel --kern ../kontinuum-core \\
        --trocken --sim klassisch --saaten 1 --ziel build/cortex
        # Drehbuch statt Modell — der Trockenlauf für CI
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from custom_components.kontinuum.cortex_organ import (
    NICHTS,
    Nachhall,
    anlass as organ_anlass,
    baue_menue,
)

from werkzeug.cortex_berater import (
    STANDARD_AGENTEN,
    STANDARD_URL,
    STANDARD_ZEITLIMIT,
    Beratung,
    OrganBerater,
    SkriptBerater,
    ZufallsBerater,
)

#: Das Nachhall-Fenster des Organs (900 s Ereigniszeit).
STANDARD_FENSTER_S = 900.0
#: Die dummen Gegner, in der Reihenfolge des Messstands.
GEGNER_NAMEN = ("B2", "B1", "B0")


# ---------------------------------------------------------------------------
# Die Tafel — je Ursprung
# ---------------------------------------------------------------------------

@dataclass
class TafelZeile:
    name: str
    gesamt: int = 0
    top1: int = 0
    top3: int = 0

    @property
    def top1_prozent(self) -> Optional[float]:
        return 100.0 * self.top1 / self.gesamt if self.gesamt else None

    @property
    def top3_prozent(self) -> Optional[float]:
        return 100.0 * self.top3 / self.gesamt if self.gesamt else None


@dataclass
class UrsprungsTafel:
    quelle: str
    haus_typ: str
    train_wochen: int
    berater: str = ""
    test_ereignisse: int = 0
    systeme: Dict[str, TafelZeile] = field(default_factory=dict)
    beratungen: List[Beratung] = field(default_factory=list)
    anlaesse: Dict[str, int] = field(default_factory=dict)
    menues: Dict[str, int] = field(default_factory=dict)
    aenderungen: int = 0
    davon_nichts: int = 0
    aenderungen_ohne_folge: int = 0
    aenderungen_richtig_sofort: int = 0
    vetos_richtig_verhindert: int = 0
    vetos_falsch_verhindert: int = 0
    sofort: Dict[str, List[int]] = field(default_factory=dict)
    fenster: Dict[str, List[int]] = field(default_factory=dict)
    fenster_organ: Dict[str, Optional[float]] = field(default_factory=dict)
    kosten: Dict[str, float] = field(default_factory=dict)

    @property
    def beratungen_je_1000(self) -> float:
        return (1000.0 * len(self.beratungen) / self.test_ereignisse
                if self.test_ereignisse else 0.0)


def _bilanz(zeile: TafelZeile, vorhersagen: Sequence, ziel: str) -> None:
    """Wörtlich die Bewertung des Messstands (auch die leere Regel)."""
    if not vorhersagen:
        return
    zeile.gesamt += 1
    if vorhersagen[0][0] == ziel:
        zeile.top1 += 1
    if any(token == ziel for token, _ in vorhersagen[:3]):
        zeile.top3 += 1


def _engine_vorhersage(schnapp, engine, letzte: List) -> List:
    """Wörtlich ``benchmarks.spur.messstand._engine_vorhersage``."""
    if not schnapp.predictions:
        return letzte
    ausgabe = []
    for eintrag in schnapp.predictions:
        token = engine.thalamus.decode_token(eintrag[0])
        if not token or token.startswith("?"):
            continue
        ausgabe.append((token, float(eintrag[2])))
    return ausgabe or letzte


class FensterWaage:
    """Die eigene Wahrheits-Waage: was tat das Haus im Fenster danach?

    Eine Beratung öffnet ein Fenster von ``fenster_s`` Sekunden
    EREIGNISZEIT. Die Wahrheit ist die erste Option, deren (Entität,
    Zustand) in diesem Fenster wirklich eintritt — sonst „nichts tun"
    (id 0). Die Grenze ist genau: das Ereignis bei ``zeit_s + fenster_s``
    zählt noch, danach nicht mehr (dieselbe Form wie der Nachhall des
    Organs: ``zeit - b["zeit"] > fenster_s`` schließt).

    Die zweite Aufgabe: je Wähler (Modell, engine, nichts, zufall …) die
    Treffer zählen, damit die Abschaltprobe auf DENSELBEN Beratungen
    steht.
    """

    def __init__(self, fenster_s: float):
        self.fenster_s = fenster_s
        self.offen: List[dict] = []
        self.bilanz: Dict[str, List[int]] = {}

    def oeffne(self, zeit_s: float, menue: list, waehler: Dict[str, int],
               gestrichen: Sequence[int]) -> None:
        self.offen.append({
            "zeit_s": zeit_s,
            "optionen": [{"id": o["id"], "entity_id": o.get("entity_id"),
                          "zustand": o.get("zustand")}
                         for o in menue if o["id"] != NICHTS],
            "waehler": dict(waehler),
            "gestrichen": list(gestrichen),
            "wahrheit": None,
        })

    def beobachte(self, entity_id, zustand, jetzt_s: float) -> None:
        for eintrag in self.offen:
            if jetzt_s - eintrag["zeit_s"] > self.fenster_s:
                continue          # das Fenster ist zu — dieses Ereignis zählt nicht
            if eintrag["wahrheit"] is not None:
                continue
            for option in eintrag["optionen"]:
                if option["entity_id"] == entity_id \
                        and option["zustand"] == zustand:
                    eintrag["wahrheit"] = option["id"]
                    break

    def schliesse(self, jetzt_s: float) -> List[dict]:
        fertig = [e for e in self.offen
                  if jetzt_s - e["zeit_s"] > self.fenster_s]
        self.offen = [e for e in self.offen
                      if jetzt_s - e["zeit_s"] <= self.fenster_s]
        for eintrag in fertig:
            self._verbuche(eintrag)
        return fertig

    def schliesse_alles(self) -> List[dict]:
        fertig, self.offen = self.offen, []
        for eintrag in fertig:
            self._verbuche(eintrag)
        return fertig

    def _verbuche(self, eintrag: dict) -> None:
        wahrheit = eintrag["wahrheit"] if eintrag["wahrheit"] is not None \
            else NICHTS
        for wer, wahl in eintrag["waehler"].items():
            treffer, n = self.bilanz.setdefault(wer, [0, 0])
            self.bilanz[wer] = [treffer + (1 if wahl == wahrheit else 0), n + 1]

    @property
    def quoten(self) -> Dict[str, List[int]]:
        return dict(self.bilanz)


def ueberlagere(vorhersagen: Sequence, wahl_token: Optional[str]) -> List:
    """Die Wahl nach vorn — ohne die Konfidenzen der Engine zu erfinden.

    Ohne Wahl (oder wenn die Wahl schon die erste Stelle ist) bleibt die
    Liste unberührt. Sonst rückt das gewählte Token an die erste Stelle;
    seine Konfidenz bleibt die der Engine (0.0, falls sie es gar nicht
    führt — dann war es auch keine Engine-Vorhersage).
    """
    if not wahl_token:
        return list(vorhersagen)
    if vorhersagen and vorhersagen[0][0] == wahl_token:
        return list(vorhersagen)
    kopf, rest = None, []
    for token, konfidenz in vorhersagen:
        if kopf is None and token == wahl_token:
            kopf = (token, konfidenz)
            continue
        rest.append((token, konfidenz))
    if kopf is None:
        kopf = (wahl_token, 0.0)
    return [kopf] + rest


# ---------------------------------------------------------------------------
# Die Schleife — ein rollierender Ursprung
# ---------------------------------------------------------------------------

def messe_ursprung(ereignisse: Sequence, ziele: Sequence[str],
                   train_wochen: int, berater=None, *,
                   engine, gegner_schar: Optional[dict] = None,
                   uhr=None,
                   anlass_fn: Optional[Callable] = None,
                   amygdala=None, fenster_s: float = STANDARD_FENSTER_S,
                   quelle: str = "", haus_typ: str = "",
                   nachhall: Optional[Nachhall] = None,
                   zufallsgegner=None) -> UrsprungsTafel:
    """Ein Ursprung: k Wochen lernen, Woche k+1 bewerten.

    ``ereignisse`` brauchen ``ts``, ``entity``, ``zustand``, ``alt``;
    ``ziele`` ist der Token-Strom (Länge wie ``ereignisse``).
    ``anlass_fn`` ist standardmäßig der echte ``anlass`` des Organs.
    """
    if train_wochen < 1:
        raise ValueError("train_wochen mindestens 1")
    if not ereignisse:
        raise ValueError("Leere Spur — nichts zu messen.")
    anlass_fn = anlass_fn or organ_anlass
    nachhall = nachhall if nachhall is not None else Nachhall(fenster_s=fenster_s)

    start = ereignisse[0].ts
    grenze_train = start + timedelta(days=7 * train_wochen)
    test_ende = grenze_train + timedelta(days=7)
    if uhr is not None:
        uhr.stelle(start)      # die Uhr steht auf dem ersten Ereignis ...
        uhr.an()               # ... und zwar BEVOR die Engine etwas rechnet

    tafel = UrsprungsTafel(quelle=quelle, haus_typ=haus_typ,
                           train_wochen=train_wochen)
    for name in ("Engine", "Engine+Cortex"):
        tafel.systeme[name] = TafelZeile(name)
    for name in (gegner_schar or {}):
        tafel.systeme[name] = TafelZeile(name)

    letzte_engine: List = []
    letzte_beratung = float("-inf")
    letzte_wahl: Optional[str] = None
    offen = None            # (Option der offenen Beratung) für die Sofort-Wahrheit
    fenster = FensterWaage(fenster_s)

    for i, ereignis in enumerate(ereignisse):
        if ereignis.ts >= test_ende:
            break
        im_test = i > 0 and grenze_train <= ereignis.ts < test_ende

        # 1) Bewerten — die Vorhersage entstand aus dem Stand von i-1.
        if im_test:
            ziel = ziele[i]
            _bilanz(tafel.systeme["Engine"], letzte_engine, ziel)
            _bilanz(tafel.systeme["Engine+Cortex"],
                    ueberlagere(letzte_engine, letzte_wahl), ziel)
            for name, gegner in (gegner_schar or {}).items():
                _bilanz(tafel.systeme[name],
                        gegner.vorhersage(ereignisse[i - 1].ts, 3), ziel)
            if offen is not None:
                option = offen
                if option.get("entity_id") == ereignis.entity \
                        and option.get("zustand") == ereignis.zustand:
                    tafel.aenderungen_richtig_sofort += 1
                offen = None
            letzte_wahl = None      # die Wahl zielte auf dieses Ereignis

        # 2) Lernen — jedes Ereignis, auch im Training.
        if uhr is not None:
            uhr.stelle(ereignis.ts)
        schnapp = engine.observe({
            "entity_id": ereignis.entity,
            "new_state": ereignis.zustand,
            "old_state": ereignis.alt,
            "timestamp": ereignis.ts,
        })
        letzte_engine = _engine_vorhersage(schnapp, engine, letzte_engine)
        for name, gegner in (gegner_schar or {}).items():
            # Die Gegner lernen mit (B1 braucht den Zeitstempel) — sonst
            # stünden ihre Zeilen als untrainierte Strohmänner in der Tafel.
            if name == "B1":
                gegner.beobachte(ziele[i], ereignis.ts)
            else:
                gegner.beobachte(ziele[i])

        # 3) Die eigene Fenster-Waage: was tat das Haus nach der Beratung?
        jetzt = (ereignis.ts - start).total_seconds()
        nachhall.beobachte(ereignis.entity, ereignis.zustand, jetzt)
        fenster.beobachte(ereignis.entity, ereignis.zustand, jetzt)
        for eintrag in fenster.schliesse(jetzt):
            wahrheit = eintrag["wahrheit"] if eintrag["wahrheit"] is not None \
                else NICHTS
            for gestrichen in eintrag["gestrichen"]:
                if gestrichen == wahrheit:
                    tafel.vetos_richtig_verhindert += 1
                else:
                    tafel.vetos_falsch_verhindert += 1
        nachhall.abschliessen(jetzt)

        # 4) Anlass und Beratung (nur Testwoche).
        if berater is None or not (grenze_train <= ereignis.ts < test_ende):
            continue
        grund = anlass_fn(i, schnapp.predictions, bool(schnapp.anomaly),
                          jetzt, letzte_beratung)
        if not grund:
            continue
        tafel.anlaesse[grund] = tafel.anlaesse.get(grund, 0) + 1
        menue = baue_menue(schnapp.predictions, engine.thalamus, amygdala)
        tafel.menues["mit_menue" if len(menue) >= 2 else "leer"] = \
            tafel.menues.get("mit_menue" if len(menue) >= 2 else "leer", 0) + 1
        letzte_beratung = jetzt       # wie Cortex.consult: sofort gesetzt
        beratung = berater.berate(jetzt_s=jetzt, anlass=grund, menue=menue,
                                  zeit_ts=ereignis.ts)
        if len(menue) < 2:
            continue

        tafel.beratungen.append(beratung)
        if beratung.wahl != 1:
            tafel.aenderungen += 1
            if beratung.wahl == NICHTS:
                tafel.davon_nichts += 1
        letzte_wahl = beratung.wahl_token
        option = beratung.wahl_option
        if beratung.wahl != NICHTS and option is not None:
            folgt = next((e for e in ereignisse[i + 1:i + 2]), None)
            if folgt is None or not (grenze_train <= folgt.ts < test_ende):
                tafel.aenderungen_ohne_folge += 1
            offen = option

        # Die Stimmen für die Bilanz: echte Stimmen + Zufallsgegner
        # (der Gegner stimmt mit, ohne mitzuzählen — die Mehrheit ist
        # längst entschieden).
        stimmen = list(beratung.stimmen)
        zufall_wahl = None
        if zufallsgegner is not None:
            zufall = zufallsgegner.berate(jetzt_s=jetzt, anlass=grund,
                                          menue=menue, zeit_ts=ereignis.ts)
            zufall_wahl = zufall.wahl
            stimmen = stimmen + [{
                "agent": zufallsgegner.name, "wahl": zufall.wahl,
                "grund": "Zufallswahl (Abschaltprobe)", "sicherheit": 0,
                "veto": [], "gueltig": True}]
        nachhall.merke(jetzt, menue, stimmen, beratung.entscheidung)

        waehler = {s["agent"]: int(s["wahl"]) for s in stimmen
                   if s.get("gueltig")}
        waehler["konsens"] = beratung.wahl
        waehler["engine"] = 1 if len(menue) > 1 else NICHTS
        waehler["nichts"] = NICHTS
        fenster.oeffne(jetzt, menue, waehler,
                       beratung.entscheidung.get("gestrichen", []))

    # Nach dem Testfenster: offene Fenster schließen (Wahrheit „nichts").
    for eintrag in fenster.schliesse_alles():
        wahrheit = eintrag["wahrheit"] if eintrag["wahrheit"] is not None \
            else NICHTS
        for gestrichen in eintrag["gestrichen"]:
            if gestrichen == wahrheit:
                tafel.vetos_richtig_verhindert += 1
            else:
                tafel.vetos_falsch_verhindert += 1
    ende_s = (ereignisse[-1].ts - start).total_seconds() + fenster_s + 1.0
    nachhall.abschliessen(ende_s)

    if uhr is not None:
        uhr.aus()          # die Wanduhr kommt zurück
    tafel.test_ereignisse = sum(
        1 for e in ereignisse if grenze_train <= e.ts < test_ende)
    tafel.fenster = fenster.quoten
    tafel.fenster_organ = nachhall.quoten()
    _kosten(tafel)
    return tafel


def _kosten(tafel: UrsprungsTafel) -> None:
    dauern = [b.dauer_s for b in tafel.beratungen]
    aufrufe = sum(len(b.tokens_antwort) for b in tafel.beratungen)
    tafel.kosten = {
        "beratungen": len(tafel.beratungen),
        "modellaufrufe": aufrufe,
        "dauer_summe_s": round(sum(dauern), 3),
        "dauer_mittel_s": round(sum(dauern) / len(dauern), 3) if dauern else 0.0,
        "tokens_prompt": sum(sum(b.tokens_prompt) for b in tafel.beratungen),
        "tokens_antwort": sum(sum(b.tokens_antwort) for b in tafel.beratungen),
        "ladungen_s": sum(sum(b.ladungen) for b in tafel.beratungen),
    }


# ---------------------------------------------------------------------------
# Der Aufbau aus dem Kern (Checkout) — Sim und CASAS
# ---------------------------------------------------------------------------

@dataclass
class Aufbau:
    spur: object
    ereignisse: Sequence
    ziele: Sequence[str]
    engine: object
    gegner: dict
    uhr: object
    amygdala: object


def kern_pfade(kern: Path) -> Path:
    """Legt den gepinnten Kern-Checkout vor alles andere auf den Pfad."""
    kern = Path(kern)
    if not (kern / "benchmarks" / "spur" / "messstand.py").exists():
        raise FileNotFoundError(
            f"Kern-Checkout ohne Messstand: {kern} — --kern/KONTINUUM_KERN "
            "auf einen kontinuum-core-Checkout setzen (Engine und Messstand "
            "aus EINEM Stand; die Module benchmarks.spur.* sind nicht Teil "
            "des PyPI-Pakets).")
    for pfad in (str(kern), str(kern / "src")):
        while pfad in sys.path:
            sys.path.remove(pfad)
        sys.path.insert(0, pfad)
    return kern


def _baue_engine(entitaeten):
    from kontinuum_core import KontinuumEngine
    from benchmarks.spur.messstand import registriere_engine
    engine = KontinuumEngine()
    # Determinismus wie im Messstand: der Traum-Replay sampelt mit dem
    # globalen Zufall — feste Saat, sonst hängt jede Zahl am Vorlauf.
    engine.sleep_consolidation._rng = random.Random(0)
    registriere_engine(engine, entitaeten)
    return engine


def _baue_gegner(ziele: Sequence[str]) -> dict:
    from benchmarks.spur.gegner import gegner
    return gegner(sorted(set(ziele)))


def aufbau_sim(haus_typ: str, saat: int, tage: int, train_wochen: int,
               kern, mit_leck_tag: bool = True) -> Aufbau:
    kern_pfade(Path(kern))
    from benchmarks.spur.simulator import simuliere
    from benchmarks.spur.spur import tokenisieren
    from benchmarks.spur.zeitgeber import Zeitgeber
    sim = simuliere(haus_typ=haus_typ, tage=tage, saat=saat,
                    mit_leck_tag=mit_leck_tag)
    spur = sim.spur
    ziele = tokenisieren(spur)
    engine = _baue_engine(spur.kopf.entitaeten)
    return Aufbau(spur=spur, ereignisse=spur.ereignisse, ziele=ziele,
                  engine=engine, gegner=_baue_gegner(ziele),
                  uhr=Zeitgeber(),
                  amygdala=getattr(engine.prefrontal_cortex, "amygdala", None))


def aufbau_casas(pfad, kern) -> Aufbau:
    kern_pfade(Path(kern))
    from benchmarks.spur.spur import lies_spur, tokenisieren
    from benchmarks.spur.zeitgeber import Zeitgeber
    spur = lies_spur(pfad)
    ziele = tokenisieren(spur)
    engine = _baue_engine(spur.kopf.entitaeten)
    return Aufbau(spur=spur, ereignisse=spur.ereignisse, ziele=ziele,
                  engine=engine, gegner=_baue_gegner(ziele),
                  uhr=Zeitgeber(),
                  amygdala=getattr(engine.prefrontal_cortex, "amygdala", None))


# ---------------------------------------------------------------------------
# Tafel-Ausgabe
# ---------------------------------------------------------------------------

def tafel_json(tafel: UrsprungsTafel) -> dict:
    def quote(paar):
        treffer, n = paar
        return {"treffer": treffer, "n": n,
                "quote": round(treffer / n, 4) if n else None}

    return {
        "quelle": tafel.quelle,
        "haus_typ": tafel.haus_typ,
        "train_wochen": tafel.train_wochen,
        "berater": tafel.berater,
        "test_ereignisse": tafel.test_ereignisse,
        "systeme": {
            name: {"gesamt": z.gesamt, "top1": z.top1, "top3": z.top3,
                   "top1_prozent": (round(z.top1_prozent, 2)
                                    if z.top1_prozent is not None else None),
                   "top3_prozent": (round(z.top3_prozent, 2)
                                    if z.top3_prozent is not None else None)}
            for name, z in tafel.systeme.items()},
        "anlaesse": dict(tafel.anlaesse),
        "menues": dict(tafel.menues),
        "beratungen": len(tafel.beratungen),
        "beratungen_je_1000": round(tafel.beratungen_je_1000, 2),
        "aenderungen": tafel.aenderungen,
        "davon_nichts": tafel.davon_nichts,
        "aenderungen_ohne_folge": tafel.aenderungen_ohne_folge,
        "aenderungen_richtig_sofort": tafel.aenderungen_richtig_sofort,
        "vetos_richtig_verhindert": tafel.vetos_richtig_verhindert,
        "vetos_falsch_verhindert": tafel.vetos_falsch_verhindert,
        "sofort": {wer: quote(paar) for wer, paar in tafel.sofort.items()},
        "fenster": {wer: quote(paar) for wer, paar in tafel.fenster.items()},
        "fenster_organ": dict(tafel.fenster_organ),
        "kosten": dict(tafel.kosten),
    }


def tafel_bericht(tafeln: Sequence[UrsprungsTafel]) -> str:
    zeilen = ["CORTEX-TAFEL — das Organ am Messstand (ha-kontinuum #3)",
              "=" * 72]
    for tafel in tafeln:
        zeilen.append(f"{tafel.quelle} (k={tafel.train_wochen}, "
                      f"{tafel.test_ereignisse} Testereignisse, "
                      f"Berater {tafel.berater or '—'})")
        for name, z in tafel.systeme.items():
            p1 = f"{z.top1_prozent:5.1f}" if z.top1_prozent is not None else "  —  "
            p3 = f"{z.top3_prozent:5.1f}" if z.top3_prozent is not None else "  —  "
            zeilen.append(f"    {name:16s} Top-1 {p1} %  Top-3 {p3} %  "
                          f"(n={z.gesamt})")
        zeilen.append(f"    Anlässe {dict(tafel.anlaesse)} · Menüs "
                      f"{dict(tafel.menues)} · Beratungen "
                      f"{len(tafel.beratungen)} "
                      f"({tafel.beratungen_je_1000:.1f} je 1000)")
        zeilen.append(f"    Änderungen {tafel.aenderungen} "
                      f"(davon nichts tun: {tafel.davon_nichts}), "
                      f"sofort richtig {tafel.aenderungen_richtig_sofort}, "
                      f"ohne Folge {tafel.aenderungen_ohne_folge}")
        zeilen.append(f"    Vetos: falsche verhindert "
                      f"{tafel.vetos_falsch_verhindert}, richtige verhindert "
                      f"{tafel.vetos_richtig_verhindert}")
        for wer, paar in sorted(tafel.fenster.items()):
            treffer, n = paar
            quote = f"{100.0 * treffer / n:5.1f}" if n else "  —  "
            organ = tafel.fenster_organ.get(wer)
            vergleich = (f"  (Organ-Waage {100.0 * organ:5.1f} %)"
                         if organ is not None else "")
            zeilen.append(f"    Fenster  {wer:12s} {quote} %  (n={n})"
                          f"{vergleich}")
        if tafel.kosten:
            k = tafel.kosten
            zeilen.append(f"    Kosten: {k.get('modellaufrufe', 0)} Aufrufe, "
                          f"{k.get('dauer_summe_s', 0):.1f} s, "
                          f"{k.get('tokens_prompt', 0)} Prompt-Tokens, "
                          f"{k.get('tokens_antwort', 0)} Antwort-Tokens")
        zeilen.append("-" * 72)
    return "\n".join(zeilen)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _berater_bauen(args, aufbau):
    brain = {"thalamus": aufbau.engine.thalamus,
             "_last_predictions": [],
             "prefrontal": aufbau.engine.prefrontal_cortex}
    if args.trocken:
        return SkriptBerater([1] * 10_000), "trocken (Drehbuch)"
    if args.zufall is not None:
        return ZufallsBerater(saat=args.zufall), f"zufall/saat={args.zufall}"
    berater = OrganBerater(brain, agenten=tuple(args.agenten.split(",")),
                           modell=args.modell, url=args.url,
                           zeitlimit=args.zeitlimit)
    return berater, f"organ/{args.modell} ({args.agenten})"


def _ein_lauf(args, aufbau, saat: int, ursprung: int) -> UrsprungsTafel:
    berater, label = _berater_bauen(args, aufbau)
    # Der Zufallsgegner (Abschaltprobe) läuft in JEDEM Lauf mit — auch im
    # Organ-Lauf; er stimmt in der Bilanz mit, ohne mitzuzählen.
    gegner_zufall = ZufallsBerater(saat=saat * 1000 + ursprung)
    tafel = messe_ursprung(
        aufbau.ereignisse, aufbau.ziele, ursprung, berater,
        engine=aufbau.engine, gegner_schar=aufbau.gegner,
        uhr=aufbau.uhr, amygdala=aufbau.amygdala,
        quelle=aufbau.spur.kopf.haus, haus_typ=aufbau.spur.kopf.haus_typ,
        zufallsgegner=gegner_zufall)
    tafel.berater = label
    return tafel


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="cortex_tafel")
    p.add_argument("--kern", default=None,
                   help="kontinuum-core-Checkout (Engine UND Messstand)")
    p.add_argument("--sim", choices=("klassisch", "geraete"), default=None)
    p.add_argument("--saaten", type=int, nargs="+", default=[1])
    p.add_argument("--tage", type=int, default=56)
    p.add_argument("--ursprunge", type=int, nargs="+", default=[4])
    p.add_argument("--casas", default=None,
                   help="Ordner mit <haus>.jsonl (CASAS-Spuren)")
    p.add_argument("--haus", default=None, help="ein Haus aus --casas")
    p.add_argument("--modell", default="llama3.2:1b")
    p.add_argument("--agenten", default=",".join(STANDARD_AGENTEN))
    p.add_argument("--url", default=STANDARD_URL)
    p.add_argument("--zeitlimit", type=float, default=STANDARD_ZEITLIMIT)
    p.add_argument("--trocken", action="store_true",
                   help="Drehbuch statt Modell (kein Ollama nötig)")
    p.add_argument("--zufall", type=int, default=None,
                   help="nur der Zufallsgegner (Abschaltprobe)")
    p.add_argument("--ziel", default="build/cortex")
    args = p.parse_args(argv)

    kern = args.kern or __import__("os").environ.get("KONTINUUM_KERN") \
        or str(Path(__file__).resolve().parent.parent.parent / "kontinuum-core")
    if args.sim is None and args.casas is None:
        p.error("--sim oder --casas angeben")
    import os
    os.environ.setdefault("TZ", "Europe/Berlin")
    if hasattr(time, "tzset"):
        time.tzset()

    ziel = Path(args.ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    tafeln: List[UrsprungsTafel] = []

    if args.sim:
        for saat in args.saaten:
            for ursprung in args.ursprunge:
                beginn = time.time()
                aufbau = aufbau_sim(args.sim, saat, args.tage, ursprung, kern)
                tafel = _ein_lauf(args, aufbau, saat, ursprung)
                tafeln.append(tafel)
                print(f"[{tafel.quelle} k={ursprung}] "
                      f"Beratungen {len(tafel.beratungen)}, "
                      f"Engine Top-1 {tafel.systeme['Engine'].top1_prozent and round(tafel.systeme['Engine'].top1_prozent, 1)} %, "
                      f"{time.time() - beginn:.0f} s", flush=True)
                _schreibe(ziel, tafel, args, saat, ursprung)
    if args.casas:
        ordner = Path(args.casas)
        haeuser = [args.haus] if args.haus else \
            [p.name[:-6] for p in sorted(ordner.glob("*.jsonl"))]
        for haus in haeuser:
            for ursprung in args.ursprunge:
                beginn = time.time()
                aufbau = aufbau_casas(ordner / f"{haus}.jsonl", kern)
                tafel = _ein_lauf(args, aufbau, 0, ursprung)
                # Identität ist der Dateistamm, nicht das Haus im Kopf der
                # Spur: aruba.jsonl und aruba_3w.jsonl tragen beide „aruba" —
                # zwei Läufe mit gleichem k hätten sich sonst überschrieben.
                tafel.quelle = f"casas-{haus}"
                tafeln.append(tafel)
                print(f"[{tafel.quelle} k={ursprung}] "
                      f"Beratungen {len(tafel.beratungen)}, "
                      f"Menüs {dict(tafel.menues)}, "
                      f"{time.time() - beginn:.0f} s", flush=True)
                _schreibe(ziel, tafel, args, 0, ursprung)

    bericht = tafel_bericht(tafeln)
    (ziel / "cortex-tafel.txt").write_text(bericht, encoding="utf-8")
    print(bericht)
    return 0


def _schreibe(ziel: Path, tafel: UrsprungsTafel, args, saat: int,
              ursprung: int) -> None:
    name = f"cortex-{tafel.quelle}-k{ursprung}"
    if args.modell and not args.trocken and args.zufall is None:
        name += "-" + args.modell.replace(":", "_").replace("/", "_")
    elif args.zufall is not None:
        name += f"-zufall{args.zufall}"
    else:
        name += "-trocken"
    (ziel / f"{name}.json").write_text(
        json.dumps(tafel_json(tafel), ensure_ascii=False, indent=1),
        encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
