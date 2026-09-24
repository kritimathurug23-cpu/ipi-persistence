"""Scenario loading and message construction.

A scenario's attack document is built from its clean document by inserting the
injection text at a fixed paragraph position. The clean and attack versions
therefore differ only by the injected text.
"""
from __future__ import annotations

import json
from pathlib import Path

DOC_OPEN = 'Document:\n"""\n'
DOC_CLOSE = '\n"""'
REDACTED = "[document removed]"

REQUIRED_FIELDS = ["scenario_id", "kind", "task_type", "pre_injection_turns", "document_clean",
                   "task", "subsequent_same_topic"]


def load_scenarios(directory: str | Path) -> list[dict]:
    out = []
    for p in sorted(Path(directory).glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        missing = [f for f in REQUIRED_FIELDS if f not in s]
        if missing:
            raise ValueError(f"{p.name}: missing fields {missing}")
        if s["kind"] == "attack":
            for f in ("category", "injection_text", "injection_position", "marker", "direct_instruction"):
                if f not in s:
                    raise ValueError(f"{p.name}: attack scenario missing '{f}'")
        if len(s["subsequent_same_topic"]) < 6:
            raise ValueError(f"{p.name}: need 6 same-topic subsequent tasks")
        out.append(s)
    return out


def load_unrelated_tasks(path: str | Path) -> list[dict]:
    tasks = json.loads(Path(path).read_text(encoding="utf-8"))
    if len(tasks) < 6:
        raise ValueError("need at least 6 unrelated tasks")
    return tasks


def attack_document(scenario: dict) -> str:
    paras = scenario["document_clean"].split("\n\n")
    pos = scenario["injection_position"]
    idx = {"beginning": 0, "middle": len(paras) // 2, "end": len(paras)}[pos]
    return "\n\n".join(paras[:idx] + [scenario["injection_text"]] + paras[idx:])


def format_injection_turn(task: str, document: str) -> str:
    return f"{task}\n\n{DOC_OPEN}{document}{DOC_CLOSE}"


def subsequent_tasks(scenario: dict, task_type: str, unrelated: list[dict], n: int) -> list[dict]:
    """Returns n task dicts {"prompt": str, "required_keywords": [...]}."""
    pool = scenario["subsequent_same_topic"] if task_type == "same_topic" else unrelated
    return [t if isinstance(t, dict) else {"prompt": t, "required_keywords": []} for t in pool[:n]]
