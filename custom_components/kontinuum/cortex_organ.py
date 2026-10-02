"""
KONTINUUM – Cortex als Organ (Stufe 3a)

Bisher hing das Sprachmodell als Dekor am Gehirn: Es wurde nur auf Knopfdruck
gefragt, bekam eine offene Frage („Was schlägst du vor?“) und durfte jede
beliebige Entität nennen. Die erste echte Beratung mit einem lokalen Modell
endete im Konsens, einen Tür-Schalter zu betätigen, „um nachzusehen“.

Dieses Modul macht daraus ein Organ mit vier Regeln:

1. **Anlass statt Knopf.** Gefragt wird nur, wenn die Engine selbst unsicher
   ist (knappe Marge zwischen den ersten Vorhersagen) oder überrascht ist
   (Anomalie) – und nie im Kaltstart.
2. **Wählen statt Erfinden.** Das Modell bekommt ein Menü aus echten
   (Dienst, Entität)-Paaren, die die Engine selbst vorhergesagt hat. Option 0
   heißt „nichts tun“. Bei Ollama erzwingt ein JSON-Schema mit ``enum``, dass
   nur eine Nummer aus dem Menü zurückkommen kann.
3. **Nichts tun ist die Grundstellung.** Eine echte Option gewinnt nur mit
   absoluter Mehrheit der Stimmen; ein Veto der Sicherheit streicht Optionen,
   bevor gezählt wird. Es gibt keine Diskussionsrunde, die Gruppendenken
   erzeugt.
4. **Lernen aus dem Ergebnis.** Jede Beratung bekommt ein Zeitfenster. Tut der
   Mensch darin genau das, was eine Option beschreibt, ist das die Wahrheit;
   tut er nichts davon, war „nichts tun“ richtig. So entsteht je Agent eine
   Trefferquote – neben zwei Gegnern, die immer gleich wählen: „engine“ (immer
   Option 1, die Top-Vorhersage) und „nichts“ (immer 0). Ein Modell ist nur
   dann ein Gewinn, wenn es beide schlägt.

Alles hier ist reines Python ohne Home Assistant, damit es sich ohne HA testen
lässt.
"""

from __future__ import annotations

import json
import re

from kontinuum_core.prefrontal_cortex import ACTIONABLE_SEMANTICS, STATE_TO_SERVICE

NICHTS = 0

# Unter so vielen gelernten Ereignissen ist jede Vorhersage Zufall – dort zu
# fragen, erzeugt nur erfundene Vorschläge.
MIN_EREIGNISSE = 300
# Mindestabstand zwischen zwei Beratungen aus eigenem Anlass. Ein lokales 8B-
# Modell braucht je Agent mehrere Sekunden GPU – das soll selten passieren.
ABSTAND_S = 900
# „Knapp“: Die ersten beiden Vorhersagen liegen näher als das beieinander …
MARGE = 0.10
# … und die erste ist weder sicher noch bedeutungslos.
UNSICHER_VON, UNSICHER_BIS = 0.30, 0.75
MAX_OPTIONEN = 5
# So lange wird nach einer Beratung beobachtet, was der Mensch tut.
FENSTER_S = 900

# Thalamus-Zustand → Home-Assistant-Zustand, wo sie sich unterscheiden.
_HA_ZUSTAND = {"heating": "heat", "cooling": "cool"}


def baue_menue(predictions, thalamus, amygdala=None, max_optionen=MAX_OPTIONEN):
    """Baut das Menü aus den Vorhersagen der Engine.

    Jede Option ist ein Paar (Dienst, Entität), das die Engine selbst
    vorhergesagt hat und das sich ausführen ließe. Option 0 ist immer
    „nichts tun“. Was die Amygdala mit VETO belegt (Schlösser, Alarm), kommt
    gar nicht erst ins Menü.
    """
    menue = [{"id": NICHTS, "text": "nichts tun"}]
    gesehen = set()
    for pred in predictions or []:
        token_id, _prob, conf = pred[0], pred[1], pred[2]
        token = thalamus.decode_token(token_id)
        teile = token.split(".")
        if len(teile) != 3:
            continue
        raum, semantik, zustand = teile
        if semantik not in ACTIONABLE_SEMANTICS:
            continue
        dienst = STATE_TO_SERVICE.get(semantik, {}).get(zustand)
        if not dienst:
            continue
        if amygdala is not None:
            urteil = amygdala.assess(token, semantik, raum, zustand, conf)
            if urteil.get("decision") == "VETO":
                continue
        kandidaten = thalamus.resolve_entities(token)
        if not kandidaten:
            continue
        entitaet = kandidaten[0]
        schluessel = (entitaet, zustand)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        menue.append({
            "id": len(menue),
            "aktion": f"{semantik}.{dienst}",
            "entity_id": entitaet,
            "zustand": zustand,
            "token": token,
            "sicherheit": round(float(conf), 3),
            "text": f"{entitaet} → {zustand} (Engine: {conf:.0%} sicher)",
        })
        if len(menue) > max_optionen:
            break
    return menue


def anlass(total_events, predictions, anomalie, jetzt, letzte_beratung,
           min_ereignisse=MIN_EREIGNISSE, abstand_s=ABSTAND_S, marge=MARGE):
    """Gibt den Grund für eine Beratung zurück – oder None, wenn keiner da ist."""
    if total_events < min_ereignisse:
        return None
    if jetzt - letzte_beratung < abstand_s:
        return None
    if anomalie:
        return "anomalie"
    if not predictions:
        return None
    erste = float(predictions[0][2])
    zweite = float(predictions[1][2]) if len(predictions) > 1 else 0.0
    if UNSICHER_VON <= erste <= UNSICHER_BIS and erste - zweite < marge:
        return "knapp"
    return None


def menue_text(menue):
    zeilen = [f"  {o['id']}: {o['text']}" for o in menue]
    return "\n".join(zeilen)


def antwort_schema(menue, mit_veto=False):
    """JSON-Schema für Ollama: ``wahl`` kann nur eine Menü-Nummer sein."""
    ids = [o["id"] for o in menue]
    eigenschaften = {
        "wahl": {"type": "integer", "enum": ids},
        "grund": {"type": "string"},
        "sicherheit": {"type": "integer", "minimum": 0, "maximum": 100},
    }
    pflicht = ["wahl", "grund", "sicherheit"]
    if mit_veto:
        echte = [i for i in ids if i != NICHTS]
        eigenschaften["veto"] = {"type": "array",
                                 "items": {"type": "integer", "enum": echte or [NICHTS]}}
        pflicht.append("veto")
    return {"type": "object", "properties": eigenschaften, "required": pflicht}


def _als_json(roh):
    if isinstance(roh, dict):
        return roh
    text = str(roh or "")
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    treffer = re.search(r"\{.*\}", text, re.S)
    if treffer:
        try:
            return json.loads(treffer.group(0))
        except (ValueError, TypeError):
            pass
    return {}


def lies_wahl(roh, menue, agent=""):
    """Liest eine Antwort. Alles, was nicht im Menü steht, wird zu „nichts tun“."""
    daten = _als_json(roh)
    ids = {o["id"] for o in menue}
    try:
        wahl = int(daten.get("wahl", NICHTS))
    except (TypeError, ValueError):
        wahl = NICHTS
    gueltig = wahl in ids
    if not gueltig:
        wahl = NICHTS
    try:
        sicherheit = max(0, min(100, int(daten.get("sicherheit", 0))))
    except (TypeError, ValueError):
        sicherheit = 0
    veto = []
    for v in daten.get("veto") or []:
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        if v in ids and v != NICHTS:
            veto.append(v)
    return {
        "agent": agent,
        "wahl": wahl,
        "grund": str(daten.get("grund", ""))[:300],
        "sicherheit": sicherheit,
        "veto": veto,
        "gueltig": gueltig and bool(daten),
    }


def entscheide(stimmen, menue):
    """Zählt die Stimmen. Nichts tun gewinnt, solange keine Option eine
    absolute Mehrheit hat; gestrichene Optionen zählen gar nicht."""
    gestrichen = {v for s in stimmen for v in s.get("veto", [])}
    waehlende = [s for s in stimmen if s.get("gueltig")]
    if not waehlende:
        return {"wahl": NICHTS, "grund": "keine gültige Stimme", "gestrichen": sorted(gestrichen)}
    zaehlung = {}
    for s in waehlende:
        w = s["wahl"]
        if w in gestrichen:
            w = NICHTS
        zaehlung[w] = zaehlung.get(w, 0) + 1
    beste, anzahl = max(zaehlung.items(), key=lambda kv: (kv[1], kv[0] == NICHTS))
    if beste != NICHTS and anzahl * 2 > len(waehlende):
        option = next(o for o in menue if o["id"] == beste)
        return {
            "wahl": beste,
            "grund": f"Mehrheit {anzahl}/{len(waehlende)} für {option['text']}",
            "gestrichen": sorted(gestrichen),
        }
    grund = "keine Mehrheit für eine Aktion" if beste != NICHTS else \
        f"Mehrheit {anzahl}/{len(waehlende)} für nichts tun"
    if gestrichen:
        grund += f"; Veto gegen {sorted(gestrichen)}"
    return {"wahl": NICHTS, "grund": grund, "gestrichen": sorted(gestrichen)}


class Nachhall:
    """Merkt sich jede Beratung und prüft im Fenster danach, was der Mensch tat."""

    def __init__(self, fenster_s=FENSTER_S):
        self.fenster_s = fenster_s
        self.offen = []
        self.bilanz = {}

    def merke(self, zeit, menue, stimmen, entscheidung):
        waehler = {s["agent"]: s["wahl"] for s in stimmen if s.get("gueltig")}
        waehler["konsens"] = entscheidung["wahl"]
        waehler["engine"] = 1 if len(menue) > 1 else NICHTS
        waehler["nichts"] = NICHTS
        self.offen.append({
            "zeit": zeit,
            "optionen": [{"id": o["id"], "entity_id": o["entity_id"],
                          "zustand": o["zustand"]} for o in menue if o["id"] != NICHTS],
            "waehler": waehler,
            "wahrheit": None,
        })

    def beobachte(self, entity_id, zustand, zeit):
        for b in self.offen:
            if b["wahrheit"] is not None or zeit - b["zeit"] > self.fenster_s:
                continue
            for o in b["optionen"]:
                erwartet = _HA_ZUSTAND.get(o["zustand"], o["zustand"])
                if o["entity_id"] == entity_id and zustand in (o["zustand"], erwartet):
                    b["wahrheit"] = o["id"]
                    break

    def abschliessen(self, zeit):
        fertig = [b for b in self.offen if zeit - b["zeit"] > self.fenster_s]
        self.offen = [b for b in self.offen if zeit - b["zeit"] <= self.fenster_s]
        for b in fertig:
            wahrheit = b["wahrheit"] if b["wahrheit"] is not None else NICHTS
            for wer, wahl in b["waehler"].items():
                eintrag = self.bilanz.setdefault(wer, {"treffer": 0, "n": 0})
                eintrag["n"] += 1
                if wahl == wahrheit:
                    eintrag["treffer"] += 1
        return len(fertig)

    def quoten(self):
        return {wer: round(e["treffer"] / e["n"], 3) if e["n"] else None
                for wer, e in self.bilanz.items()}

    def to_dict(self):
        return {"offen": self.offen, "bilanz": self.bilanz}

    def from_dict(self, daten):
        self.offen = list((daten or {}).get("offen", []))
        self.bilanz = dict((daten or {}).get("bilanz", {}))

