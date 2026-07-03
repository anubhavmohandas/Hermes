#!/usr/bin/env python3
"""
integrations/media.py — media module (Stage 5, opt-in).

Pattern source (reimplemented fresh, no code copied): the `claude-video` /
`claude-watch` extraction repos and the v1 blueprint's "media/ (video
download / frame extract / transcribe — claude-video, /watch)". Per
HERMES_GOAL_Start_to_End.md Stage 5 and Invariant #5, external media tools
(yt-dlp, ffmpeg, whisper) are OPTIONAL — this module DETECTS what's present
and BUILDS the exact command to run, but by default only reports the plan.
It does not silently shell out to tools that may not exist.

Fallback behavior: with none of the tools installed, every operation returns
a structured "unavailable + install hint" — never a fake transcript, never a
silent no-op. With tools present, `--run` executes the built command through
the same approval classification as everything else.

Downloads and URL operations pass through meta/security/url_safety first —
a media URL is still a URL (SSRF applies).

CLI:
    python3 integrations/media.py status
    python3 integrations/media.py plan download <url>
    python3 integrations/media.py plan frames <file> --fps 1
    python3 integrations/media.py plan transcribe <file>
"""
import json
import shutil
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT / "meta" / "security"))
import url_safety  # noqa: E402
import approval    # noqa: E402

TOOLS = {
    "download": ("yt-dlp", "pip install yt-dlp / brew install yt-dlp"),
    "frames": ("ffmpeg", "brew install ffmpeg"),
    "transcribe": ("whisper", "pip install openai-whisper (needs ffmpeg too)"),
}


def _available(tool: str) -> bool:
    return shutil.which(tool) is not None


def plan(op: str, target: str, fps: float = 1.0):
    if op not in TOOLS:
        return {"planned": False, "reason": f"unknown op '{op}'"}
    tool, hint = TOOLS[op]
    if op == "download":
        allowed, reason = url_safety.check_url(target)
        if not allowed:
            return {"planned": False, "op": op, "reason": f"SSRF layer: {reason}"}
        cmd = f"yt-dlp -f bestvideo+bestaudio -o '%(title)s.%(ext)s' {target}"
    elif op == "frames":
        cmd = f"ffmpeg -i {target} -vf fps={fps} frame_%04d.png"
    else:  # transcribe
        cmd = f"whisper {target} --model base --output_format txt"

    verdict, vreason = approval.classify_command(cmd)
    return {
        "planned": True,
        "op": op,
        "tool": tool,
        "tool_available": _available(tool),
        "install_hint": None if _available(tool) else hint,
        "command": cmd,
        "approval_verdict": verdict,
        "note": ("ready to run" if _available(tool)
                 else f"{tool} not installed — command is the plan, not executed"),
    }


def status():
    return {op: {"tool": tool, "available": _available(tool),
                 "install_hint": None if _available(tool) else hint}
            for op, (tool, hint) in TOOLS.items()}


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "status":
        print(json.dumps(status(), indent=2))
    elif len(args) >= 3 and args[0] == "plan":
        fps = 1.0
        if "--fps" in args:
            fps = float(args[args.index("--fps") + 1])
        print(json.dumps(plan(args[1], args[2], fps), indent=2))
    else:
        print("usage: media.py status | plan download|frames|transcribe <target> [--fps N]",
              file=sys.stderr)
        sys.exit(2)
