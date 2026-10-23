"""Der Berater: das Cortex-Organ am Messstand (ha-kontinuum #3).

Diese Datei baut KEIN zweites Organ. Gemessen wird das echte:
`baue_menue`, `anlass`, `lies_wahl`, `entscheide`, `Nachhall` kommen aus
`custom_components.kontinuum.cortex_organ`; jeder Modellaufruf geht über den
echten `CortexAgent.waehle` (und damit über `_call_ollama` — derselbe
Nutzlast-Aufbau, dasselbe Schema, dieselbe Veto-Regel, dieselbe
Zeitüberschreitung ohne Wiederholung).

Warum nicht einfach `Cortex.consult`? Weil `consult` seine Abstände an der
WANDUHR misst (`MIN_INTERVAL = 30`, `letzte_beratung = time.time()`). Im
Replay liegen Beratungen Millisekunden auseinander — `consult` würde nach
der ersten Beratung fast jede weitere verweigern. Der Berater ruft deshalb
dieselben Teile in derselben Reihenfolge auf; die Frage selbst ist wörtlich
die des Organs (`frage_fuer`, gepinnt durch einen Test gegen `consult`).

Kosten: `KostenSpion` hängt sich vor die aiohttp-Sitzung und liest aus der
Antwort, was Ollama ohnehin mitschickt (prompt_eval_count, eval_count,
total_duration, load_duration). Der Transport bleibt der echte — kein
zweiter HTTP-Weg.
"""
from __future__ import annotations

import asyncio
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, Sequence

from custom_components.kontinuum.cortex import CortexAgent, organ_prompt
from custom_components.kontinuum.cortex_organ import (
    NICHTS,
    entscheide,
    lies_wahl,
    menue_text,
)
from kontinuum_core import build_llm_context, render_llm_context

#: Ollama liegt im Haus auf demselben Blech (nur lokal, nie ein Cloud-Dienst).
STANDARD_URL = "http://127.0.0.1:11434"
#: Dasselbe Zeitlimit wie `Cortex.zeitlimit` (ohne Wiederholung).
STANDARD_ZEITLIMIT = 90.0
#: Ein Agent je Modellgröße — die Größe ist der Parameter der Tafel.
STANDARD_AGENTEN = ("comfort",)


# ---------------------------------------------------------------------------
# Die Frage — wörtlich die des Organs
# ---------------------------------------------------------------------------

def zustands_text(brain) -> str:
    """Wörtlich wie ``Cortex._zustand_text`` (ohne „Known entities")."""
    try:
        return render_llm_context(build_llm_context(brain)) + "\n\n"
    except Exception:  # noqa: BLE001 — wie das Organ: lieber ohne Zustand als nicht fragen
        return ""


def frage_fuer(brain, anlass: str, menue: list) -> str:
    """Wörtlich wie ``Cortex.consult``: Zustand + Anlass + Menü."""
    return (zustands_text(brain)
            + f"Anlass der Frage: {anlass}\n\n"
            + "Menü (wähle genau eine Nummer):\n" + menue_text(menue))


# ---------------------------------------------------------------------------
# Die Antwort — mit ihren Kosten
# ---------------------------------------------------------------------------

@dataclass
class Beratung:
    """Eine Beratung mit allem, was nachher gewogen wird."""

    zeit_s: float
    anlass: str
    menue: list
    stimmen: list
    entscheidung: dict
    zeit_ts: Optional[object] = None
    dauer_s: float = 0.0
    tokens_prompt: List[int] = field(default_factory=list)
    tokens_antwort: List[int] = field(default_factory=list)
    ladungen: List[float] = field(default_factory=list)

    @property
    def wahl(self) -> int:
        try:
            return int(self.entscheidung.get("wahl", NICHTS))
        except (TypeError, ValueError):
            return NICHTS

    @property
    def wahl_option(self) -> Optional[dict]:
        for option in self.menue:
            if option.get("id") == self.wahl:
                return option
        return None

    @property
    def wahl_token(self) -> Optional[str]:
        option = self.wahl_option
        return option.get("token") if option and self.wahl != NICHTS else None

    @property
    def wahl_entity(self) -> Optional[str]:
        option = self.wahl_option
        return option.get("entity_id") if option and self.wahl != NICHTS else None

    @property
    def wahl_zustand(self) -> Optional[str]:
        option = self.wahl_option
        return option.get("zustand") if option and self.wahl != NICHTS else None


class KostenSpion:
    """Sitzungs-Hülle: reicht alles durch und merkt sich den Preis.

    ``_call_ollama`` ruft ``session.post(...)`` als Kontextmanager und liest
    ``status``/``json()`` — mehr nicht. Genau das wird durchgereicht; die
    Antwort wird beim Lesen zusätzlich ausgewertet.
    """

    def __init__(self, sitzung):
        self.sitzung = sitzung
        self.antworten: list = []
        self.nutzlasten: list = []
        self.tokens_prompt: List[int] = []
        self.tokens_antwort: List[int] = []
        self.ladungen: List[float] = []
        self.dauern: List[float] = []

    def post(self, url, json=None, timeout=None):        # noqa: A002 — aiohttp-Name
        self.nutzlasten.append(json)
        return _Beitrag(self.sitzung.post(url, json=json, timeout=timeout), self)

    def merke(self, daten: dict) -> None:
        self.antworten.append(daten)
        self.tokens_prompt.append(int(daten.get("prompt_eval_count") or 0))
        self.tokens_antwort.append(int(daten.get("eval_count") or 0))
        self.ladungen.append(float(daten.get("load_duration") or 0) / 1e9)
        self.dauern.append(float(daten.get("total_duration") or 0) / 1e9)


class _Beitrag:
    def __init__(self, beitrag, spion: KostenSpion):
        self._beitrag, self._spion = beitrag, spion

    async def __aenter__(self):
        self._antwort = await self._beitrag.__aenter__()
        return _Antwort(self._antwort, self._spion)

    async def __aexit__(self, *args):
        return await self._beitrag.__aexit__(*args)


class _Antwort:
    def __init__(self, antwort, spion: KostenSpion):
        self._antwort, self._spion = antwort, spion

    @property
    def status(self):
        return self._antwort.status

    async def json(self):
        daten = await self._antwort.json()
        self._spion.merke(daten)
        return daten

    async def text(self):
        return await self._antwort.text()


def _in_faden(coro, frist: float = 600.0):
    """Fährt eine Koroutine in eigenem Faden mit eigenem Loop.

    Der Messlauf ist synchron (Schleife über Ereignisse); die Sitzung des
    Organs ist asynchron. Ein eigenes ``asyncio.run`` in einem Faden lässt
    den Loop des Aufrufers unberührt (dieselbe Vorsicht wie in
    ``tests/test_cortex_organ.py`` beschrieben).
    """
    ergebnis, fehler = {}, {}

    def lauf():
        try:
            ergebnis["wert"] = asyncio.run(coro)
        except BaseException as problem:  # noqa: BLE001 — reist zum Aufrufer
            fehler["problem"] = problem

    faden = threading.Thread(target=lauf, name="cortex-beratung")
    faden.start()
    faden.join(timeout=frist)
    if faden.is_alive():
        raise TimeoutError(f"Beratung lief länger als {frist:.0f} s")
    if fehler:
        raise fehler["problem"]
    return ergebnis.get("wert")


# ---------------------------------------------------------------------------
# Die drei Berater: Organ, Zufall (Abschaltprobe), Skript (Trockenlauf)
# ---------------------------------------------------------------------------

class Berater(Protocol):
    def berate(self, *, jetzt_s: float, anlass: str, menue: list,
               zeit_ts=None) -> Beratung:
        ...


class OrganBerater:
    """Das Organ am Draht: echte Agents, echte Mehrheit, echte Kosten."""

    def __init__(self, brain, agenten: Sequence[str] = STANDARD_AGENTEN,
                 modell: str = "llama3.2:1b", url: str = STANDARD_URL,
                 zeitlimit: float = STANDARD_ZEITLIMIT,
                 sitzung_bauer: Optional[Callable[[], object]] = None):
        self.brain = brain
        self.modell = modell
        self.url = url
        self.zeitlimit = zeitlimit
        self.agenten = [
            CortexAgent(name=name, provider="ollama", model=modell, url=url,
                        api_key="", system_prompt=organ_prompt(name))
            for name in agenten
        ]
        self.sitzung_bauer = sitzung_bauer or self._echte_sitzung
        self.aufrufe = 0

    @staticmethod
    def _echte_sitzung():
        import aiohttp
        return aiohttp.ClientSession()

    def berate(self, *, jetzt_s: float, anlass: str, menue: list,
               zeit_ts=None) -> Beratung:
        if len(menue) < 2:
            # Wörtlich wie Cortex.consult: kein Menü heißt kein Aufruf.
            return Beratung(
                zeit_s=jetzt_s, anlass=anlass, menue=menue, stimmen=[],
                entscheidung={"wahl": NICHTS, "gestrichen": [],
                              "grund": "kein Menü: die Engine sagt gerade "
                                       "nichts Ausführbares voraus"},
                zeit_ts=zeit_ts)
        frage = frage_fuer(self.brain, anlass, menue)
        sitzung = self.sitzung_bauer()
        spion = KostenSpion(sitzung)
        beginn = time.monotonic()
        try:
            stimmen = [self._stimme(agent, frage, menue, spion)
                       for agent in self.agenten]
        finally:
            _schliesse(sitzung)
        dauer = time.monotonic() - beginn
        entscheidung = entscheide(stimmen, menue)
        return Beratung(
            zeit_s=jetzt_s, anlass=anlass, menue=menue, stimmen=stimmen,
            entscheidung=entscheidung, zeit_ts=zeit_ts, dauer_s=dauer,
            tokens_prompt=list(spion.tokens_prompt),
            tokens_antwort=list(spion.tokens_antwort),
            ladungen=list(spion.ladungen))

    def _stimme(self, agent: CortexAgent, frage: str, menue: list,
                spion: KostenSpion) -> dict:
        self.aufrufe += 1
        try:
            return _in_faden(
                agent.waehle(frage, menue, spion, timeout=self.zeitlimit))
        except Exception as problem:  # noqa: BLE001 — eine Stimme darf die Runde nicht sprengen
            return {"agent": agent.name, "wahl": NICHTS,
                    "grund": f"{type(problem).__name__}: {problem}"[:300],
                    "sicherheit": 0, "veto": [], "gueltig": False}


def _schliesse(sitzung) -> None:
    schliessen = getattr(sitzung, "close", None)
    if schliessen is None:
        return
    try:
        ergebnis = schliessen()
        if asyncio.iscoroutine(ergebnis):
            _in_faden(ergebnis, frist=30.0)
    except Exception:  # noqa: BLE001 — ein Schließen-Fehler ist kein Messfehler
        pass


def _als_beratung(jetzt_s: float, anlass: str, menue: list, wahl: int,
                  wer: str, grund: str, zeit_ts=None) -> Beratung:
    stimmen = [{"agent": wer, "wahl": int(wahl), "grund": grund,
                "sicherheit": 0, "veto": [], "gueltig": True}]
    entscheidung = entscheide(stimmen, menue)
    return Beratung(zeit_s=jetzt_s, anlass=anlass, menue=menue,
                    stimmen=stimmen, entscheidung=entscheidung, zeit_ts=zeit_ts)


class ZufallsBerater:
    """Der B-Gegner des Cortex (Abschaltprobe): Zufallswahl aus dem Menü.

    Gleiche Saat ⇒ gleiche Folge; gezogen wird nur, was im Menü steht.
    """

    def __init__(self, saat: int = 0, name: str = "zufall"):
        self.name = name
        self.saat = saat
        self.rng = random.Random(saat)

    def berate(self, *, jetzt_s: float, anlass: str, menue: list,
               zeit_ts=None) -> Beratung:
        if len(menue) < 2:
            return _als_beratung(jetzt_s, anlass, menue, NICHTS, self.name,
                                 "kein Menü", zeit_ts)
        wahl = self.rng.choice([option["id"] for option in menue])
        return _als_beratung(jetzt_s, anlass, menue, wahl, self.name,
                             "Zufallswahl (Abschaltprobe)", zeit_ts)


class SkriptBerater:
    """Antwortet aus einem Drehbuch — Trockenlauf ohne Modell (CI, Tests)."""

    def __init__(self, wahlen: Sequence[int], name: str = "skript"):
        self.name = name
        self.wahlen = list(wahlen)
        self.gestellt = 0

    def berate(self, *, jetzt_s: float, anlass: str, menue: list,
               zeit_ts=None) -> Beratung:
        if len(menue) < 2:
            return _als_beratung(jetzt_s, anlass, menue, NICHTS, self.name,
                                 "kein Menü", zeit_ts)
        wahl = self.wahlen.pop(0) if self.wahlen else NICHTS
        if wahl not in {option["id"] for option in menue}:
            wahl = NICHTS
        self.gestellt += 1
        return _als_beratung(jetzt_s, anlass, menue, wahl, self.name,
                             "Drehbuch", zeit_ts)
