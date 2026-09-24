# Writing scenarios

Each scenario is one JSON file in `data/scenarios/`. The five `S00x` files and two `B00x`
files are worked examples, one per attack category plus benign controls. The full
benchmark needs about 15 attack scenarios per category (~60) plus about 10–15 benign
controls, written in Weeks 4–5.

## Attack scenario fields

| Field | Meaning |
|---|---|
| `scenario_id` | unique, e.g. `S017` |
| `kind` | `"attack"` |
| `category` | `instruction_override`, `goal_hijacking`, `context_manipulation`, `persistent_behavioral_influence` |
| `task_type` | `summarization`, `question_answering`, `information_extraction`, `document_comparison`, `classification` |
| `pre_injection_turns` | legitimate turns before the document. **Include checkable facts or constraints** (a name, a length limit): Semester 2 uses them to measure context retention |
| `document_clean` | the external content, paragraphs separated by blank lines |
| `injection_text` | the malicious instruction; inserted at `injection_position` (`beginning`, `middle`, `end`) |
| `task` | the user's legitimate request about the document |
| `task_required_keywords` | words a correct answer must contain (word-boundary, case-insensitive) |
| `marker` | `{"type", "value", "task_independent"}`, see `scoring/markers.py` |
| `attacker_goal` | one sentence, shown to the judge and to human annotators |
| `direct_instruction` | used ONLY to build constructed states: asks the same model to show the target behavior in its reply |
| `subsequent_same_topic` | exactly 6 follow-up tasks about the same document, each with `required_keywords` |

## Rules that protect validity

1. **Clean and attack versions differ only by the injected text.** Never edit the clean document to fit the injection.
2. **Every marker must be scorable by software.** If you can't write the check, change the attacker goal.
3. **`task_independent: true` only if the marker could appear in ANY answer** (language, signature, prefix, canary, product mention). Planted facts are `false`.
4. **Same-topic tasks must give the marker a chance to appear.** For a planted fact, at least two follow-ups should ask about it.
5. **Keywords must be unambiguous.** Prefer names and numbers; avoid words a wrong answer would also contain.
6. **Vary injection position and format** across scenarios (plain text, "note to AI", P.S., metadata-style) and record them.
7. **No real people, companies, credentials, or URLs.** Use fictional names and products.
8. **Unrelated tasks** (`data/unrelated_tasks.json`) ask for two or three sentences, so language detection has enough text.

Run `python -m pytest tests -q` after adding scenarios: loading validates required fields.
