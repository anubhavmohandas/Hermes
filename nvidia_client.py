#!/usr/bin/env python3
"""
ollama_client.py — Tier 2 model dispatch. The piece that makes "multi-model"
true instead of a label (2026-07-02 gap analysis, B0): brain.py classifies a
task as Tier 2, and until this file existed nothing consumed that verdict —
every sub-skill ran on Claude regardless.

Flow (mirrors SKILL.md §2):
    brain.py check --task ... --via local   -> tier
    if tier == 2: ollama_client.chat(...)   -> local model, data never leaves

Enforcement is NOT re-implemented here — this calls the same brain.py
functions the hook path uses:
  - check_model_allowed(2, model, via="local") before every call (the
    Chinese-API exclusion is via=api only; local open-weight builds are
    exempt by design, but the check stays as the single seam).
  - Sensitive data MAY route here (Tier 2 = local, data never leaves the
    machine) — that's the H2-audited rule in brain.get_tier().

Stdlib only (urllib): no third-party HTTP dep for the core dispatch path.

Config: OLLAMA_MODEL from HERMES.local.md (or HERMES_OLLAMA_MODEL env);
        HERMES_OLLAMA_URL env overrides the default localhost endpoint.

CLI:
    python3 ollama_client.py status
    python3 ollama_client.py chat "<prompt>" [--model NAME] [--system TEXT]
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(HERMES_ROOT))
import brain

OLLAMA_URL = os.environ.get("HERMES_OLLAMA_URL", "http://localhost:11434")
LOCAL_CONFIG = HERMES_ROOT / "HERMES.local.md"


def load_local_model() -> str:
    """OLLAMA_MODEL from HERMES.local.md; env HERMES_OLLAMA_MODEL wins.
    Returns "" when unset — callers must treat that as 'Tier 2 not
    configured', not guess a model name."""
    env = os.environ.get("HERMES_OLLAMA_MODEL")
    if env:
        return env
    if LOCAL_CONFIG.exists():
        m = re.search(r"^OLLAMA_MODEL:\s*(\S+)", LOCAL_CONFIG.read_text(), re.MULTILINE)
        if m and not m.group(1).startswith("<"):  # "<set-your-local-model-name>" placeholder
            return m.group(1)
    return ""


def _post(endpoint: str, payload: dict, timeout: float):
    req = urllib.request.Request(
        f"{OLLAMA_URL}{endpoint}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def is_available(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout):
            return True
    except (urllib.error.URLError, OSError):
        return False


def status() -> dict:
    model = load_local_model()
    up = is_available()
    return {
        "ollama_url": OLLAMA_URL,
        "reachable": up,
        "configured_model": model or None,
        "tier2_ready": bool(up and model),
        "note": None if (up and model) else
                ("Ollama unreachable — start it with `ollama serve`" if not up else
                 "no OLLAMA_MODEL set in HERMES.local.md — Tier 2 routing has no target"),
    }


def chat(prompt: str, model: str = None, system: str = None, timeout: float = 300.0) -> dict:
    """One Tier 2 completion. Returns {content, model, tokens, latency_ms} —
    the same fields Apollo needs for brain.py log / ReasoningBank log.
    Raises RuntimeError with an actionable message on any refusal/failure;
    never silently substitutes a different tier or model."""
    model = model or load_local_model()
    if not model:
        raise RuntimeError("Tier 2 dispatch refused: no model given and no OLLAMA_MODEL "
                           "in HERMES.local.md. Set it, or pass --model.")

    allowed, reason = brain.check_model_allowed(2, model, via="local")
    if not allowed:
        raise RuntimeError(f"Tier 2 dispatch refused by brain.py: {reason}")

    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    start = time.monotonic()
    try:
        data = _post("/api/chat", {"model": model, "messages": messages, "stream": False}, timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Ollama rejected the request ({e.code}): {body} — "
                           f"is '{model}' pulled? (`ollama pull {model}`)")
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"Ollama unreachable at {OLLAMA_URL} ({e}) — Tier 2 is down. "
                           f"Do NOT silently retry on Tier 1 if the task is running "
                           f"local-only for sensitivity reasons; surface this to the user.")
    latency_ms = int((time.monotonic() - start) * 1000)

    return {
        "content": data.get("message", {}).get("content", ""),
        "model": data.get("model", model),
        "tokens": int(data.get("prompt_eval_count", 0)) + int(data.get("eval_count", 0)),
        "latency_ms": latency_ms,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "chat"):
        print("usage: ollama_client.py status | chat \"<prompt>\" [--model NAME] [--system TEXT]",
              file=sys.stderr)
        sys.exit(2)
    if sys.argv[1] == "status":
        print(json.dumps(status(), indent=2))
        sys.exit(0)

    args = sys.argv[2:]
    if not args:
        print("chat requires a prompt", file=sys.stderr)
        sys.exit(2)
    prompt, model, system = args[0], None, None
    rest = args[1:]
    while rest:
        if rest[0] == "--model" and len(rest) > 1:
            model, rest = rest[1], rest[2:]
        elif rest[0] == "--system" and len(rest) > 1:
            system, rest = rest[1], rest[2:]
        else:
            print(f"unknown argument: {rest[0]}", file=sys.stderr)
            sys.exit(2)
    try:
        result = chat(prompt, model=model, system=system)
    except RuntimeError as e:
        print(f"ollama_client.py: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2))
