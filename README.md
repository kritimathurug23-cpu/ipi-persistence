# Where Does Injected Influence Survive? — Semester 1 codebase

Code for measuring within-session persistence of indirect prompt injection under controlled
context transformation (P1 retained, P2 redacted, P3 summarized, P4 full-rollback control).
Section numbers below refer to the Semester 1 proposal.

## What is done, and what you still need to do

| Done in this repository | Still yours to do |
|---|---|
| Harness: provider adapters, logging, caching, retries, resumable runs | Get API keys, research credits, and GPU access |
| P1–P4 conditions, with unit tests | Verify each real provider adapter in the pilot (they are written but untested against live APIs) |
| Phase A, compromised-state building (natural + constructed), Phase B, clean controls, judge | Benchmark reviewed by the authors (60 attack scenarios + 12 benign controls, drafted with AI assistance); revise answer keywords after the pilot |
| Marker, detection, refusal, and correctness scoring | Literature review (Weeks 1–3) |
| Freeze mechanism that blocks post-freeze changes | Pilot decisions, then fill in and file the preregistration |
| Full analysis: tables, figures, McNemar, bootstrap, KM, GEE, R mixed model | Human labeling (Week 14) and a second annotator |
| Validation sampling and kappa scripts | Writing the report and paper |
| Preregistration draft | |

Everything has been run end to end with **simulated models** (`config/mock.yaml`). Those numbers
are meaningless; they only show the pipeline works.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests -q                  # 14 tests, including a full mock run
```

R (for the primary mixed model): install R, then `install.packages(c("lme4", "emmeans"))`.

API keys are read from environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GOOGLE_API_KEY` (or `GEMINI_API_KEY`), and `OPENAI_COMPATIBLE_API_KEY` for a hosted open-weight
endpoint. Never commit keys.

## Try the whole pipeline now (no keys needed)

```bash
python -m harness.run all --config config/mock.yaml
python -m analysis.analyze --config config/mock.yaml      # -> runs/mock/analysis/report.md
Rscript analysis/glmer.R runs/mock/analysis/turns.csv
```

## Week-by-week workflow

**Weeks 1–3 — literature + setup.** Read the benchmarks and persistence/memory papers; build your
positioning table. Get keys working: put one real model in a copy of the config and run
`python -m harness.run phase-a --config config/<yours>.yaml --models api_model_1 --limit-scenarios 1`.

**Weeks 4–5 — design.**
1. Fill every `REPLACE_` in `config/experiment.yaml`: exact dated model IDs, documented default
   settings (with source URLs), prices, open-weight checkpoint hash and inference stack.
2. Write scenarios following `data/SCENARIO_GUIDE.md` (~15 per category).
3. Draft `prereg/preregistration_draft.md`, including the pilot decision rules in Section 8,
   written BEFORE you run the pilot.

**Weeks 6–7 — pilot.** Use a separate run directory (e.g. `run_dir: runs/pilot`) on 2–3 models and ~10 scenarios:
```bash
python -m harness.run all --config config/pilot.yaml --models api_model_1,open_weight --limit-scenarios 10
python -m analysis.analyze --config config/pilot.yaml
python -m scripts.cost_report --config config/pilot.yaml
```
Check: attack success per model; markers vs your own reading of ~50 outputs; cost × full design;
whether constructed states are built successfully (`results/construct_failures.jsonl`).
Apply your preregistered decision rules.

**Week 8 — freeze.**
```bash
python -m scripts.freeze --config config/experiment.yaml
git add -A && git commit -m "Freeze" && git tag v1.0-freeze
```
File the preregistration on OSF with the FREEZE.json hashes. From now on, every run uses `--main`,
which refuses to run if any data or config file has changed.

**Weeks 9–10 — Phase A.**
```bash
python -m harness.run phase-a --config config/experiment.yaml --main
python -m harness.run states  --config config/experiment.yaml --main
```

**Weeks 11–13 — Phase B and clean controls.**
```bash
python -m harness.run phase-b --config config/experiment.yaml --main
python -m harness.run clean   --config config/experiment.yaml --main
python -m harness.run judge   --config config/experiment.yaml --main
python -m scripts.cost_report --config config/experiment.yaml      # daily
```
Runs are resumable: if anything crashes, run the same command again.

**Week 14 — validation.**
```bash
python -m validation.sample_for_labeling --config config/experiment.yaml --n 200
# label runs/main/validation/to_label.csv following validation/RUBRIC.md, save as labels_annotator1.csv
python -m validation.agreement --config config/experiment.yaml \
    --labels runs/main/validation/labels_annotator1.csv --labels2 runs/main/validation/labels_annotator2.csv
```

**Week 15 — analysis.**
```bash
python -m analysis.analyze --config config/experiment.yaml
Rscript analysis/glmer.R runs/main/analysis/turns.csv
```

**Week 16 — reporting.** `runs/main/analysis/report.md` and `figures/` are the starting point.
`runs/main/results/states.jsonl` is the Semester 2 starting set.

## Repository map

```
config/          experiment.yaml (real, fill in), mock.yaml (simulated)
data/            scenarios/*.json, unrelated_tasks.json, SCENARIO_GUIDE.md
harness/         providers.py, calls.py (log/cache/retry), scenarios.py, conditions.py (P1–P4), run.py
scoring/         markers.py (attacker-goal markers), rules.py (detection, refusal, correctness, judge)
analysis/        analyze.py (all tables/figures/tests), glmer.R (primary mixed model)
validation/      sample_for_labeling.py, agreement.py, RUBRIC.md
scripts/         freeze.py, cost_report.py
prereg/          preregistration_draft.md
tests/           conditions, scoring, freeze, full mock pipeline
runs/<name>/     calls.jsonl (every call, append-only), cache/, results/*.jsonl, analysis/
```

## Design decisions to know about

- **P4 is not in the mixed model.** P4 has ~0 markers by design, which causes complete separation
  in logistic regression (found when testing this pipeline). Noise-floor tests against P4 are exact
  McNemar tests; the mixed model compares P1–P3 with P2 as reference. This is in the preregistration draft.
- **P3 places the summary in the system prompt** with an empty history, as context compaction usually
  works, rather than inventing an assistant turn.
- **Constructed states** are written by the same model under a direct instruction, then placed after the
  injected document. Document this method exactly; reviewers will look closely at it.
- **Resistance** requires the marker to be absent AND the task to be completed (keyword check; falls back
  to "did not refuse" when a task has no keywords).
- **Rule-based detection and markers are a first pass.** They must be validated against human labels.
- **Repetitions are part of the cache key**, so repetitions are always separate calls, and a crashed run
  never pays twice for the same call.
