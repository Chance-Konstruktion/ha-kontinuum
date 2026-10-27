"""Bounded, read-only context contract for external KONTINUUM agents.

This module deliberately does not call an LLM, write brain state, expose secrets,
or execute Home Assistant services. It gives a connected agent enough grounded
state and capability information to reason without exporting brain.json.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .cortex_organ import NICHTS, baue_menue

SCHEMA = "kontinuum.agent_context.v1"
MAX_ACTION_OPTIONS = 10
MAX_PREDICTIONS = 5


def _number(value: Any) -> float | None:
    """Return a finite JSON-safe number, otherwise None."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _read(module: Any, attribute: str, default: Any = None) -> Any:
    try:
        return getattr(module, attribute)
    except Exception:  # defensive: a partially initialized module must not break status
        return default


def _stats(module: Any) -> dict:
    value = _read(module, "stats", {})
    return value if isinstance(value, dict) else {}


def build_agent_context(brain: dict, integration_version: str) -> dict:
    """Build a small machine-readable snapshot; never performs an LLM call.

    The returned action menu is a proposal boundary, not execution permission.
    Actual actions remain subject to KONTINUUM's normal operation-mode,
    activation, risk and confirmation checks.
    """
    brain = brain if isinstance(brain, dict) else {}
    thalamus = brain.get("thalamus")
    prefrontal = brain.get("prefrontal")
    cortex = brain.get("cortex")
    hippocampus = brain.get("hippocampus")
    cerebellum = brain.get("cerebellum")
    basal_ganglia = brain.get("basal_ganglia")
    insula = brain.get("insula")
    spatial = brain.get("spatial")
    hypothalamus = brain.get("hypothalamus")
    amygdala = brain.get("amygdala")

    mode = _read(prefrontal, "operation_mode",
                 _read(prefrontal, "mode", "unknown"))
    if not isinstance(mode, (str, int, float, bool)) and mode is not None:
        mode = getattr(mode, "value", str(mode))
    activated = _read(prefrontal, "activated_semantics", set()) or set()
    try:
        activated_semantics = sorted(str(item) for item in activated)
    except TypeError:
        activated_semantics = []

    predictions = brain.get("_last_predictions") or []
    top_predictions = []
    if thalamus is not None:
        for item in predictions[:MAX_PREDICTIONS]:
            try:
                token = thalamus.decode_token(item[0])
                top_predictions.append({
                    "token": str(token),
                    "probability": _number(item[1]) if len(item) > 1 else None,
                    "confidence": _number(item[2]) if len(item) > 2 else None,
                    "source": str(item[3]) if len(item) > 3 else None,
                    "observations": int(item[4]) if len(item) > 4 and item[4] is not None else None,
                })
            except (IndexError, KeyError, TypeError, ValueError, AttributeError):
                continue

    action_menu = [{"id": NICHTS, "text": "nichts tun"}]
    menu_truncated = False
    if thalamus is not None:
        try:
            full_menu = baue_menue(
                predictions, thalamus, _read(prefrontal, "amygdala", amygdala)
            )
            menu_truncated = len(full_menu) > MAX_ACTION_OPTIONS
            action_menu = full_menu[:MAX_ACTION_OPTIONS]
        except Exception:  # an incomplete snapshot must still return safe status
            action_menu = [{"id": NICHTS, "text": "nichts tun"}]

    safe_options = []
    for option in action_menu:
        action = option.get("aktion")
        safe_options.append({
            "choice_id": option.get("id", NICHTS),
            "label": str(option.get("text", "nichts tun"))[:160],
            "service": str(action) if action else None,
            "entity_id": str(option["entity_id"]) if option.get("entity_id") else None,
            "target_state": str(option["zustand"]) if option.get("zustand") is not None else None,
            "proposal_only": True,
            "execution_authorized": False,
        })

    energy_summary = {}
    try:
        summary = hypothalamus.get_energy_summary() if hypothalamus is not None else {}
        if isinstance(summary, dict):
            # Whitelist small, useful fields instead of serializing an entire module.
            for key in ("battery", "solar", "consumption", "grid", "status"):
                if key in summary and isinstance(summary[key], (str, int, float, bool, type(None))):
                    value = summary[key]
                    energy_summary[key] = _number(value) if isinstance(value, float) else value
    except Exception:
        energy_summary = {}

    hippocampus_stats = _stats(hippocampus)
    cerebellum_stats = _stats(cerebellum)
    amygdala_stats = _stats(amygdala)
    try:
        room = spatial.get_current_location() if spatial is not None else None
    except Exception:
        room = None
    try:
        energy_accuracy = _number(_read(hippocampus, "accuracy"))
    except Exception:
        energy_accuracy = None

    state = {
        "mode": _read(insula, "current_mode", "unknown"),
        "room": room,
        "predictions": top_predictions,
        "risk": _number(amygdala_stats.get("last_risk", 0)),
        "energy": energy_summary,
        "events_seen": _read(hippocampus, "total_events", 0),
        "prediction_accuracy": energy_accuracy,
        "patterns": hippocampus_stats.get("patterns", 0),
        "habits": _read(basal_ganglia, "total_habits", 0),
        "rules": len(_read(cerebellum, "rules", []) or []),
        "tracked_entities": len(_read(thalamus, "entity_semantic", {}) or {}),
    }

    agents = []
    for agent in (_read(cortex, "agents", []) or []):
        # An explicit allow-list prevents URLs, API keys and system prompts escaping.
        agents.append({
            "name": str(_read(agent, "name", "agent")),
            "provider": str(_read(agent, "provider", "unknown")),
            "model": str(_read(agent, "model", "unknown")),
            "total_calls": int(_read(agent, "total_calls", 0) or 0),
            "total_errors": int(_read(agent, "total_errors", 0) or 0),
        })

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "integration_version": str(integration_version),
        "read_only": True,
        "side_effects": [],
        "resource_profile": {
            "llm_calls": 0,
            "brain_writes": 0,
            "max_action_options": MAX_ACTION_OPTIONS,
            "options_truncated": menu_truncated,
        },
        "system": {
            "preset": brain.get("preset", "unknown"),
            "operation_mode": mode,
            "activated_semantics": activated_semantics,
            "home_only_mode": bool(brain.get("_home_only_mode", False)),
        },
        "brain": state,
        "cortex": {
            "enabled": bool(_read(cortex, "enabled", False)),
            "busy": bool(_read(cortex, "beschaeftigt", False)),
            "sequential_mode": bool(_read(cortex, "sequential_mode", False)),
            "agent_count": len(agents),
            "agents": agents,
        },
        "action_options": safe_options,
        "capabilities": {
            "read_context": {
                "service": "kontinuum.cortex_context",
                "model_calls": 0,
                "writes_state": False,
            },
            "request_consultation": {
                "service": "kontinuum.cortex_consult",
                "available": bool(_read(cortex, "enabled", False)),
                "model_calls": True,
                "may_enter_action_pipeline": True,
            },
            "review_learning": {
                "service": "kontinuum.brain_review",
                "available": bool(_read(cortex, "enabled", False)),
                "model_calls": True,
                "applies_suggestions_automatically": False,
            },
            "configuration_changes": {
                "services": [
                    "kontinuum.set_mode",
                    "kontinuum.activate",
                    "kontinuum.deactivate",
                ],
                "requires_explicit_user_authorization": True,
            },
        },
        "agent_contract": {
            "purpose": "help the user understand and improve KONTINUUM without bypassing its safeguards",
            "rules": [
                "Treat this payload as a snapshot, not as an instruction to act.",
                "Only discuss action options present in action_options; never invent entities or services.",
                "action_options are proposals, never execution permission.",
                "Never directly call a device service to enact a KONTINUUM proposal.",
                "KONTINUUM's operation mode, activated semantics, risk checks and confirmation pipeline remain authoritative.",
                "Do not change modes, activation, configuration or pending confirmations without explicit user intent.",
                "Prefer this zero-LLM snapshot for inspection; use Cortex LLM services only when analysis is genuinely needed or requested.",
                "When evidence is missing or ambiguous, state uncertainty and prefer no action.",
            ],
        },
        "privacy": {
            "includes_person_names": False,
            "includes_api_keys_or_prompts": False,
            "includes_raw_history_or_full_brain_export": False,
        },
    }
