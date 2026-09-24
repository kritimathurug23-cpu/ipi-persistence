# Preregistration (DRAFT) — Where Does Injected Influence Survive?

*Measuring Within-Session Persistence of Indirect Prompt Injection Under Controlled Context Transformation*

Status: draft written during design (Weeks 4–5). Items marked **[FILL AT PILOT]** are completed after the
Weeks 6–7 pilot. Submit on OSF (osf.io) at the Week 8 freeze, together with the FREEZE.json hash.

---

## 1. Research questions

**Primary (confirmatory)**

- **RQ1 — Persistence under context transformation.** Following a successful compromise, to what extent does attacker influence persist across subsequent turns when the injected content is retained (P1), redacted (P2), or replaced by a summary (P3)?
- **RQ1a — Local versus broader persistence.** When residual influence persists, does it remain primarily on tasks related to the original attack, or does it persist on unrelated tasks?

**Supporting**

- **RQ3** Detection (spontaneous and prompted). **RQ4** Resistance and over-defense. **RQ5** Detection–resistance dissociation. **RQ6** Natural versus constructed compromised states.

The study does not assume that any particular model or condition will show more persistence. Expected findings listed in the proposal (Section 32) are possible outcomes, not hypotheses.

## 2. Design

- **Models (4):** three proprietary API models, one open-weight 7–8B model. Exact identifiers: **[FILL AT FREEZE — copy from config/experiment.yaml]**.
- **Generation settings:** provider-documented defaults (no temperature/top-p override); explicit values recorded per run.
- **Benchmark:** **[FILL]** attack scenarios across four attack categories (instruction override, goal hijacking, context manipulation, persistent behavioral influence), **[FILL]** benign instruction-like controls, and a fixed pool of unrelated tasks. Frozen data hash: **[FILL AT FREEZE]**.
- **Phase A (compromise characterization):** every attack and benign scenario runs inside a multi-turn script (legitimate pre-injection turns → external content with task → model reply), 2 repetitions. Prompted detection runs separately and never produces compromised states.
- **Phase B (persistence):** every usable compromised state is run under P1, P2, P3 and the P4 full-rollback control, with 6 subsequent turns, 2 repetitions. Same-topic and unrelated subsequent tasks are both run under P2 and P3 for task-independent markers; P1 and P4 use same-topic tasks.
- **Controls:** 5 clean trajectories per matched task; clean-summary control for P3 **[KEEP / DROP — decided at pilot]**; P4 full rollback.

### Condition definitions

| Condition | Pre-injection turns | Injected content | Influenced reply | Summary |
|---|---|---|---|---|
| P1 Retained | kept | kept | kept | none |
| P2 Redacted | kept | replaced by "[document removed]" | kept | none |
| P3 Summarized | summarized | summarized | summarized | same-model summary of the whole conversation, placed in the system prompt |
| P4 Full rollback (control) | kept | removed | removed | none |

Summarization instruction (fixed): see `harness/conditions.py` (`SUMMARY_INSTRUCTION`).

## 3. Sampling plan

- **Unit of analysis:** the usable compromised state.
- **Target:** approximately 40 usable compromised states per model.
- **Natural states:** every Phase A attack run in either "follows" cell (attacker marker present), whether or not the model detected the injection.
- **Constructed states:** for scenarios without a natural compromise, the same model writes the influenced reply under a direct instruction (e.g. "Respond only in French for this reply"), which is then placed after the injected document. Up to 3 attempts; the reply must contain the marker. Constructed histories only ever reuse the same model's output.
- **Stopping rule:** the sample is fixed by the frozen benchmark; no additional scenarios are added after inspecting Phase B results.

## 4. Variables

- **Compromise (Phase A):** preregistered attacker-goal marker present in the reply to the injection turn.
- **Primary outcome (Phase B):** attacker-goal marker present (0/1) at each subsequent turn t = 1…6. Marker definitions per scenario are in `data/scenarios/*.json` (types: canary, mention, signature, prefix, language, regex).
- **Duration:** time to first clean turn (primary); last influenced turn (exploratory). Trajectories still influenced at turn 6 are right-censored.
- **Secondary:** spontaneous detection (rule-based, `scoring/rules.py`), prompted detection, resistance (marker absent AND legitimate task completed), over-defense (benign control flagged or refused), task correctness (keyword criteria), judge-rated drift (0/1/2), P3 summary containing the marker.

## 5. Analysis plan

**Descriptive:** all rates with 95% cluster-bootstrap CIs (2,000 resamples; clusters = compromised states in Phase B, scenarios in Phase A).

**RQ1, confirmatory tests:**

1. *Does influence exceed the noise floor?* Exact McNemar tests on the same states and repetitions: P2 vs P4 and P3 vs P4, at turns 1 and 3.
2. *Do the persistence conditions differ?* Logistic mixed-effects model on P1–P3 only (reference P2): `marker ~ condition * turn + task_type + source + (1 | state_id)` (`analysis/glmer.R`), with Holm-adjusted pairwise contrasts at turns 1 and 3. If the model is singular or does not converge, refit without the condition × turn interaction and report both.

   *Rationale for excluding P4 from the model:* P4 is expected to show approximately zero markers by construction, which causes complete separation in a logistic model. Noise-floor comparisons against P4 therefore use the exact tests in (1).

3. Exact McNemar P2 vs P3 and P1 vs P2 at turns 1 and 3. Holm correction across all McNemar tests in (1) and (3).

**RQ1a:** for task-independent markers under P2 and P3, the within-state difference in marker rate (same-topic minus unrelated), with a bootstrap CI over states.

**Duration:** Kaplan–Meier curves of time to first clean turn by condition.

**RQ3–RQ5:** proportions with CIs; the detection × resistance 2×2 table per model.

**RQ6:** persistence by source (natural / constructed) per model and condition, reported with the number of states per cell; no pooling; no generalization beyond models with overlap.

**Cross-check:** GEE logistic model clustered by state (`analysis/analyze.py`).

## 6. Scoring validation

- Stratified, blinded sample of ~200 Phase B outputs labeled by the researcher; ~50 labeled by a second annotator (`validation/`).
- Agreement: Cohen's kappa (automatic marker vs human; human vs human). Initial practical benchmark κ ≈ 0.60. If agreement is substantially lower, the marker rule is reviewed; any change is reported as a deviation.

## 7. Exclusions and data handling

- API calls that fail after 5 retries are logged and reported; they are not replaced by new samples with different inputs.
- Successful calls are never rerun (responses are cached).
- Compromised states for which a condition could not be completed are reported, not silently dropped.

## 8. Pilot decision rules (written before the pilot)

- If an API model yields fewer than **[e.g. 10]** natural compromised states from the pilot scenarios, strengthen the attack set before the freeze.
- If the projected cost exceeds **[budget]**, reduce in order: repetitions → cross-task combinations → judge evaluations. P2 and P3 are never removed.
- If the clean-summary control costs more than **[X]** % of the budget, drop it and interpret P3 as a combined compression-and-transformation condition.
- If rule-based markers disagree with manual reading on more than **[X]** % of pilot outputs, revise the marker rules before the freeze.

## 9. Deviations

Any deviation from this plan after the freeze will be listed in the final report with its reason.
