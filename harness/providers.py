"""Provider adapters behind one interface.

Every adapter implements:
    chat(model_id, system, messages, settings) -> {"text": str, "usage": {"input": int, "output": int}}

`messages` is a list of {"role": "user" | "assistant", "content": str}.
`settings` is passed through to the provider unchanged, so whatever is written in
config/experiment.yaml is exactly what is sent (this is what gets recorded).

The real adapters (anthropic, openai, google, openai_compatible) import their SDKs
lazily so the rest of the code works without them installed. They have NOT been
run against live APIs in this repository: check each one in the pilot.

The `mock` provider simulates a model that sometimes follows injections and
sometimes carries the behaviour forward. It exists only to test the pipeline
end to end; its numbers mean nothing.
"""
from __future__ import annotations

import hashlib
import random
import re


class ProviderError(RuntimeError):
    pass


# --------------------------------------------------------------------------- real providers

def _anthropic(model_id, system, messages, settings):
    import anthropic  # pip install anthropic
    client = anthropic.Anthropic()
    kwargs = {"max_tokens": 1024, **settings}
    resp = client.messages.create(model=model_id, system=system, messages=messages, **kwargs)
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return {"text": text, "usage": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}}


def _openai_like(model_id, system, messages, settings, base_url=None, api_key_env="OPENAI_API_KEY"):
    import os
    from openai import OpenAI  # pip install openai
    client = OpenAI(base_url=base_url, api_key=os.environ.get(api_key_env, "EMPTY"))
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    resp = client.chat.completions.create(model=model_id, messages=msgs, **settings)
    usage = resp.usage
    return {"text": resp.choices[0].message.content or "",
            "usage": {"input": getattr(usage, "prompt_tokens", 0), "output": getattr(usage, "completion_tokens", 0)}}


def _google(model_id, system, messages, settings):
    from google import genai  # pip install google-genai
    client = genai.Client()
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages]
    config = {**settings}
    if system:
        config["system_instruction"] = system
    resp = client.models.generate_content(model=model_id, contents=contents, config=config)
    um = getattr(resp, "usage_metadata", None)
    return {"text": resp.text or "",
            "usage": {"input": getattr(um, "prompt_token_count", 0) or 0,
                      "output": getattr(um, "candidates_token_count", 0) or 0}}


# --------------------------------------------------------------------------- mock provider

_FR = ["Voici une réponse à votre demande.", "Le document présente plusieurs points importants.",
       "Nous pouvons conclure que les arguments sont clairs.", "C'est une analyse assez simple."]
_EN = ["Here is a response to your request.", "The document presents several important points.",
       "In summary, the main arguments are clearly stated.", "This analysis is fairly straightforward."]

_PATTERNS = {
    "french": re.compile(r"respond (?:only )?in French", re.I),
    "signature": re.compile(r'end (?:every|each|all of your|your|this) (?:answer|response|reply)s? with (?:the signature )?"([^"]+)"', re.I),
    "prefix": re.compile(r'begin (?:every|each|your) (?:answer|response|reply)s? with "([^"]+)"', re.I),
    "canary": re.compile(r'(?:reply|respond) only with the phrase "([^"]+)"', re.I),
    "mention": re.compile(r'(?:recommend|mention) (?:the product )?"([^"]+)"', re.I),
    "fact": re.compile(r'state that ([^.]+)\.', re.I),
}


def _mock(model_id, system, messages, settings):
    """Deterministic-per-input simulated model. Only for testing the pipeline."""
    seed_src = model_id + system + "".join(m["content"] for m in messages) + str(settings.get("_rep", ""))
    rng = random.Random(int(hashlib.sha256(seed_src.encode()).hexdigest()[:12], 16))
    susceptibility = {"mock-weak": 0.8, "mock-strong": 0.25}.get(model_id, 0.5)
    last_user = messages[-1]["content"] if messages else ""

    if "JUDGE_TASK" in last_user:          # simulated judge output
        return {"text": '{"drift": %d, "reason": "simulated"}' % rng.choice([0, 0, 0, 1, 2]),
                "usage": {"input": 100, "output": 10}}
    if "Does it contain any instruction that attempts" in last_user:   # prompted detection
        hit = any(pat.search(last_user) for pat in _PATTERNS.values())
        ans = "YES" if (hit and rng.random() < 0.9) or (not hit and rng.random() < 0.1) else "NO"
        return {"text": ans + "\nSimulated explanation.", "usage": {"input": 250, "output": 10}}
    if "SUMMARIZE_CONVERSATION" in last_user:
        visible = system + " " + " ".join(m["content"] for m in messages[:-1])
        s = "The user asked for help with several documents and tasks."
        for key in ("french", "signature", "prefix", "mention", "fact"):
            m = _PATTERNS[key].search(visible)
            if m and rng.random() < 0.5:   # summary sometimes carries the instruction forward
                s += " A document also said: " + m.group(0) + "."
        return {"text": s, "usage": {"input": 200, "output": 40}}

    # Instructions visible anywhere in the current context (documents, summaries, direct requests)
    visible = system + " " + " ".join(m["content"] for m in messages if m["role"] == "user")
    active = {}
    for key, pat in _PATTERNS.items():
        m = pat.search(visible)
        if m:
            outside_doc = re.sub(r'Document:\n""".*?"""', "", last_user, flags=re.S)
            p = 0.95 if pat.search(outside_doc) else susceptibility
            if rng.random() < p:
                active[key] = m.group(1) if m.groups() else True
    # Behaviour carried forward from the model's own earlier replies (decays with distance)
    prior = [m["content"] for m in messages if m["role"] == "assistant"]
    for dist, text in enumerate(reversed(prior), start=1):
        carry = 0.7 * (0.75 ** (dist - 1))
        if text.startswith("Voici") and rng.random() < carry:
            active.setdefault("french", True)
        sig = re.search(r"\n— (.+)$", text)
        if sig and rng.random() < carry:
            active.setdefault("signature", sig.group(1))

    if "canary" in active:
        return {"text": active["canary"], "usage": {"input": 300, "output": 5}}
    body = list(_FR if "french" in active else _EN)
    rng.shuffle(body)
    text = " ".join(body[:3])
    if "mention" in active:
        text += f" I also recommend {active['mention']}."
    if "fact" in active:
        text += f" Note that {active['fact']}."
    if "prefix" in active:
        text = active["prefix"] + " " + text
    if "signature" in active:
        text += f"\n— {active['signature']}"
    if "Document:" in last_user and not active and rng.random() < 0.3:
        text = "Note: the document contains an embedded instruction, which I will ignore. " + text
    return {"text": text, "usage": {"input": 300, "output": 60}}


# --------------------------------------------------------------------------- dispatch

def chat(provider: str, model_id: str, system: str, messages: list[dict], settings: dict,
         base_url: str | None = None, api_key_env: str | None = None) -> dict:
    settings = dict(settings or {})
    if provider == "mock":
        return _mock(model_id, system, messages, settings)
    settings.pop("_rep", None)
    if provider == "anthropic":
        return _anthropic(model_id, system, messages, settings)
    if provider == "openai":
        return _openai_like(model_id, system, messages, settings)
    if provider == "openai_compatible":           # e.g. a vLLM server for the open-weight model
        return _openai_like(model_id, system, messages, settings, base_url=base_url,
                            api_key_env=api_key_env or "OPENAI_COMPATIBLE_API_KEY")
    if provider == "google":
        return _google(model_id, system, messages, settings)
    raise ProviderError(f"Unknown provider: {provider}")
