"""Unit-Tests für die Wiring-Helfer in custom_components/kontinuum/__init__.py.

Getestet wird mit den echten kontinuum_core-Modulen (Thalamus,
BasalGanglia, AnteriorCingulateCortex, Decision), damit das Zusammenspiel
der Verdrahtung verifiziert wird – nicht nur Mock-Verhalten.

Benötigt installiertes homeassistant + kontinuum-core (wie die Smoke-CI).
"""
from types import SimpleNamespace

from kontinuum_core.anterior_cingulate import AnteriorCingulateCortex
from kontinuum_core.basal_ganglia import BasalGanglia
from kontinuum_core.prefrontal_cortex import Decision
from kontinuum_core.thalamus import Thalamus

from custom_components.kontinuum import (
    _build_acc_proposals,
    _rank_with_basal_ganglia,
)


def _make_thalamus(tokens):
    t = Thalamus()
    for token in tokens:
        t.token_to_id[token] = t._next_id
        t.id_to_token[t._next_id] = token
        t._next_id += 1
    return t


def _tid(thalamus, token):
    return thalamus.token_to_id[token]


# ──────────────────────────────────────────────────────────────────
# _rank_with_basal_ganglia
# ──────────────────────────────────────────────────────────────────

def test_rank_acc_damping_lowers_confidence():
    thalamus = _make_thalamus(["wohnzimmer.light.on"])
    bg = BasalGanglia()
    preds = [(_tid(thalamus, "wohnzimmer.light.on"), 0.8, 0.6, "hippocampus", 20)]

    relaxed = _rank_with_basal_ganglia(preds, bg, 0, thalamus)
    acc = AnteriorCingulateCortex()
    acc.cognitive_control = 1.0
    stressed = _rank_with_basal_ganglia(preds, bg, 0, thalamus, acc=acc)

    assert stressed[0][2] < relaxed[0][2]
    # Max. Dämpfung ist 25%
    assert stressed[0][2] >= relaxed[0][2] * 0.75 - 1e-9


def test_rank_no_acc_keeps_behavior():
    thalamus = _make_thalamus(["bad.light.on"])
    bg = BasalGanglia()
    preds = [(_tid(thalamus, "bad.light.on"), 0.7, 0.5, "hippocampus", 10)]

    baseline = _rank_with_basal_ganglia(preds, bg, 0, thalamus)
    with_idle_acc = _rank_with_basal_ganglia(
        preds, bg, 0, thalamus, acc=AnteriorCingulateCortex())

    # Frischer ACC (cognitive_control=0) darf nichts verändern
    assert baseline[0][2] == with_idle_acc[0][2]


def test_rank_anticipation_boosts_expected_room():
    thalamus = _make_thalamus(["kueche.light.on", "bad.light.on"])
    bg = BasalGanglia()
    preds = [
        (_tid(thalamus, "kueche.light.on"), 0.5, 0.5, "hippocampus", 10),
        (_tid(thalamus, "bad.light.on"), 0.5, 0.5, "hippocampus", 10),
    ]

    ranked = _rank_with_basal_ganglia(
        preds, bg, 0, thalamus, expected_room="kueche")
    by_token = {tid: conf for tid, _prob, conf, _src, _n in ranked}

    boosted = by_token[_tid(thalamus, "kueche.light.on")]
    plain = by_token[_tid(thalamus, "bad.light.on")]
    assert abs(boosted - plain - 0.05) < 1e-9
    # Und der erwartete Raum gewinnt das Ranking
    assert ranked[0][0] == _tid(thalamus, "kueche.light.on")


# ──────────────────────────────────────────────────────────────────
# _build_acc_proposals
# ──────────────────────────────────────────────────────────────────

def test_single_source_means_no_conflict():
    thalamus = _make_thalamus(["flur.light.on"])
    preds = [(_tid(thalamus, "flur.light.on"), 0.8, 0.7, "hippocampus", 30)]

    proposals = _build_acc_proposals(preds, preds, None, None, thalamus)

    assert len(proposals) == 1
    acc = AnteriorCingulateCortex()
    assert acc.observe_decision(proposals) == 0.0


def test_cerebellum_disagreement_creates_conflict():
    thalamus = _make_thalamus(["flur.light.on", "flur.light.off"])
    preds = [(_tid(thalamus, "flur.light.on"), 0.8, 0.7, "hippocampus", 30)]
    fired_rule = SimpleNamespace(
        target=_tid(thalamus, "flur.light.off"), confidence=0.9)

    proposals = _build_acc_proposals(preds, preds, fired_rule, None, thalamus)

    assert {p["source"] for p in proposals} == {"hippocampus", "cerebellum"}
    acc = AnteriorCingulateCortex()
    assert acc.observe_decision(proposals) > 0.0


def test_basal_ganglia_flip_gets_own_vote():
    thalamus = _make_thalamus(["bad.light.on", "bad.switch.on"])
    raw = [
        (_tid(thalamus, "bad.light.on"), 0.8, 0.7, "hippocampus", 30),
        (_tid(thalamus, "bad.switch.on"), 0.6, 0.6, "hippocampus", 20),
    ]
    ranked = list(reversed(raw))  # BG hat die Reihenfolge gekippt

    proposals = _build_acc_proposals(raw, ranked, None, None, thalamus)

    assert {p["source"] for p in proposals} == {"hippocampus", "basal_ganglia"}


def test_reflex_as_ranked_top_does_not_double_vote():
    thalamus = _make_thalamus(["bad.light.on", "bad.light.off"])
    raw = [(_tid(thalamus, "bad.light.on"), 0.8, 0.7, "hippocampus", 30)]
    fired_rule = SimpleNamespace(
        target=_tid(thalamus, "bad.light.off"), confidence=0.9)
    # Reflex wurde injiziert und steht nach Ranking oben
    ranked = [(_tid(thalamus, "bad.light.off"), 0.9, 0.9, "cerebellum", 60)] + raw

    proposals = _build_acc_proposals(raw, ranked, fired_rule, None, thalamus)

    # Cerebellum stimmt einmal ab – nicht zusätzlich als "basal_ganglia"
    assert {p["source"] for p in proposals} == {"hippocampus", "cerebellum"}


def test_risky_decision_adds_amygdala_veto():
    thalamus = _make_thalamus(["flur.lock.unlocked"])
    preds = [(_tid(thalamus, "flur.lock.unlocked"), 0.8, 0.7, "hippocampus", 30)]
    decision = Decision()
    decision.risk = 0.8

    proposals = _build_acc_proposals(preds, preds, None, decision, thalamus)

    vetoes = [p for p in proposals if p.get("veto")]
    assert len(vetoes) == 1
    assert vetoes[0]["confidence"] == 0.8
    acc = AnteriorCingulateCortex()
    assert acc.observe_decision(proposals) > 0.0


def test_empty_predictions_yield_no_proposals():
    thalamus = _make_thalamus([])
    assert _build_acc_proposals([], [], None, None, thalamus) == []


# ──────────────────────────────────────────────────────────────────
# ACC outcome feedback (error-rate half of cognitive_control)
# ──────────────────────────────────────────────────────────────────

def test_acc_outcome_feedback_drives_cognitive_control():
    """User overrides/accepts must move cognitive_control.

    The handler now feeds overrides (system mistake) and implicit accepts
    (correct prediction) into acc.observe_outcome, so the error-rate half of
    cognitive_control (conflict·0.6 + error_rate·0.4) reflects real
    corrections — previously only the autonomous-execute path fed it, so for
    every non-ACTIVE user error_rate stayed 0 forever. observe_outcome only
    updates error_rate; cognitive_control is refreshed by the following
    observe_decision (exactly the handler order: feedback, then ranking).
    """
    acc = AnteriorCingulateCortex()
    assert acc.cognitive_control == 0.0

    for _ in range(20):
        acc.observe_outcome(False)   # repeated overrides = system mistakes
        acc.observe_decision([])     # refreshes the EMA-derived control
    assert acc.error_rate > 0.0
    stressed = acc.cognitive_control
    assert stressed > 0.0           # control now brakes on real errors

    for _ in range(80):
        acc.observe_outcome(True)    # consistent accepts = correct
        acc.observe_decision([])
    assert acc.error_rate < 0.1
    assert acc.cognitive_control < stressed   # recovers smoothly
