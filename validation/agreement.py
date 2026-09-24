"""Week 14: agreement statistics (proposal Section 20).

    python -m validation.agreement --config config/experiment.yaml \
        --labels runs/main/validation/labels_annotator1.csv [--labels2 runs/main/validation/labels_annotator2.csv]

Reports Cohen's kappa for automatic marker vs human, and human vs human if a second
annotator's file is given. Compare against the preregistered target (initial benchmark κ≈0.60).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--labels", required=True)
    ap.add_argument("--labels2")
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / a.config).read_text())
    key = pd.read_csv(ROOT / cfg["run_dir"] / "validation/key.csv")
    l1 = pd.read_csv(a.labels).dropna(subset=["human_marker"])
    d = key.merge(l1[["item_id", "human_marker", "human_drift"]], on="item_id")
    auto = d.marker.astype(str).str.lower().isin(["true", "1"]).astype(int)
    k = cohen_kappa_score(auto, d.human_marker.astype(int))
    print(f"Automatic marker vs annotator 1: kappa = {k:.3f} (n = {len(d)})")
    print("Disagreements by condition:")
    print(d.assign(disagree=(auto != d.human_marker.astype(int))).groupby("condition").disagree.mean().round(3))
    if a.labels2:
        l2 = pd.read_csv(a.labels2).dropna(subset=["human_marker"])
        m = l1.merge(l2, on="item_id", suffixes=("_1", "_2"))
        print(f"Annotator 1 vs 2 (marker): kappa = {cohen_kappa_score(m.human_marker_1.astype(int), m.human_marker_2.astype(int)):.3f} (n = {len(m)})")
        md = m.dropna(subset=["human_drift_1", "human_drift_2"])
        if len(md):
            kd = cohen_kappa_score(md.human_drift_1.astype(int), md.human_drift_2.astype(int), weights="linear")
            print(f"Annotator 1 vs 2 (drift, linear-weighted): kappa = {kd:.3f} (n = {len(md)})")


if __name__ == "__main__":
    main()
