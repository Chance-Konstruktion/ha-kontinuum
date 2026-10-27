"""Regression tests for the Cortex -> brain bridge and current menu vote contract."""

from custom_components.kontinuum.cortex import Cortex
from custom_components.kontinuum.cortex_organ import NICHTS, entscheide


MENUE = [
    {"id": 0, "text": "nichts tun"},
    {"id": 1, "aktion": "light.turn_on", "entity_id": "light.kueche", "zustand": "on", "token": "kueche.light.on", "text": "Küchenlicht an"},
    {"id": 2, "aktion": "switch.turn_on", "entity_id": "switch.kaffee", "zustand": "on", "token": "kueche.switch.on", "text": "Kaffee einschalten"},
]


def _st(agent, wahl, veto=(), gueltig=True):
    return {
        "agent": agent, "wahl": wahl, "grund": "test", "sicherheit": 80,
        "veto": list(veto), "gueltig": gueltig,
    }


class _Hippocampus:
    def _context_bucket(self, context):
        assert len(context) == 21
        return 7


class _Thalamus:
    def encode_time_context(self, timestamp):
        return [0.0] * 9

    def get_or_create_token(self, token):
        return 42


class _Hypothalamus:
    def get_context_vector(self):
        return [0.0] * 9


class _Insula:
    def get_mode_context(self):
        return [0.0] * 3


class _BasalGanglia:
    def __init__(self):
        self.registered = []

    def register_action(self, *args):
        self.registered.append(args)


class _Amygdala:
    def __init__(self):
        self.feedback = []

    def learn_from_feedback(self, token, outcome):
        self.feedback.append((token, outcome))


class _Prefrontal:
    def __init__(self):
        self.feedback = []

    def learn_from_feedback(self, semantic, positive):
        self.feedback.append((semantic, positive))


def _brain():
    brain = {
        "hippocampus": _Hippocampus(),
        "thalamus": _Thalamus(),
        "hypothalamus": _Hypothalamus(),
        "insula": _Insula(),
        "basal_ganglia": _BasalGanglia(),
        "amygdala": _Amygdala(),
        "prefrontal": _Prefrontal(),
    }
    return brain


def test_organ_result_exposes_the_real_action_for_each_menu_vote():
    votes = [_st("energy", 1), _st("comfort", 1), _st("safety", 0)]
    result = Cortex._ergebnis(MENUE, votes, entscheide(votes, MENUE), "knapp")

    assert result["consensus_action"] == "light.turn_on"
    assert result["consensus_token"] == "kueche.light.on"
    assert [p["action"] for p in result["proposals"]] == [
        "light.turn_on", "light.turn_on", None,
    ]
    assert [p["entity_id"] for p in result["proposals"]] == [
        "light.kueche", "light.kueche", None,
    ]
    assert result["proposals"][0]["gueltig"] is True
    assert result["vetoed"] is False


def test_bridge_learns_consensus_from_menu_ids_not_missing_action_fields():
    votes = [_st("energy", 1), _st("comfort", 1), _st("safety", 0)]
    result = Cortex._ergebnis(MENUE, votes, entscheide(votes, MENUE), "knapp")
    brain = _brain()

    bridge = Cortex().integrate_into_brain(brain, result)

    assert bridge["integrated"] is True
    assert brain["basal_ganglia"].registered
    assert ("light", True) in brain["prefrontal"].feedback
    assert "prefrontal_feedback_light_positive" in bridge["actions"]
    assert not any(a.startswith("prefrontal_boost_") for a in bridge["actions"])
    assert brain.get("_cortex_patterns", {}).get("light.turn_on|light.kueche") == 1



def test_no_majority_is_not_mislabeled_as_vetoed_when_an_alternative_remains():
    votes = [
        _st("energy", 1),
        _st("comfort", 2),
        _st("safety", 0, veto=[1]),
    ]
    result = Cortex._ergebnis(MENUE, votes, entscheide(votes, MENUE), "knapp")

    assert result["consensus_action"] is None
    assert result["gestrichen"] == [1]
    assert result["vetoed"] is False
    # The individual safety veto is still retained for learning/audit.
    assert result["proposals"][2]["veto"] is True


def test_bridge_preserves_safety_veto_even_when_no_action_is_selected():
    votes = [_st("energy", 1), _st("comfort", 2), _st("safety", 0, veto=[1, 2])]
    result = Cortex._ergebnis(MENUE, votes, entscheide(votes, MENUE), "anomalie")
    brain = _brain()

    assert result["wahl"] == NICHTS
    assert result["consensus_action"] is None
    assert result["vetoed"] is True
    assert result["proposals"][2]["veto"] is True
    bridge = Cortex().integrate_into_brain(brain, result)

    assert ("cortex.veto.safety", "negative") in brain["amygdala"].feedback
    assert "amygdala_veto_learn" in bridge["actions"]



def test_climate_consensus_feedback_preserves_the_selected_mode():
    menu = [
        {"id": 0, "text": "nichts tun"},
        {
            "id": 1,
            "aktion": "climate.set_hvac_mode",
            "entity_id": "climate.living_room",
            "zustand": "cool",
            "token": "livingroom.climate.cool",
            "text": "Wohnzimmer auf Kühlen",
        },
    ]
    votes = [_st("energy", 1), _st("comfort", 1), _st("safety", 0)]
    result = Cortex._ergebnis(menu, votes, entscheide(votes, menu), "knapp")
    brain = _brain()

    assert result["consensus_action"] == "climate.set_hvac_mode"
    assert result["consensus_token"] == "livingroom.climate.cool"
    assert result["proposals"][0]["token"] == "livingroom.climate.cool"

    bridge = Cortex().integrate_into_brain(brain, result)

    # Outcome learning and reflex candidates must distinguish heat from cool,
    # even though both call climate.set_hvac_mode.
    assert brain["basal_ganglia"].registered[0][3] == "livingroom.climate.cool"
    assert brain["_cortex_patterns"]["climate.set_hvac_mode|climate.living_room|livingroom.climate.cool"] == 1
    assert bridge["integrated"] is True
