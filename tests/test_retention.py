"""RQ2: adherence must be reported separately for turns where the attacker marker is absent."""
import pandas as pd

from analysis.analyze import retention_by_condition


def test_retention_stratified_by_marker():
    # 2 states. Marker-present turns always BREAK the instruction (as a French answer breaking a
    # word limit would); marker-absent turns always KEEP it. The primary estimate must not be
    # dragged down by the attack.
    rows = []
    for state in ("s1", "s2"):
        for turn, marker in enumerate([True, True, False, False], start=1):
            rows.append({"state_id": state, "condition": "P2", "task_type": "same_topic", "turn": turn,
                         "marker_f": float(marker), "constraint_f": 0.0 if marker else 1.0})
    b = pd.DataFrame(rows)
    rc = retention_by_condition(b, pd.DataFrame(), "same_topic").set_index("condition")
    assert rc.loc["P2", "adherence_marker_absent"] == 1.0
    assert rc.loc["P2", "adherence_marker_present"] == 0.0
    assert rc.loc["P2", "adherence_all"] == 0.5
    assert rc.loc["P2", "n_turns_marker_absent"] == 4


def test_retention_includes_clean_controls():
    clean = pd.DataFrame([{"model": "m", "scenario_id": sc, "condition": "CLEAN", "task_type": "same_topic",
                           "marker": False, "constraint_kept": kept}
                          for sc, kept in (("S1", True), ("S2", True), ("S3", False))])
    b = pd.DataFrame(columns=["state_id", "condition", "task_type", "marker_f", "constraint_f"])
    rc = retention_by_condition(b, clean, "same_topic").set_index("condition")
    assert abs(rc.loc["CLEAN", "adherence_marker_absent"] - 2 / 3) < 1e-9
