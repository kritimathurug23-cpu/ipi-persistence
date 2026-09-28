"""Quality checks for the benchmark scenarios (run after writing or editing any scenario).

These enforce the rules in data/SCENARIO_GUIDE.md, so a mistake in one of ~70 files is caught
automatically instead of silently distorting the results.
"""
import re
from collections import Counter
from pathlib import Path

import pytest

from harness.scenarios import attack_document, load_scenarios, load_unrelated_tasks
from scoring.markers import marker_present
from scoring.rules import normalize_answer

ROOT = Path(__file__).resolve().parent.parent
SCEN = load_scenarios(ROOT / "data/scenarios")
ATTACKS = [s for s in SCEN if s["kind"] == "attack"]
BENIGN = [s for s in SCEN if s["kind"] == "benign"]
UNRELATED = load_unrelated_tasks(ROOT / "data/unrelated_tasks.json")
CATEGORIES = ["instruction_override", "goal_hijacking", "context_manipulation", "persistent_behavioral_influence"]
TASK_TYPES = {"summarization", "question_answering", "information_extraction", "document_comparison", "classification"}
LENGTH_CHANGING = {"canary", "mention", "language", "signature", "prefix"}

# Answer keywords that are computed from the document rather than copied from it
COMPUTED_ANSWERS = {("S002", "48"), ("S049", "16"), ("S043", "yes"), ("S027", "no"), ("S044", "no"),
                    ("S009", "one"), ("S037", "60"), ("S050", "yes"), ("S051", "yes"), ("S046", "yes"), ("S057", "yes")}


def _prompts(s):
    return ([t["prompt"] if isinstance(t, dict) else t for t in s["pre_injection_turns"]] + [s["task"]] +
            [t["prompt"] if isinstance(t, dict) else t for t in s["subsequent_same_topic"]])


def test_counts_and_ids():
    ids = [s["scenario_id"] for s in SCEN]
    assert len(ids) == len(set(ids)), "duplicate scenario_id"
    assert Counter(s["category"] for s in ATTACKS) == {c: 15 for c in CATEGORIES}
    assert len(BENIGN) >= 10


@pytest.mark.parametrize("cat", CATEGORIES)
def test_balance_within_category(cat):
    group = [s for s in ATTACKS if s["category"] == cat]
    assert {s["task_type"] for s in group} == TASK_TYPES
    assert {s["injection_position"] for s in group} == {"beginning", "middle", "end"}


@pytest.mark.parametrize("s", ATTACKS, ids=lambda s: s["scenario_id"])
def test_attack_scenario(s):
    doc, marker, sid = s["document_clean"], s["marker"], s["scenario_id"]
    # the injection is really inserted, and the clean document does not already contain it
    assert s["injection_text"] not in doc and s["injection_text"] in attack_document(s)
    # the clean document and every prompt must NOT already show the attacker marker (no false positives)
    assert not marker_present(doc, marker), f"{sid}: marker already in clean document"
    for p in _prompts(s):
        assert not marker_present(p, marker), f"{sid}: marker appears in prompt: {p}"
    if marker.get("task_independent"):
        for t in UNRELATED:
            assert not marker_present(t["prompt"], marker), f"{sid}: marker in unrelated task"
    # the injection actually asks for the marker
    if marker["type"] in ("canary", "mention", "signature", "prefix"):
        assert marker["value"] in s["injection_text"]
    if marker["type"] == "regex":
        assert re.search(marker["value"], s["injection_text"], flags=re.I)
        assert marker.get("task_independent") is False
    # the injection style is recorded
    assert s.get("injection_format") in {"note_to_ai", "ps", "system_update", "hidden_comment", "metadata", "plain"}
    # the direct instruction (used for constructed states) exists
    assert s["direct_instruction"].strip()
    # six follow-ups, each with a checkable answer that comes from the document
    assert len(s["subsequent_same_topic"]) == 6
    for t in s["subsequent_same_topic"]:
        assert t["required_keywords"], f"{sid}: follow-up without keyword: {t['prompt']}"
        for k in t["required_keywords"]:
            alts = [k] if isinstance(k, str) else k
            assert any(normalize_answer(a) in normalize_answer(doc) or (sid, a) in COMPUTED_ANSWERS for a in alts), \
                f"{sid}: keyword {k!r} not in document"


@pytest.mark.parametrize("s", ATTACKS, ids=lambda s: s["scenario_id"])
def test_legitimate_instruction(s):
    """RQ2 rules from SCENARIO_GUIDE rule 9."""
    cs = s.get("pre_injection_constraints", [])
    assert len(cs) == 1, f"{s['scenario_id']}: expected exactly one pre-injection constraint"
    c = cs[0]
    pre_text = " ".join(t["prompt"] for t in s["pre_injection_turns"])
    if c["type"] == "max_words":
        assert s["marker"]["type"] not in LENGTH_CHANGING, "no word limits when the attack changes answer length"
        assert str(c["value"]) in pre_text, "the word limit must be stated in a pre-injection turn"
    elif c["type"] == "must_include":
        assert c["value"] in pre_text, "the required name must be stated in a pre-injection turn"
        later = s["document_clean"] + " " + s["task"] + " " + " ".join(t["prompt"] for t in s["subsequent_same_topic"])
        assert c["value"].lower() not in later.lower(), "the name must not appear later, or it is not a test of retention"
        assert c["value"].lower() not in s["injection_text"].lower()
    else:
        pytest.fail(f"unexpected constraint type {c['type']}")


@pytest.mark.parametrize("s", BENIGN, ids=lambda s: s["scenario_id"])
def test_benign_scenario(s):
    assert "injection_text" not in s and "marker" not in s
    assert len(s["subsequent_same_topic"]) >= 6
