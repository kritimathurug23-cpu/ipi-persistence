"""Freeze the benchmark (proposal Section 28, timeline Week 8).

    python -m scripts.freeze --config config/experiment.yaml

Writes FREEZE.json with SHA-256 hashes of every data file and the config. After this,
`python -m harness.run ... --main` refuses to run if anything has changed.
Commit FREEZE.json and tag the repository (git tag v1.0-freeze).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compute_hashes(cfg_path: str) -> dict:
    hashes = {str(p.relative_to(ROOT)): _sha(p) for p in sorted((ROOT / "data").rglob("*")) if p.is_file()}
    hashes[cfg_path] = _sha(ROOT / cfg_path)
    return hashes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/experiment.yaml")
    a = ap.parse_args()
    out = {"frozen_at": datetime.now(timezone.utc).isoformat(), "config": a.config,
           "hashes": compute_hashes(a.config)}
    (ROOT / "FREEZE.json").write_text(json.dumps(out, indent=2))
    print(f"Froze {len(out['hashes'])} files -> FREEZE.json")


if __name__ == "__main__":
    main()
