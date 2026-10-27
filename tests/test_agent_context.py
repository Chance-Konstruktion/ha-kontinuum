"""Tests for the read-only external-agent context contract."""
from types import SimpleNamespace

from kontinuum_core.amygdala import Amygdala
from kontinuum_core.thalamus import Thalamus

from custom_components.kontinuum.agent_context import SCHEMA, build_agent_context


class _Agent:
    name = "comfort"
    provider = "ollama"
    model = "test-model"
    total_calls = 2
    total_errors = 1
    api_key = "must-never-appear"
    url = "http://secret-host"


class _Cortex:
    enabled = True
    beschaeftigt = False
    sequential_mode = True
    agents = [_Agent()]


def _fixture_brain():
    thalamus = Thalamus()
    thalamus.entity_semantic["light.living_room"] = "light"
    thalamus.entity_room["light.living_room"] = "living_room"
    token = "living_room.light.on"
    thalamus.token_to_id[token] = thalamus._next_id
    thalamus.id_to_token[thalamus._next_id] = token
    thalamus._next_id += 1

    amygdala = Amygdala()
    pfc = SimpleNamespace(
        operation_mode="confirm",
        activated_semantics={"light"},
        amygdala=amygdala,
    )
    return {
        "preset": "ausgeglichen",
        "_home_only_mode": True,
        "_persons_home": ["Alice Example"],
        "_last_predictions": [(thalamus.token_to_id[token], 0.8, 0.75, "hippocampus", 12)],
        "thalamus": thalamus,
        "prefrontal": pfc,
        "cortex": _Cortex(),
        "insula": SimpleNamespace(current_mode="relaxing"),
        "spatial": SimpleNamespace(get_current_location=lambda: "living_room"),
        "hippocampus": SimpleNamespace(total_events=42, accuracy=0.8, stats={"patterns": 9}),
        "cerebellum": SimpleNamespace(rules=[1, 2]),
        "basal_ganglia": SimpleNamespace(total_habits=3),
        "hypothalamus": SimpleNamespace(get_energy_summary=lambda: {"battery": 72.0, "solar": 1.2}),
        "amygdala": amygdala,
    }


def test_agent_context_is_read_only_and_zero_llm():
    payload = build_agent_context(_fixture_brain(), "0.test")
    assert payload["schema"] == SCHEMA
    assert payload["read_only"] is True
    assert payload["side_effects"] == []
    assert payload["resource_profile"]["llm_calls"] == 0
    assert payload["resource_profile"]["brain_writes"] == 0


def test_agent_context_only_exposes_grounded_menu_options():
    payload = build_agent_context(_fixture_brain(), "0.test")
    options = payload["action_options"]
    assert options[0]["label"] == "nichts tun"
    actions = [o for o in options if o["service"]]
    assert actions
    assert all(o["service"] == "light.turn_on" for o in actions)
    assert all(o["entity_id"] == "light.living_room" for o in actions)
    assert all(o["proposal_only"] and not o["execution_authorized"] for o in options)


def test_agent_context_redacts_secrets_and_person_names():
    payload = build_agent_context(_fixture_brain(), "0.test")
    serialized = repr(payload)
    for value in ("Alice Example", "must-never-appear", "secret-host", '"api_key":', '"system_prompt":'):
        assert value not in serialized


def test_agent_contract_preserves_control_boundaries():
    payload = build_agent_context(_fixture_brain(), "0.test")
    rules = payload["agent_contract"]["rules"]
    assert any("Never directly call a device service" in rule for rule in rules)
    assert payload["capabilities"]["request_consultation"]["may_enter_action_pipeline"] is True
    assert payload["capabilities"]["configuration_changes"]["requires_explicit_user_authorization"] is True
