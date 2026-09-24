import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_freeze_blocks_changed_data(tmp_path):
    freeze = ROOT / "FREEZE.json"
    backup = freeze.read_text() if freeze.exists() else None
    target = ROOT / "data/scenarios/S001_override_canary.json"
    original = target.read_text()
    try:
        subprocess.run([sys.executable, "-m", "scripts.freeze", "--config", "config/mock.yaml"], cwd=ROOT, check=True,
                       capture_output=True)
        target.write_text(original.replace("Priya", "Priyanka"))
        r = subprocess.run([sys.executable, "-m", "harness.run", "phase-a", "--config", "config/mock.yaml", "--main"],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode != 0 and "changed since the freeze" in (r.stderr + r.stdout)
    finally:
        target.write_text(original)
        if backup is None:
            freeze.unlink(missing_ok=True)
        else:
            freeze.write_text(backup)
