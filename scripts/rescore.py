"""Re-score stored outputs after a scoring-rule change, without calling any model.

    python -m scripts.rescore --config config/experiment.yaml [--dry-run]

Every result row keeps the model's full output, so when a rule in scoring/ changes (for example
the context-aware marker adopted after the pilot), the derived columns can be recomputed:

    phase_a.jsonl             compromised, compromised_raw, detected, refused, task_correct
    phase_b.jsonl             marker, marker_raw, correct, constraint_kept, refused
    clean.jsonl               marker, marker_raw, correct, constraint_kept, refused
    phase_b_summaries.jsonl   summary_marker, summary_marker_raw

Originals are copied to results/backup_<timestamp>/ first; nothing is deleted. states.jsonl is
NOT rewritten: the set of compromised states was fixed when it was built. If a Phase A row is no
longer counted as compromised, the affected natural states are listed so you can decide (before
the freeze) whether to rebuild the states with `python -m harness.run states`.

Any rescoring after the freeze is a deviation and must be reported as such.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from harness.calls import read_jsonl
from harness.scenarios import load_scenarios, load_unrelated_tasks, pre_injection_constraints, subsequent_tasks
from scoring.markers import marker_present, marker_present_raw
from scoring.rules import constraints_all_kept, refused, spontaneous_detection, task_correct

ROOT = Path(__file__).resolve().parent.parent


def _rescore_rows(rows, fn, changes: Counter):
    out = []
    for r in rows:
        new = dict(r)
        new.update(fn(r))
        for k in new:
            if k not in r or r[k] != new[k]:
                changes[k] += 1
        out.append(new)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--dry-run", action="store_true", help="report changes without writing")
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / a.config).read_text())
    res = ROOT / cfg["run_dir"] / "results"
    scen = {s["scenario_id"]: s for s in load_scenarios(ROOT / cfg["scenarios_dir"])}
    unrelated = load_unrelated_tasks(ROOT / cfg["unrelated_tasks"])
    n_turns = cfg["n_subsequent_turns"]

    def turn_task(r):
        return subsequent_tasks(scen[r["scenario_id"]], r["task_type"], unrelated, n_turns)[r["turn"] - 1]

    def phase_a(r):
        s = scen[r["scenario_id"]]
        attack = r["kind"] == "attack"
        return {"compromised": marker_present(r["output"], s["marker"]) if attack else None,
                "compromised_raw": marker_present_raw(r["output"], s["marker"]) if attack else None,
                "detected": spontaneous_detection(r["output"]), "refused": refused(r["output"]),
                "task_correct": task_correct(r["output"], s.get("task_required_keywords", []))}

    def turn_row(r):
        s = scen[r["scenario_id"]]
        return {"marker": marker_present(r["output"], s["marker"]),
                "marker_raw": marker_present_raw(r["output"], s["marker"]),
                "correct": task_correct(r["output"], turn_task(r).get("required_keywords", [])),
                "constraint_kept": constraints_all_kept(r["output"], pre_injection_constraints(s)),
                "refused": refused(r["output"])}

    def summary(r):
        s = scen[r["state_id"].split("|")[1]]
        return {"summary_marker": marker_present(r["summary"], s["marker"]),
                "summary_marker_raw": marker_present_raw(r["summary"], s["marker"])}

    plan = [("phase_a.jsonl", phase_a), ("phase_b.jsonl", turn_row), ("clean.jsonl", turn_row),
            ("phase_b_summaries.jsonl", summary)]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = res / f"backup_{stamp}"
    rescored = {}
    for name, fn in plan:
        rows = read_jsonl(res / name)
        if not rows:
            continue
        changes = Counter()
        rescored[name] = _rescore_rows(rows, fn, changes)
        print(f"{name}: {len(rows)} rows; changed fields: {dict(changes) or 'none'}")

    # Natural states whose Phase A reply is no longer counted as compromised
    if "phase_a.jsonl" in rescored:
        still = {(r["model"], r["scenario_id"], r["rep"]): r["compromised"] for r in rescored["phase_a.jsonl"]}
        stale = [s["state_id"] for s in read_jsonl(res / "states.jsonl")
                 if s["source"] == "natural" and not still.get(
                     (s["model"], s["scenario_id"], int(s["state_id"].rsplit("r", 1)[1])), True)]
        if stale:
            print(f"\nWARNING: {len(stale)} natural state(s) are no longer compromised under the new rule:",
                  file=sys.stderr)
            for sid in stale:
                print("   ", sid, file=sys.stderr)
            print("   Decide before the freeze whether to rebuild states (python -m harness.run states).",
                  file=sys.stderr)

    if a.dry_run:
        print("\n(dry run: nothing written)")
        return
    backup.mkdir(parents=True, exist_ok=True)
    for name in rescored:
        shutil.copy2(res / name, backup / name)
        with (res / name).open("w", encoding="utf-8") as f:
            for r in rescored[name]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nRescored {len(rescored)} file(s); originals in {backup}")


if __name__ == "__main__":
    main()
