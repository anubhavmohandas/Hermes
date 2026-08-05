#!/usr/bin/env python3
"""
nvidia_client.py — Tier 2 model dispatch. The piece that makes "multi-model"
true instead of a label (2026-07-02 gap analysis, B0): brain.py classifies a
task as Tier 2, and until this file existed nothing consumed that verdict —
every sub-skill ran on Claude regardless.

Tier 2 is the NVIDIA API (integrate.api.nvidia.com, OpenAI-compatible chat
completions) — the bulk/cost-sensitive tier. It is a REMOTE cloud API: unlike
the retired local-Ollama Tier 2, data DOES leave the machine, so sensitive
tasks are no longer permitted here (brain.get_tier routes sensitive -> Tier 1
unconditionally).

Flow (mirrors SKILL.md §2):
    brain.py check --task ...           -> tier
    if tier == 2: nvidia_client.chat(...)

Enforcement is NOT re-implemented here — this calls the same brain.py
functions the hook path uses: check_model_allowed(2, model) before every call
(the Chinese-API exclusion is the single seam).

Stdlib only (urllib): no third-party HTTP dep for the core dispatch path.

Config: NVIDIA_API_KEY env (required); NVIDIA_MODEL from HERMES.local.md
        (or HERMES_NVIDIA_MODEL env); HERMES_NVIDIA_URL env overrides the
        default https://integrate.api.nvidia.com endpoint.

CLI:
    python3 nvidia_client.py status
    python3 nvidia_client.py chat "<prompt>" [--model NAME] [--system TEXT]
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
from meta.paths import load_env
load_env()  # pulls NVIDIA_API_KEY etc. from ~/.claude/hermes/.env if not already set

NVIDIA_URL = os.environ.get("HERMES_NVIDIA_URL", "https://integrate.api.nvidia.com")

# Your settings, not source: HERMES is installed globally and assists whatever
# project you're in, so its config lives at ~/.claude/hermes/HERMES.local.md
# rather than inside the plugin's version-pinned install dir. A copy sitting in
# a dev checkout is migrated across on first read (meta/paths.py).
from meta.paths import state_file  # noqa: E402
LOCAL_CONFIG = state_file("HERMES.local.md")


def api_key() -> str:
    return os.environ.get("NVIDIA_API_KEY", "")


def load_local_model() -> str:
    """NVIDIA_MODEL from HERMES.local.md; env HERMES_NVIDIA_MODEL wins.
    Returns "" when unset — callers must treat that as 'Tier 2 not
    configured', not guess a model name."""
    env = os.environ.get("HERMES_NVIDIA_MODEL")
    if env:
        return env
    if LOCAL_CONFIG.exists():
        m = re.search(r"^NVIDIA_MODEL:\s*(\S+)", LOCAL_CONFIG.read_text(), re.MULTILINE)
        if m and not m.group(1).startswith("<"):  # "<set-your-nvidia-model-name>" placeholder
            return m.group(1)
    return ""


def _post(endpoint: str, payload: dict, timeout: float):
    req = urllib.request.Request(
        f"{NVIDIA_URL}{endpoint}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key()}"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def is_available(timeout: float = 30.0) -> bool:
    """True only when the key actually authenticates FOR INFERENCE.

    Deliberately not a /v1/models probe. That endpoint answers HTTP 200 with
    no Authorization header at all (verified 2026-08-05), so it proves the
    host is up and nothing whatsoever about the credentials — a key that 401s
    on every chat call still scored `reachable: true` there, and Apollo gates
    Tier 2 dispatch on this result (SKILL.md §61). A readiness check has to
    exercise the path it gates, so this sends the smallest real completion
    (max_tokens=1) instead. Costs a token per probe; that is the price of an
    answer that isn't a guess.
    """
    model = load_local_model()
    if not api_key() or not model:
        return False
    try:
        _post("/v1/chat/completions",
              {"model": model, "messages": [{"role": "user", "content": "hi"}],
               "max_tokens": 1, "stream": False}, timeout)
        return True
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return False


def status() -> dict:
    model = load_local_model()
    key = bool(api_key())
    up = is_available() if key else False
    return {
        "nvidia_url": NVIDIA_URL,
        "api_key_set": key,
        "reachable": up,
        "configured_model": model or None,
        "tier2_ready": bool(key and up and model),
        "note": None if (key and up and model) else
                ("no NVIDIA_API_KEY in the environment — Tier 2 has no credentials" if not key else
                 "no NVIDIA_MODEL set in HERMES.local.md — Tier 2 routing has no target" if not model else
                 f"NVIDIA API unreachable or key rejected at {NVIDIA_URL} — the probe "
                 f"completion for '{model}' did not succeed; check network, key validity, "
                 f"and that the key's account has access to this model"),
    }


def chat(prompt: str, model: str = None, system: str = None, timeout: float = 300.0) -> dict:
    """One Tier 2 completion. Returns {content, model, tokens, latency_ms} —
    the same fields Apollo needs for brain.py log / ReasoningBank log.
    Raises RuntimeError with an actionable message on any refusal/failure;
    never silently substitutes a different tier or model."""
    model = model or load_local_model()
    if not model:
        raise RuntimeError("Tier 2 dispatch refused: no model given and no NVIDIA_MODEL "
                           "in HERMES.local.md. Set it, or pass --model.")
    if not api_key():
        raise RuntimeError("Tier 2 dispatch refused: NVIDIA_API_KEY is not set in the "
                           "environment.")

    allowed, reason = brain.check_model_allowed(2, model)
    if not allowed:
        raise RuntimeError(f"Tier 2 dispatch refused by brain.py: {reason}")

    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    start = time.monotonic()
    try:
        data = _post("/v1/chat/completions",
                     {"model": model, "messages": messages, "stream": False}, timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        hint = " — is NVIDIA_API_KEY valid?" if e.code in (401, 403) else \
               (f" — is '{model}' a valid NVIDIA API model id?" if e.code == 404 else "")
        raise RuntimeError(f"NVIDIA API rejected the request ({e.code}): {body}{hint}")
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"NVIDIA API unreachable at {NVIDIA_URL} ({e}) — Tier 2 is down. "
                           f"Do NOT silently retry on another tier; surface this to the user.")
    latency_ms = int((time.monotonic() - start) * 1000)

    choices = data.get("choices") or [{}]
    usage = data.get("usage") or {}
    return {
        "content": choices[0].get("message", {}).get("content", ""),
        "model": data.get("model", model),
        "tokens": int(usage.get("total_tokens", 0)),
        "latency_ms": latency_ms,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "chat"):
        print("usage: nvidia_client.py status | chat \"<prompt>\" [--model NAME] [--system TEXT]",
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
        print(f"nvidia_client.py: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2))
