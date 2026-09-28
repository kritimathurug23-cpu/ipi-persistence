"""Merge several run directories (e.g. one Kaggle checkpoint per model) into one for analysis.

    python -m scripts.merge_runs runs/pilot_llama8b runs/pilot_qwen3b --into runs/pilot

Result files are append-only JSONL keyed by model, so merging is concatenation. Rows already
present in the target (same key) are skipped, so the command can be re-run after a checkpoint is
updated. calls.jsonl is concatenated too (for the cost report); the per-call cache is not copied.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from harness.calls import append_jsonl, read_jsonl

ROOT = Path(__file__).resolve().parent.parent

KEYS = {
    "phase_a.jsonl": ("model", "scenario_id", "rep"),
    "phase_a_prompted.jsonl": ("model", "scenario_id", "rep"),
    "states.jsonl": ("state_id",),
    "construct_failures.jsonl": ("model", "scenario_id"),
    "phase_b.jsonl": ("state_id", "condition", "task_type", "rep", "turn"),
    "phase_b_summaries.jsonl": ("kind", "state_id", "condition", "rep"),
    "clean.jsonl": ("model", "scenario_id", "condition", "task_type", "rep", "turn"),
    "judge.jsonl": ("state_id", "condition", "task_type", "rep", "turn"),
}


def _resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", help="run directories (each containing results/)")
    ap.add_argument("--into", required=True, help="target run directory")
    a = ap.parse_args()
    target = _resolve(a.into)
    (target / "results").mkdir(parents=True, exist_ok=True)
    for name, key in KEYS.items():
        seen = {tuple(r[k] for k in key) for r in read_jsonl(target / "results" / name)}
        added = 0
        for src in a.sources:
            for r in read_jsonl(_resolve(src) / "results" / name):
                k = tuple(r[k] for k in key)
                if k not in seen:
                    append_jsonl(target / "results" / name, r)
                    seen.add(k)
                    added += 1
        if added:
            print(f"{name}: +{added} rows")
    seen_calls = {r.get("key") for r in read_jsonl(target / "calls.jsonl")}
    added = 0
    for src in a.sources:
        for r in read_jsonl(_resolve(src) / "calls.jsonl"):
            if r.get("key") not in seen_calls:
                append_jsonl(target / "calls.jsonl", r)
                seen_calls.add(r.get("key"))
                added += 1
    print(f"calls.jsonl: +{added} records -> {target}")


if __name__ == "__main__":
    main()
