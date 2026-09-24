"""End-to-end run with simulated models: every step must produce well-formed output."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_full_mock_pipeline(tmp_path):
    cfg = (ROOT / "config/mock.yaml").read_text().replace("run_dir: runs/mock", f"run_dir: {tmp_path}/run")
    cfg = cfg.replace("clean_reps: 5", "clean_reps: 2").replace("judge_max_rows: 300", "judge_max_rows: 20")
    cfg_path = tmp_path / "mock_test.yaml"
    cfg_path.write_text(cfg)
    r = subprocess.run([sys.executable, "-m", "harness.run", "all", "--config", str(cfg_path)],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    res = tmp_path / "run" / "results"
    for f in ("phase_a.jsonl", "phase_a_prompted.jsonl", "states.jsonl", "phase_b.jsonl", "clean.jsonl"):
        assert (res / f).exists() and (res / f).stat().st_size > 0, f
    # Resuming must not add duplicate rows
    before = (res / "phase_b.jsonl").read_text().count("\n")
    subprocess.run([sys.executable, "-m", "harness.run", "phase-b", "--config", str(cfg_path)], cwd=ROOT, check=True,
                   capture_output=True)
    assert (res / "phase_b.jsonl").read_text().count("\n") == before
