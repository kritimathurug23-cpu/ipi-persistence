"""Token usage and cost so far (check this daily during the experiment).

    python -m scripts.cost_report --config config/experiment.yaml

Prices come from `price_per_million_tokens` in the config. Fill them in from each
provider's current pricing page; they are placeholders in the template.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import yaml

from harness.calls import read_jsonl

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/experiment.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / a.config).read_text())
    prices = {m["name"]: m.get("price_per_million_tokens", {"input": 0, "output": 0}) for m in cfg["models"]}
    jm = cfg.get("judge_model")
    if jm:
        prices[jm["name"]] = jm.get("price_per_million_tokens", {"input": 0, "output": 0})
    tot = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0})
    errors = 0
    for r in read_jsonl(ROOT / cfg["run_dir"] / "calls.jsonl"):
        if r["type"] == "error":
            errors += 1
            continue
        t = tot[r["model"]]
        t["calls"] += 1
        t["input"] += r["usage"].get("input", 0)
        t["output"] += r["usage"].get("output", 0)
    grand = 0.0
    print(f"{'model':<24}{'calls':>8}{'in_tok':>12}{'out_tok':>12}{'cost_usd':>10}")
    for name, t in sorted(tot.items()):
        p = prices.get(name, {"input": 0, "output": 0})
        cost = t["input"] / 1e6 * p["input"] + t["output"] / 1e6 * p["output"]
        grand += cost
        print(f"{name:<24}{t['calls']:>8}{t['input']:>12}{t['output']:>12}{cost:>10.2f}")
    print(f"{'TOTAL':<56}{grand:>10.2f}")
    print(f"failed calls: {errors}")


if __name__ == "__main__":
    main()
