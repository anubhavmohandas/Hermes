#!/usr/bin/env python3
"""
meta/upstream_tracker.py — upstream source-repo drift tracker (Phase 3D).

Pattern source (reimplemented fresh, no code copied): v1 blueprint's
"GitHub-API commit-hash diff on source repos, human-review only". The 58
extraction repos HERMES's patterns came from keep moving; this notices when
one has new commits so the HUMAN can decide whether re-extraction is worth
it. It reports hashes. It never fetches code, never diffs file contents,
never applies anything (Invariant #3 — and #4: patterns, not code, so there
is deliberately no "pull" subcommand to misuse).

State: meta/upstreams.json — {"owner/repo": {"last_seen_sha": ..., ...}}.
Network: GitHub REST /repos/{repo}/commits?per_page=1 via stdlib urllib
(anonymous, 60 req/h — fine for a personal watchlist; GITHUB_TOKEN env is
honored if present for the 5000 req/h limit). Offline or rate-limited =>
that repo reports "unreachable", the run continues (Invariant #5).

CLI:
    python3 meta/upstream_tracker.py watch <owner/repo>
    python3 meta/upstream_tracker.py unwatch <owner/repo>
    python3 meta/upstream_tracker.py check          # network; reports drift
    python3 meta/upstream_tracker.py ack <owner/repo>   # human reviewed it
    python3 meta/upstream_tracker.py list
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT))
from meta.paths import state_file  # noqa: E402

# Generated, not shipped (untracked in git) — so it is runtime state and
# belongs under ~/.claude/hermes/ with the rest. See meta/paths.py.
STATE_PATH = state_file("meta", "upstreams.json")
API_BASE = "https://api.github.com"
TIMEOUT_SECONDS = 15


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def _save(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def _fetch_head(repo: str, fetcher=None):
    """Returns (sha, date, err). `fetcher` is injectable for offline tests."""
    if fetcher is not None:
        return fetcher(repo)
    url = f"{API_BASE}/repos/{repo}/commits?per_page=1"
    headers = {"User-Agent": "HERMES-upstream-tracker/1.0",
               "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS,
                                    context=_ssl_context()) as resp:
            body = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return None, None, f"unreachable: {e}"
    if not isinstance(body, list) or not body:
        return None, None, "no commits visible (empty or private repo)"
    head = body[0]
    return head.get("sha"), head.get("commit", {}).get("committer", {}).get("date"), None


def watch(repo: str):
    state = _load()
    if repo in state:
        return {"watched": False, "repo": repo, "reason": "already watched"}
    state[repo] = {"last_seen_sha": None, "added": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _save(state)
    return {"watched": True, "repo": repo,
            "note": "run `check` to baseline the current head, then `ack` it"}


def unwatch(repo: str):
    state = _load()
    existed = state.pop(repo, None) is not None
    _save(state)
    return {"unwatched": existed, "repo": repo}


def check(fetcher=None):
    """Compare each watched repo's live head to last_seen_sha. Drift is
    REPORTED, never acted on — `ack` (a human) moves the pointer."""
    state = _load()
    report = []
    for repo, info in sorted(state.items()):
        sha, date, err = _fetch_head(repo, fetcher)
        if err:
            report.append({"repo": repo, "status": "unreachable", "detail": err})
            continue
        last = info.get("last_seen_sha")
        if last is None:
            info["candidate_sha"] = sha
            report.append({"repo": repo, "status": "unbaselined",
                           "head": sha[:12], "head_date": date,
                           "action": f"ack {repo} to baseline"})
        elif sha != last:
            info["candidate_sha"] = sha
            report.append({"repo": repo, "status": "DRIFT",
                           "last_seen": last[:12], "head": sha[:12],
                           "head_date": date,
                           "action": f"review upstream, then ack {repo}"})
        else:
            report.append({"repo": repo, "status": "unchanged", "head": sha[:12]})
    _save(state)
    return {"checked": len(report), "drifted": sum(1 for r in report if r["status"] == "DRIFT"),
            "report": report}


def ack(repo: str):
    """Human reviewed the upstream — advance the pointer to the candidate
    recorded by the last check. No candidate, no move (ack can't invent)."""
    state = _load()
    if repo not in state:
        return {"acked": False, "repo": repo, "reason": "not watched"}
    candidate = state[repo].get("candidate_sha")
    if not candidate:
        return {"acked": False, "repo": repo,
                "reason": "no candidate sha — run `check` first"}
    state[repo]["last_seen_sha"] = candidate
    state[repo]["acked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state[repo].pop("candidate_sha", None)
    _save(state)
    return {"acked": True, "repo": repo, "last_seen_sha": candidate[:12]}


def list_watched():
    return _load()


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "watch":
        print(json.dumps(watch(args[1]), indent=2))
    elif len(args) >= 2 and args[0] == "unwatch":
        print(json.dumps(unwatch(args[1]), indent=2))
    elif args and args[0] == "check":
        print(json.dumps(check(), indent=2))
    elif len(args) >= 2 and args[0] == "ack":
        print(json.dumps(ack(args[1]), indent=2))
    elif args and args[0] == "list":
        print(json.dumps(list_watched(), indent=2))
    else:
        print("usage: upstream_tracker.py watch|unwatch|ack <owner/repo> | check | list",
              file=sys.stderr)
        sys.exit(2)
