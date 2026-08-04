#!/usr/bin/env python3
"""
scripts/install_statusline.py — one-time installer for Clio's statusLine.

Why this exists: Claude Code's statusLine hook can only be configured in
*your* ~/.claude/settings.json (user-level, global) or a project's
.claude/settings.json (scoped to just that project). A plugin's own
manifest cannot ship a default statusLine — confirmed against
code.claude.com/docs/en/plugins-reference, which lists only `agent` and
`subagentStatusLine` as supported keys in a plugin's settings.json. So
HERMES cannot silently register this just by being enabled; one command
has to write the one line into your global config, once.

This is why it has to be user-level, not project-level: HERMES is meant to
run as a plugin inside *other* projects, not just live in this repo. An
earlier version of this pointed at ${CLAUDE_PROJECT_DIR}, which only
resolves correctly while this repo itself is the open project — the moment
HERMES is enabled somewhere else, that path breaks silently. This script
resolves its own absolute location instead, so the statusLine entry it
writes works regardless of which project you have open afterward.

Run it once, from anywhere, as long as this repo is on disk:
  python3 scripts/install_statusline.py

It merges a statusLine entry into ~/.claude/settings.json — it does not
overwrite the file, every other key you already have stays untouched.
"""
import json
import os
import stat
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
STATUSLINE_SCRIPT = HERMES_ROOT / "clio" / "statusline.py"
GLOBAL_SETTINGS = Path.home() / ".claude" / "settings.json"


def main():
    if not STATUSLINE_SCRIPT.exists():
        print(f"ERROR: {STATUSLINE_SCRIPT} not found. Run this from inside the HERMES repo.", file=sys.stderr)
        sys.exit(1)

    # chmod +x
    mode = os.stat(STATUSLINE_SCRIPT).st_mode
    os.chmod(STATUSLINE_SCRIPT, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    GLOBAL_SETTINGS.parent.mkdir(parents=True, exist_ok=True)

    if GLOBAL_SETTINGS.exists():
        try:
            settings = json.loads(GLOBAL_SETTINGS.read_text())
        except json.JSONDecodeError:
            print(f"ERROR: {GLOBAL_SETTINGS} exists but isn't valid JSON. Fix it by hand first, nothing written.", file=sys.stderr)
            sys.exit(1)
    else:
        settings = {}

    existing = settings.get("statusLine")
    if existing and existing.get("command") and "clio/statusline.py" not in existing["command"]:
        print(f"NOTE: {GLOBAL_SETTINGS} already has a different statusLine configured:")
        print(f"  {existing}")
        print("Overwriting it with HERMES's. If that's wrong, edit the file by hand afterward.")

    settings["statusLine"] = {
        "type": "command",
        "command": f'python3 "{STATUSLINE_SCRIPT}"',
    }

    GLOBAL_SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"Wrote statusLine to {GLOBAL_SETTINGS}, pointing at:")
    print(f"  {STATUSLINE_SCRIPT}")
    print("This is now global — it'll run in the Claude Code CLI terminal in any project, not just this one.")
    print("Start a new `claude` session to pick it up (statusLine loads at session start).")


if __name__ == "__main__":
    main()
