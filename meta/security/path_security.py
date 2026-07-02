#!/usr/bin/env python3
"""
path_security.py — Layer 2/7: path traversal check.
Any file operation must resolve inside an allowed base directory.
Pattern: Path.resolve().relative_to() — raises ValueError if outside base.
Reimplemented fresh from pattern (hermes-agent P16). No source copied.
"""
import sys
from pathlib import Path


def check_traversal(base_dir: str, requested_path: str):
    """Returns (safe: bool, resolved_path_or_reason: str)."""
    try:
        base = Path(base_dir).resolve()
        target = (base / requested_path).resolve() if not Path(requested_path).is_absolute() \
            else Path(requested_path).resolve()
        target.relative_to(base)
        return True, str(target)
    except ValueError:
        return False, f"BLOCKED: '{requested_path}' resolves outside base dir '{base_dir}' (path traversal)"
    except Exception as e:
        return False, f"BLOCKED: could not resolve path — {e}"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: path_security.py <base_dir> <requested_path>", file=sys.stderr)
        sys.exit(2)
    safe, msg = check_traversal(sys.argv[1], sys.argv[2])
    print(msg)
    sys.exit(0 if safe else 1)
