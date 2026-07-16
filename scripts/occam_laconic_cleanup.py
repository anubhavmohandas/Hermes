#!/usr/bin/env python3
"""
scripts/occam_laconic_cleanup.py — removes state Occam/Laconic write
outside the plugin's own tracked files: the two mode flags, Occam's
external config dir, and (if present) the statusLine entry
meta/occam.py's nudge helped the user add to settings.json.

Ported from the source project's own scripts/uninstall.js — same shape
(best-effort, leaves anything it doesn't own untouched, only removes its
own statusLine segment if the user combined it with something else).

Plugin files themselves are removed by `/plugin remove hermes` or deleting
the checkout; this only cleans up what that can't see.

CLI: python3 scripts/occam_laconic_cleanup.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meta import occam  # noqa: E402
from meta import laconic  # noqa: E402

STATUSLINE_SCRIPT = "hermes_statusline.sh"


def _remove_if_exists(path: Path, label: str) -> None:
    try:
        path.unlink()
        print(f"Removed {label}: {path}")
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"Could not remove {label} ({path}): {e}", file=sys.stderr)


def _clean_statusline(settings_path: Path) -> None:
    try:
        raw = settings_path.read_text(encoding="utf-8").lstrip("﻿")
        settings = json.loads(raw)
    except FileNotFoundError:
        return
    except json.JSONDecodeError as e:
        print(
            f"settings.json is malformed — could not remove the HERMES statusLine "
            f"entry. Remove it manually from: {settings_path} ({e})",
            file=sys.stderr,
        )
        return

    status_line = settings.get("statusLine")
    cmd = status_line.get("command") if isinstance(status_line, dict) else None
    if not isinstance(cmd, str) or STATUSLINE_SCRIPT not in cmd:
        return

    parts = [p.strip() for p in cmd.replace(";", "&&").split("&&") if p.strip()]
    others = [p for p in parts if STATUSLINE_SCRIPT not in p]
    if not others:
        del settings["statusLine"]
        print(f"Removed HERMES statusLine entry from {settings_path}")
    else:
        settings["statusLine"]["command"] = " && ".join(others)
        print(f"Removed HERMES statusLine segment from {settings_path}")
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def main() -> None:
    _remove_if_exists(occam.FLAG_PATH, "occam mode flag")
    _remove_if_exists(laconic.FLAG_PATH, "laconic mode flag")
    _remove_if_exists(occam._external_config_dir() / "config.json", "occam config file")

    settings_path = occam._config_dir() / "settings.json"
    _clean_statusline(settings_path)


if __name__ == "__main__":
    main()
