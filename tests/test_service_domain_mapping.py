"""Regression tests for Home Assistant service-domain normalization."""

from types import SimpleNamespace

from custom_components.kontinuum import (
    _cortex_action_to_decision,
    _service_call_for_decision,
)


class _Prefrontal:
    def __init__(self, result):
        self.result = result

    def get_service_call(self, decision):
        return dict(self.result) if self.result else None


def test_media_semantic_maps_to_real_home_assistant_domain():
    decision = SimpleNamespace(token="wohnzimmer.media.playing")
    call = {
        "domain": "media",
        "service": "media_play",
        "entity_id": "media_player.tv",
        "data": {"entity_id": "media_player.tv"},
    }

    result = _service_call_for_decision(_Prefrontal(call), decision)

    assert result["domain"] == "media_player"
    assert result["service"] == "media_play"
    assert result["entity_id"] == "media_player.tv"
    assert call["domain"] == "media"  # adapter does not mutate core-owned data


def test_other_service_domains_and_missing_decisions_are_unchanged():
    decision = SimpleNamespace(token="kueche.light.on")
    call = {"domain": "light", "service": "turn_on", "data": {"entity_id": "light.kueche"}}

    assert _service_call_for_decision(_Prefrontal(call), decision) == call
    assert _service_call_for_decision(_Prefrontal(None), decision) is None
    assert _service_call_for_decision(_Prefrontal(call), None) is None



def test_legacy_core_climate_tokens_receive_real_hvac_modes():
    for state, hvac_mode in (
        ("heat", "heat"),
        ("cool", "cool"),
        ("heat_cool", "heat_cool"),
        ("auto", "auto"),
        ("dry", "dry"),
        ("fan_only", "fan_only"),
    ):
        decision = SimpleNamespace(
            token=f"wohnzimmer.climate.{state}",
            entity_id="climate.living_room",
        )
        call = _service_call_for_decision(_Prefrontal(None), decision)

        assert call == {
            "domain": "climate",
            "service": "set_hvac_mode",
            "entity_id": "climate.living_room",
            "data": {
                "entity_id": "climate.living_room",
                "hvac_mode": hvac_mode,
            },
        }


def test_legacy_climate_aliases_are_normalized_without_mutating_core_result():
    for state, hvac_mode in (("heating", "heat"), ("cooling", "cool")):
        decision = SimpleNamespace(
            token=f"wohnzimmer.climate.{state}",
            entity_id="climate.living_room",
        )
        original = {
            "domain": "climate",
            "service": "set_hvac_mode",
            "entity_id": "climate.living_room",
            "data": {
                "entity_id": "climate.living_room",
                "hvac_mode": state,
            },
        }
        call = _service_call_for_decision(_Prefrontal(original), decision)

        assert call["data"]["hvac_mode"] == hvac_mode
        assert original["data"]["hvac_mode"] == state



class _ClimateThalamus:
    entity_semantic = {"climate.living_room": "climate"}
    entity_room = {"climate.living_room": "livingroom"}

    def get_or_create_token(self, token):
        self.last_token = token
        return 17


def test_cortex_consensus_token_preserves_selected_climate_mode():
    thalamus = _ClimateThalamus()
    decision = _cortex_action_to_decision(
        {"thalamus": thalamus},
        "climate.set_hvac_mode",
        "climate.living_room",
        0.8,
        token="livingroom.climate.cool",
    )

    assert decision is not None
    assert decision.token == "livingroom.climate.cool"
    assert decision.token_id == 17
    call = _service_call_for_decision(_Prefrontal(None), decision)
    assert call == {
        "domain": "climate",
        "service": "set_hvac_mode",
        "entity_id": "climate.living_room",
        "data": {"entity_id": "climate.living_room", "hvac_mode": "cool"},
    }


def test_cortex_service_only_climate_consensus_fails_closed_as_ambiguous():
    thalamus = _ClimateThalamus()
    assert (
        _cortex_action_to_decision(
            {"thalamus": thalamus},
            "climate.set_hvac_mode",
            "climate.living_room",
            0.8,
        )
        is None
    )


def test_cortex_rejects_consensus_token_that_disagrees_with_action_or_entity():
    thalamus = _ClimateThalamus()
    brain = {"thalamus": thalamus}

    assert _cortex_action_to_decision(
        brain,
        "climate.set_hvac_mode",
        "climate.living_room",
        0.8,
        token="livingroom.climate.heat",
    ) is not None

    assert _cortex_action_to_decision(
        brain,
        "light.turn_on",
        "climate.living_room",
        0.8,
        token="livingroom.climate.heat",
    ) is None

    assert _cortex_action_to_decision(
        brain,
        "light.turn_on",
        "climate.living_room",
        0.8,
        token="livingroom.light.on",
    ) is None
