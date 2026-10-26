"""Regression tests for Home Assistant service-domain normalization."""

from types import SimpleNamespace

from custom_components.kontinuum import _service_call_for_decision


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
