"""Week 14: draw a stratified, BLINDED sample for human labeling (proposal Section 20).

    python -m validation.sample_for_labeling --config config/experiment.yaml --n 200

Writes runs/<run>/validation/to_label.csv   (what annotators see: no model, no condition)
       runs/<run>/validation/key.csv        (hidden mapping back to the run; do not open while labeling)

Annotators fill `human_marker` (1 = attacker goal visible, 0 = not) and optionally
`human_drift` (0 none, 1 subtle, 2 clear), following the rubric in validation/RUBRIC.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from harness.calls import read_jsonl

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260923)
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / a.config).read_text())
    res = ROOT / cfg["run_dir"] / "results"
    scen = {}
    for p in (ROOT / cfg["scenarios_dir"]).glob("*.json"):
        s = pd.read_json(p, typ="series")
        scen[s["scenario_id"]] = s.get("attacker_goal", "")
    b = pd.DataFrame(read_jsonl(res / "phase_b.jsonl"))
    b["stratum"] = b.model + "|" + b.condition
    per = max(1, a.n // b.stratum.nunique())
    sample = (b.sample(frac=1, random_state=a.seed).groupby("stratum").head(per)
                .sample(frac=1, random_state=a.seed).reset_index(drop=True))
    sample["item_id"] = [f"item_{i:04d}" for i in range(len(sample))]
    out = ROOT / cfg["run_dir"] / "validation"
    out.mkdir(parents=True, exist_ok=True)
    sample.assign(attacker_goal=sample.scenario_id.map(scen), human_marker="", human_drift="")[
        ["item_id", "attacker_goal", "output", "human_marker", "human_drift"]].to_csv(out / "to_label.csv", index=False)
    sample[["item_id", "state_id", "model", "condition", "task_type", "rep", "turn", "marker"]].to_csv(
        out / "key.csv", index=False)
    print(f"{len(sample)} items -> {out/'to_label.csv'}")


if __name__ == "__main__":
    main()
