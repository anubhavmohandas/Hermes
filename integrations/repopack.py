#!/usr/bin/env python3
"""
integrations/repopack.py — codebase packing + reviewer fan-out (Stage 5, opt-in).

Pattern source (reimplemented fresh, no code copied): the v1 blueprint's
`repomix/` module — "Pack repo for AI analysis, security/perf/quality
review" with 6 reviewer agents. This is the repomix CONCEPT rebuilt in
stdlib Python (Invariant #4): walk a repo, emit ONE reviewable markdown
file with a tree summary and fenced file contents, secrets redacted; then
optionally fan the six reviewer lenses out through delegation/dispatch.py
(≤3 concurrent, the locked cap).

Fallbacks (Invariant #5): packing needs nothing beyond stdlib; review
fan-out needs the `claude` CLI and degrades to printing the six prompts
for manual use when it's absent.

CLI:
    python3 integrations/repopack.py pack <root> [--out packed.md]
                                     [--max-file-kb 64] [--max-total-mb 4]
    python3 integrations/repopack.py reviewers
    python3 integrations/repopack.py review <packed.md> [--dry-run] [--lenses security,tests]
"""
import argparse
import json
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT / "meta" / "security"))
sys.path.insert(0, str(HERMES_ROOT / "delegation"))
import redact  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", ".next", ".cache", "coverage", ".pytest_cache", "vault"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip",
                 ".gz", ".tar", ".whl", ".so", ".dylib", ".bin", ".db",
                 ".sqlite", ".lock", ".woff", ".woff2", ".ttf", ".mp4", ".mov"}
LANG_BY_SUFFIX = {".py": "python", ".ts": "typescript", ".tsx": "tsx",
                  ".js": "javascript", ".jsx": "jsx", ".sh": "bash",
                  ".md": "markdown", ".json": "json", ".yaml": "yaml",
                  ".yml": "yaml", ".css": "css", ".html": "html",
                  ".sql": "sql", ".go": "go", ".rs": "rust", ".c": "c",
                  ".cpp": "cpp", ".swift": "swift", ".rb": "ruby"}

# The six reviewer lenses — v1's "6 reviewer agents", as dispatchable prompts.
REVIEWERS = {
    "security": "Review the packed codebase below for SECURITY issues only: injection, "
                "path traversal, SSRF (host/protocol-controlled), secrets in code, unsafe "
                "deserialization, missing authz at trust boundaries. Trace untrusted "
                "input → dangerous sink. Report file:line, severity, data flow, and a fix. "
                "Apply the /security-review discipline (commands/security-review.md): drop "
                "any finding below 8/10 confidence and honor the 14 hard exclusions (no "
                "DoS, no rate-limiting, no outdated-deps, no memory-safety in memory-safe "
                "langs, no path-only SSRF, no test-file-only findings, etc.). Better silent "
                "than noisy. No style comments.",
    "performance": "Review the packed codebase below for PERFORMANCE issues only: "
                   "quadratic scans, repeated I/O in loops, unbounded memory growth, "
                   "missing caching where results repeat. Report file:line, expected "
                   "impact, and a concrete fix. No speculation without evidence in code.",
    "quality": "Review the packed codebase below for CORRECTNESS bugs only: logic errors, "
               "unhandled edge cases (empty/None/unicode), swallowed exceptions, dead or "
               "unreachable code, doc/code drift. Report file:line + failure scenario.",
    "architecture": "Review the packed codebase below for ARCHITECTURE issues: modules "
                    "that reach into each other's internals, missing seams, duplicated "
                    "concepts, dependency direction violations. Report the 3-5 highest-"
                    "leverage changes with justification — not a laundry list.",
    "tests": "Review the packed codebase below for TEST GAPS: code paths with behavior "
             "but no test (name the specific untested branch), tests that can't fail, "
             "tests coupled to implementation detail. Propose the 5 most valuable "
             "missing test cases with names.",
    "docs": "Review the packed codebase below for DOC issues: claims that contradict the "
            "code, missing setup steps a fresh machine would hit, stale references to "
            "renamed/removed things. Report doc-location → code-evidence pairs only.",
}


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS or part.startswith(".") and part not in (".claude-plugin",)
               for part in path.relative_to(root).parts[:-1]):
            continue
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        yield path


def pack(root: Path, out_path: Path, max_file_kb: int = 64,
         max_total_mb: int = 4) -> dict:
    root = root.resolve()
    if not root.is_dir():
        return {"packed": False, "reason": f"not a directory: {root}"}
    max_file = max_file_kb * 1024
    max_total = max_total_mb * 1024 * 1024
    sections, tree, total, truncated, skipped_binary = [], [], 0, [], 0
    for path in _iter_files(root):
        rel = path.relative_to(root)
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:1024]:
            skipped_binary += 1
            continue
        text = raw.decode("utf-8", errors="replace")
        if len(text) > max_file:
            text = text[:max_file] + f"\n… [truncated at {max_file_kb}KB]\n"
            truncated.append(str(rel))
        if total + len(text) > max_total:
            truncated.append(f"[PACK CAP HIT at {max_total_mb}MB — remaining files listed in tree only]")
            tree.append(str(rel))
            continue
        total += len(text)
        tree.append(str(rel))
        lang = LANG_BY_SUFFIX.get(path.suffix.lower(), "")
        sections.append(f"\n## FILE: {rel}\n```{lang}\n{text}\n```\n")
    header = (f"# Repopack of {root.name}\n\n"
              f"{len(tree)} files, ~{total // 1024}KB text, ~{total // 4} tokens (est). "
              f"{skipped_binary} binaries skipped. Secrets redacted at pack time.\n\n"
              f"## Tree\n```\n" + "\n".join(tree) + "\n```\n")
    out_path.write_text(redact.redact(header + "".join(sections)))
    return {"packed": True, "out": str(out_path), "files": len(tree),
            "approx_tokens": total // 4, "truncated": truncated}


def review(pack_file: Path, lenses=None, dry_run: bool = False) -> dict:
    import dispatch
    if not pack_file.exists():
        return {"reviewed": False, "reason": f"pack file missing: {pack_file}"}
    chosen = [l for l in (lenses or REVIEWERS)] if lenses else list(REVIEWERS)
    unknown = [l for l in chosen if l not in REVIEWERS]
    if unknown:
        return {"reviewed": False, "reason": f"unknown lenses: {unknown}",
                "available": list(REVIEWERS)}
    prompts = [f"{REVIEWERS[l]}\n\nRead the packed codebase at: {pack_file.resolve()}"
               for l in chosen]
    result = dispatch.dispatch(prompts, timeout_seconds=900, dry_run=dry_run)
    return {"reviewed": result.get("dispatched", False) or dry_run,
            "lenses": chosen, **result}


def main():
    parser = argparse.ArgumentParser(prog="integrations/repopack.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pack = sub.add_parser("pack")
    p_pack.add_argument("root")
    p_pack.add_argument("--out", default="packed.md")
    p_pack.add_argument("--max-file-kb", type=int, default=64)
    p_pack.add_argument("--max-total-mb", type=int, default=4)

    sub.add_parser("reviewers")

    p_rev = sub.add_parser("review")
    p_rev.add_argument("pack_file")
    p_rev.add_argument("--dry-run", action="store_true")
    p_rev.add_argument("--lenses", default=None, help="comma-separated subset")

    args = parser.parse_args()
    if args.command == "pack":
        out = pack(Path(args.root), Path(args.out),
                   max_file_kb=args.max_file_kb, max_total_mb=args.max_total_mb)
    elif args.command == "reviewers":
        out = REVIEWERS
    else:
        lenses = args.lenses.split(",") if args.lenses else None
        out = review(Path(args.pack_file), lenses=lenses, dry_run=args.dry_run)
    print(json.dumps(out, indent=2))
    if isinstance(out, dict) and out.get("packed") is False or \
       isinstance(out, dict) and out.get("reviewed") is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
