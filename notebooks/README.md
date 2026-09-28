# Pilot notebooks (Kaggle, open-weight models, no API keys)

One notebook per model, set to the full benchmark (`LIMIT = None`; use `LIMIT = 10` for a quick pilot). Each person runs one on their own Kaggle account (own GPU quota). Run with Save Version → "Save & Run All (Commit)" so it continues with the laptop closed. The Llama 8B notebook stops itself after 11 hours (a commit past 12 hours fails and saves nothing) and saves its checkpoint; attach that output as an input and commit again to continue. Expect two commits.

| Notebook | Model | Accelerator | Model source |
|---|---|---|---|
| `pilot_kaggle_llama8b.ipynb` | Llama-3.1-8B-Instruct | GPU T4 x2 | Add Input → Models → "Llama 3.1" → Transformers → 8b-instruct |
| `../kaggle/ipi_single_model_kaggle.ipynb` | Qwen2.5-3B-Instruct | GPU T4 x1 | downloaded from Hugging Face (ungated); set `PROFILE = "full"` |

`pilot_kaggle_llama3b.ipynb` (Llama-3.2-3B, GPU T4 x1) is a faster spare, not used in the current plan.
`pilot_kaggle_qwen3b.ipynb` is superseded by the Qwen notebook in `kaggle/`.

Both need **Internet: On** and clone this repository at run time, so push before starting and run
the same commit. Each writes its checkpoint to `/kaggle/working/runs/pilot_<model>` and a
`runs_checkpoint.zip`; Save Version when done. To resume after a timeout, attach the saved output
as an input dataset and run again (finished calls come from the cache).

Afterwards, on one laptop:

```bash
# unpack the two zips so that runs/pilot_llama8b/results and runs/pilot_qwen3b/results exist
python -m scripts.merge_runs runs/pilot_llama8b runs/pilot_qwen3b --into runs/pilot
python -m analysis.analyze --config config/pilot_open.yaml
python -m scripts.cost_report --config config/pilot_open.yaml
```
