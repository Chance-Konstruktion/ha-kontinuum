"""Provider contract tests: configured Cortex prompts and per-provider deadlines."""

import pytest

from custom_components.kontinuum import cortex as cortex_mod
from custom_components.kontinuum.cortex import CortexAgent, DEFAULT_PROMPTS, organ_prompt


MENUE = [{"id": 0, "text": "nichts tun"}, {"id": 1, "aktion": "light.turn_on",
         "entity_id": "light.kueche", "zustand": "on", "text": "Licht an"}]


class _Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self.payload

    async def text(self):
        return "unexpected response"


class _Session:
    def __init__(self, payload):
        self.payload = payload
        self.timeout = None
        self.url = None

    def post(self, url, json=None, headers=None, timeout=None):
        self.url = url
        self.timeout = timeout
        return _Response(self.payload)


def test_custom_prompt_is_included_but_menu_contract_remains_authoritative():
    prompt = organ_prompt("comfort", "Prefer energy efficiency and avoid noisy changes.")
    assert "Prefer energy efficiency and avoid noisy changes." in prompt
    assert "wahl" in prompt
    assert "nichts tun" in prompt


def test_builtin_legacy_prompt_does_not_conflict_with_organ_menu_schema():
    assert organ_prompt("comfort", DEFAULT_PROMPTS["comfort"]) == organ_prompt("comfort")


@pytest.mark.asyncio
async def test_agent_uses_configured_prompt_in_actual_organ_call(monkeypatch):
    seen = {}

    async def fake_call(*args, **kwargs):
        seen["system_prompt"] = args[5]
        return '{"wahl": 0, "grund": "kein klarer Vorteil", "sicherheit": 80}'

    monkeypatch.setattr(cortex_mod, "_call_llm", fake_call)
    agent = CortexAgent(
        name="comfort", provider="ollama", model="test", url="http://localhost",
        api_key="", system_prompt="Bevorzuge Energiesparen.",
    )
    result = await agent.waehle("Frage", MENUE, object())
    assert result["gueltig"] is True
    assert "Bevorzuge Energiesparen." in seen["system_prompt"]
    assert '"wahl"' in seen["system_prompt"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("caller", "payload"),
    [
        (cortex_mod._call_openai, {"choices": [{"message": {"content": "ok"}}]}),
        (cortex_mod._call_claude, {"content": [{"text": "ok"}]}),
        (cortex_mod._call_gemini, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}),
    ],
)
async def test_cloud_provider_http_timeout_is_configurable(caller, payload):
    session = _Session(payload)
    result = await caller(
        session, "https://provider.example", "key", "model", "system", "user",
        timeout=73,
    )
    assert result == "ok"
    assert session.timeout.total == 73


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "patched_function"),
    [
        ("openai", "_call_openai"),
        ("grok", "_call_openai"),
        ("custom", "_call_openai"),
        ("claude", "_call_claude"),
        ("gemini", "_call_gemini"),
    ],
)
async def test_dispatcher_forwards_configured_timeout(monkeypatch, provider, patched_function):
    seen = {}

    async def fake_call(*args, **kwargs):
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr(cortex_mod, patched_function, fake_call)
    await cortex_mod._call_llm(
        object(), provider, "https://provider.example", "key", "model",
        "system", "user", timeout=73,
    )
    assert seen["timeout"] == 73
