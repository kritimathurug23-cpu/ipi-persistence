"""Logged, cached, retried model calls.

Rules this module enforces:
  * every call is appended to runs/<experiment>/calls.jsonl with the full input and output;
  * responses are cached by a hash of (model, system, messages, settings, cache_salt),
    so a crashed run can be resumed without paying twice. `cache_salt` includes the
    repetition number, so repetitions are always separate calls;
  * nothing is ever overwritten.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import providers


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class CallClient:
    def __init__(self, run_dir: str | Path, max_retries: int = 5):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.run_dir / "calls.jsonl"
        self.cache_dir = self.run_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.max_retries = max_retries

    def call(self, model: dict, system: str, messages: list[dict], cache_salt: str, meta: dict | None = None) -> dict:
        """model: one entry from config (name, provider, model_id, settings, ...)."""
        settings = dict(model.get("settings") or {})
        if model["provider"] == "mock":
            settings["_rep"] = cache_salt
        key = _hash({"model": model["model_id"], "provider": model["provider"], "system": system,
                     "messages": messages, "settings": settings, "salt": cache_salt})
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())

        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = providers.chat(model["provider"], model["model_id"], system, messages, settings,
                                      base_url=model.get("base_url"), api_key_env=model.get("api_key_env"))
                break
            except Exception as e:  # network errors, rate limits, etc.
                last_err = e
                time.sleep(min(60, 2 ** attempt))
        else:
            self._append({"type": "error", "key": key, "model": model["name"], "error": repr(last_err),
                          "meta": meta or {}, "timestamp": _now()})
            raise providers.ProviderError(f"Call failed after retries: {last_err!r}")

        record = {"type": "call", "key": key, "model": model["name"], "model_id": model["model_id"],
                  "provider": model["provider"], "settings": {k: v for k, v in settings.items() if k != "_rep"},
                  "system": system, "messages": messages, "output": resp["text"], "usage": resp["usage"],
                  "cache_salt": cache_salt, "meta": meta or {}, "timestamp": _now()}
        self._append(record)
        cache_file.write_text(json.dumps(resp, ensure_ascii=False))
        return resp

    def _append(self, record: dict):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: str | Path, record: dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
