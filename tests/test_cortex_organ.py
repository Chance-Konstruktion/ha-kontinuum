"""Tests für den Cortex als Organ (Stufe 3a).

Der Anlass für diese Tests war die erste echte Beratung mit einem lokalen
Modell: Vier Agenten einigten sich darauf, einen Tür-Schalter zu betätigen,
„um nachzusehen“. Die Tests halten fest, was seitdem gilt:

- gefragt wird nur bei Anlass, nie im Kaltstart;
- gewählt wird aus einem Menü, das die Engine vorgibt – nichts anderes kommt durch;
- „nichts tun“ gewinnt, solange keine Option eine absolute Mehrheit hat;
- eine Zeitüberschreitung wird nicht wiederholt;
- aus dem, was der Mensch danach tut, entsteht eine Trefferquote.


Die asynchronen Tests laufen über pytest-asyncio, nicht über asyncio.run():
asyncio.run() schließt die Ereignisschleife, und die Fixtures von
pytest-homeassistant-custom-component scheitern danach in jedem weiteren Test.
"""
import asyncio

import pytest
from kontinuum_core.amygdala import Amygdala
from kontinuum_core.thalamus import Thalamus

from custom_components.kontinuum import cortex as cortex_mod
from custom_components.kontinuum.cortex import Cortex
from custom_components.kontinuum.cortex_organ import (
    NICHTS,
    Nachhall,
    anlass,
    antwort_schema,
    baue_menue,
    entscheide,
    lies_wahl,
)


def _thalamus(entitaeten):
    """entitaeten: {entity_id: (raum, semantik)}; Tokens werden mit angelegt."""
    t = Thalamus()
    for eid, (raum, sem) in entitaeten.items():
        t.entity_semantic[eid] = sem
        t.entity_room[eid] = raum
    return t


def _tid(t, token):
    if token not in t.token_to_id:
        t.token_to_id[token] = t._next_id
        t.id_to_token[t._next_id] = token
        t._next_id += 1
    return t.token_to_id[token]


@pytest.fixture
def haus():
    t = _thalamus({
        "light.wohnzimmer": ("wohnzimmer", "light"),
        "switch.kaffee": ("kueche", "switch"),
        "lock.haustuer": ("flur", "lock"),
        "sensor.temp": ("flur", "temperature"),
    })
    preds = [
        (_tid(t, "wohnzimmer.light.on"), 0.6, 0.55, "hippocampus", 30),
        (_tid(t, "kueche.switch.on"), 0.5, 0.50, "hippocampus", 20),
        (_tid(t, "flur.lock.unlocked"), 0.4, 0.40, "hippocampus", 10),
        (_tid(t, "flur.temperature.warm"), 0.3, 0.30, "hippocampus", 10),
        (_tid(t, "wohnzimmer.light.on"), 0.2, 0.20, "cerebellum", 5),
    ]
    return t, preds


# ── Menü ─────────────────────────────────────────────────────────

def test_menue_nur_ausfuehrbares_ohne_doppelte(haus):
    t, preds = haus
    menue = baue_menue(preds, t, Amygdala())
    assert menue[0] == {"id": NICHTS, "text": "nichts tun"}
    paare = [(o["aktion"], o["entity_id"]) for o in menue[1:]]
    # Licht und Kaffee ja; Schloss (nicht ausführbar), Sensor und das
    # doppelte Licht nein.
    assert paare == [("light.turn_on", "light.wohnzimmer"),
                     ("switch.turn_on", "switch.kaffee")]
    assert [o["id"] for o in menue] == [0, 1, 2]


def test_menue_ohne_entitaet_bleibt_leer():
    t = _thalamus({})
    preds = [(_tid(t, "bad.light.on"), 0.9, 0.9, "hippocampus", 50)]
    assert baue_menue(preds, t) == [{"id": NICHTS, "text": "nichts tun"}]


# ── Anlass ───────────────────────────────────────────────────────

def test_kein_anlass_im_kaltstart():
    preds = [(1, 0.5, 0.5, "h", 1), (2, 0.5, 0.48, "h", 1)]
    assert anlass(10, preds, True, 10_000, 0) is None


def test_anlass_anomalie_und_knapp_und_abstand():
    knapp = [(1, 0.5, 0.50, "h", 1), (2, 0.5, 0.45, "h", 1)]
    klar = [(1, 0.9, 0.90, "h", 1), (2, 0.1, 0.10, "h", 1)]
    assert anlass(1000, klar, True, 10_000, 0) == "anomalie"
    assert anlass(1000, knapp, False, 10_000, 0) == "knapp"
    assert anlass(1000, klar, False, 10_000, 0) is None
    # Mindestabstand zur letzten Beratung
    assert anlass(1000, knapp, True, 10_000, 9_500) is None


# ── Antwort lesen ────────────────────────────────────────────────

MENUE = [
    {"id": 0, "text": "nichts tun"},
    {"id": 1, "aktion": "light.turn_on", "entity_id": "light.a", "zustand": "on", "text": "a"},
    {"id": 2, "aktion": "switch.turn_on", "entity_id": "switch.b", "zustand": "on", "text": "b"},
]


def test_schema_laesst_nur_menue_nummern_zu():
    schema = antwort_schema(MENUE)
    assert schema["properties"]["wahl"]["enum"] == [0, 1, 2]
    assert "veto" not in schema["properties"]
    mit = antwort_schema(MENUE, mit_veto=True)
    assert mit["properties"]["veto"]["items"]["enum"] == [1, 2]


def test_erfundenes_wird_zu_nichts():
    # Genau das kam in der ersten Beratung zurück: die Vorlage abgeschrieben.
    roh = '{"action": "service.call", "entity_id": "switch.esp82_flur_door"}'
    assert lies_wahl(roh, MENUE)["wahl"] == NICHTS
    assert lies_wahl('{"wahl": 7, "grund": "x", "sicherheit": 90}', MENUE)["wahl"] == NICHTS
    assert lies_wahl("kein json", MENUE)["gueltig"] is False


def test_wahl_mit_text_drumherum_und_veto():
    roh = 'Klar: ```json\n{"wahl": "2", "grund": "Kaffee", "sicherheit": 140, "veto": [1, 0, 9]}\n```'
    st = lies_wahl(roh, MENUE, agent="safety")
    assert st["wahl"] == 2 and st["sicherheit"] == 100 and st["veto"] == [1]
    assert st["gueltig"] is True


# ── Auszählen ────────────────────────────────────────────────────

def _st(agent, wahl, veto=()):
    return {"agent": agent, "wahl": wahl, "grund": "", "sicherheit": 50,
            "veto": list(veto), "gueltig": True}


def test_mehrheit_gewinnt():
    e = entscheide([_st("energy", 1), _st("comfort", 1), _st("safety", 0)], MENUE)
    assert e["wahl"] == 1


def test_ohne_absolute_mehrheit_nichts_tun():
    e = entscheide([_st("energy", 1), _st("comfort", 2), _st("safety", 0)], MENUE)
    assert e["wahl"] == NICHTS


def test_veto_streicht_vor_dem_zaehlen():
    e = entscheide([_st("energy", 1), _st("comfort", 1), _st("safety", 1, veto=[1])], MENUE)
    assert e["wahl"] == NICHTS and e["gestrichen"] == [1]


def test_ungueltige_stimmen_zaehlen_nicht():
    kaputt = {"agent": "x", "wahl": 0, "veto": [], "gueltig": False}
    assert entscheide([kaputt], MENUE)["wahl"] == NICHTS
    e = entscheide([kaputt, _st("energy", 2)], MENUE)
    assert e["wahl"] == 2


# ── Nachhall ─────────────────────────────────────────────────────

def test_nachhall_trefferquoten():
    n = Nachhall(fenster_s=100)
    stimmen = [_st("energy", 1), _st("comfort", 0)]
    n.merke(0, MENUE, stimmen, {"wahl": NICHTS})
    n.beobachte("light.a", "on", 50)          # Mensch schaltet Option 1
    assert n.abschliessen(50) == 0            # Fenster noch offen
    assert n.abschliessen(101) == 1
    q = n.quoten()
    assert q["energy"] == 1.0 and q["comfort"] == 0.0
    assert q["engine"] == 1.0 and q["nichts"] == 0.0 and q["konsens"] == 0.0


def test_nachhall_ohne_tat_heisst_nichts_war_richtig():
    n = Nachhall(fenster_s=10)
    n.merke(0, MENUE, [_st("energy", 2)], {"wahl": 2})
    n.beobachte("light.a", "on", 50)          # zu spät, Fenster vorbei
    n.abschliessen(50)
    assert n.quoten()["nichts"] == 1.0 and n.quoten()["energy"] == 0.0
    # übersteht Speichern und Laden
    m = Nachhall()
    m.from_dict(n.to_dict())
    assert m.quoten() == n.quoten()


# ── Eine ganze Beratung ──────────────────────────────────────────

class _Agent:
    def __init__(self, name, wahl, veto=()):
        self.name, self.provider, self.model = name, "ollama", "test"
        self._wahl, self._veto = wahl, list(veto)
        self.fragen = []

    async def waehle(self, frage, menue, session, keep_alive=None, timeout=90):
        self.fragen.append(frage)
        return {"agent": self.name, "wahl": self._wahl, "grund": "test",
                "sicherheit": 80, "veto": self._veto, "gueltig": True}

    @property
    def stats(self):
        return {"name": self.name}


def _brain(t, preds):
    class _Pfc:
        amygdala = Amygdala()
    return {"thalamus": t, "_last_predictions": preds, "prefrontal": _Pfc()}


@pytest.mark.asyncio
async def test_beratung_waehlt_aus_dem_menue(haus):
    t, preds = haus
    c = Cortex()
    c.agents = [_Agent("energy", 1), _Agent("comfort", 1), _Agent("safety", 0),
                _Agent("coordinator", 2)]
    c.enabled = True
    erg = await c.consult(_brain(t, preds), anlass="knapp")
    assert erg["wahl"] == 1
    assert erg["consensus_action"] == "light.turn_on"
    assert erg["consensus_entity"] == "light.wohnzimmer"
    # Der Koordinator wird im Organ-Modus nicht gefragt.
    assert c.agents[3].fragen == []
    # Die Frage enthält das Menü, aber nicht mehr die Liste „you may control“.
    frage = c.agents[0].fragen[0]
    assert "0: nichts tun" in frage and "may control" not in frage
    assert len(c.nachhall.offen) == 1


@pytest.mark.asyncio
async def test_beratung_ohne_menue_fragt_niemanden():
    t = _thalamus({})
    c = Cortex()
    a = _Agent("energy", 1)
    c.agents, c.enabled = [a], True
    erg = await c.consult(_brain(t, []), anlass="anomalie")
    assert erg["wahl"] == NICHTS and erg["consensus_action"] is None
    assert a.fragen == []


# ── Keine Wiederholung bei Zeitüberschreitung ────────────────────

@pytest.mark.asyncio
async def test_zeitueberschreitung_wird_nicht_wiederholt():
    aufrufe = []

    async def langsam():
        aufrufe.append(1)
        raise asyncio.TimeoutError()

    with pytest.raises(asyncio.TimeoutError):
        await cortex_mod._retry_llm_call(langsam)
    assert len(aufrufe) == 1


@pytest.mark.asyncio
async def test_ollama_bekommt_schema_und_kein_denken():
    gesendet = {}

    class _Antwort:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def json(self):
            return {"message": {"content": '{"wahl": 1, "grund": "x", "sicherheit": 60}'}}

    class _Sitzung:
        def post(self, url, json=None, timeout=None):
            gesendet.update(json)
            return _Antwort()

    schema = antwort_schema(MENUE)
    roh = await cortex_mod._call_ollama(
        _Sitzung(), "http://x", "m", "sys", "frage", fmt=schema, think=False)
    assert gesendet["format"] == schema and gesendet["think"] is False
    assert lies_wahl(roh, MENUE)["wahl"] == 1
