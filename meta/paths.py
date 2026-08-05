#!/usr/bin/env python3
"""
meta/paths.py — where HERMES keeps runtime state.

HERMES is a globally-installed plugin: it assists whatever project the user
is actually working in, and its own code lives in a version-pinned cache
directory (~/.claude/plugins/cache/hermes/hermes/<version>/). Anything
written *inside* that directory is deleted the next time the plugin
updates — which previously included the Mnemos vault, every log, the
kanban board, and the reasoning bank.

So runtime state goes next to the user's Claude config, not next to the
code:

    ${CLAUDE_CONFIG_DIR:-~/.claude}/hermes/<same relative path as before>

The relative layout is preserved (logs/, mnemos/vault/, curator/pending/),
so only the root moves. meta/occam.py already resolved CLAUDE_CONFIG_DIR
this way for its mode flag — that is why Occam survived plugin updates and
Mnemos did not. This module generalises that one resolver.

Migration is lazy and one-way: the first call for a path that still has an
in-repo copy moves it across. Existing destination data is never
overwritten.

Self-check:  python3 meta/paths.py
"""
import os
import shutil
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent


def config_dir() -> Path:
    """User's Claude config dir. CLAUDE_CONFIG_DIR overrides ~/.claude,
    matching meta/occam.py._config_dir() and hooks/hermes_statusline.sh."""
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(d) if d else Path.home() / ".claude"


def data_dir() -> Path:
    """Root for all HERMES runtime state. Survives plugin updates."""
    return config_dir() / "hermes"


def _migrate(legacy: Path, new: Path) -> None:
    """Move a pre-existing in-repo copy to the durable location, once.

    Directories are migrated by *contents*, not wholesale: several state
    dirs (curator/pending, mnemos/vault) hold a git-tracked `.gitkeep`,
    and moving the directory itself would show up as a deleted tracked
    file in anyone developing against the repo. The placeholder stays put.

    Never overwrites an existing destination. A failure here is reported
    but not raised — the old copy staying where it is is recoverable,
    crashing a status line or a hook is not."""
    try:
        if legacy.is_dir():
            # Refusing to migrate a directory that holds source is a hard
            # guard, not caution: several modules (reasoningbank/, clio/,
            # curator/) keep their state right next to their own .py files,
            # and a directory-level migration there would carry the module's
            # code out of the repo. Name such state per-file instead.
            if any(c.suffix == ".py" for c in legacy.iterdir()):
                raise ValueError(
                    f"{legacy} contains source files — migrate its state "
                    f"per-file with state_file() instead of state_dir()")
            new.mkdir(parents=True, exist_ok=True)
            for entry in sorted(legacy.iterdir()):
                if entry.name == ".gitkeep":
                    continue
                dest = new / entry.name
                if not dest.exists():
                    shutil.move(str(entry), str(dest))
            return
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(new))
    except (OSError, shutil.Error) as e:
        # occam: last-writer-wins on a concurrent migration — two processes
        # can both see `new` missing, and the loser lands here. The winner's
        # data is intact and the loser's legacy copy is left untouched for a
        # human to reconcile. Add a lockfile if that ever actually races.
        print(f"hermes/paths: could not migrate {legacy} -> {new} ({e})",
              file=sys.stderr)


def _resolve(parts) -> Path:
    rel = Path(*parts)
    new = data_dir() / rel
    if not new.exists():
        legacy = HERMES_ROOT / rel
        if legacy.exists():
            _migrate(legacy, new)
    return new


def state_dir(*parts: str) -> Path:
    """Durable path for a state *directory*, created if absent."""
    p = _resolve(parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_file(*parts: str) -> Path:
    """Durable path for a state *file*. The file itself is not created,
    but its parent directory is — callers that open() for append or hand
    the path to sqlite3 would otherwise fail on a fresh install."""
    p = _resolve(parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_env() -> None:
    """Load KEY=value pairs from the durable .env (~/.claude/hermes/.env)
    into os.environ, so secrets like NVIDIA_API_KEY survive across every
    new terminal instead of needing `export` each session. `setdefault`
    only — an explicit shell `export` always wins over the file. Plain
    KEY=value parsing, no quoting/interpolation rules: that's the whole
    reason this doesn't need python-dotenv as a dependency."""
    env_file = state_file(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def demo():
    """Self-check.

    Uses only `_selfcheck_*` relative paths. This is not cosmetic: an
    earlier version of this demo asked for "logs/reasoning_seed.jsonl",
    and because migration is real, it MOVED the live log into the
    throwaway tempdir, which was then deleted. Any name used here must be
    one that cannot exist under HERMES_ROOT for real."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CLAUDE_CONFIG_DIR"] = tmp
        root = Path(tmp) / "hermes"

        assert data_dir() == root, data_dir()

        # a file's parent is created; the file is not
        f = state_file("_selfcheck_logs", "trace.jsonl")
        assert f == root / "_selfcheck_logs" / "trace.jsonl", f
        assert f.parent.is_dir() and not f.exists()

        # a directory is created outright
        d = state_dir("_selfcheck_curator", "pending")
        assert d.is_dir(), d

        # migration moves an in-repo copy across, once
        legacy = HERMES_ROOT / "_selfcheck_migrate"
        legacy.mkdir(exist_ok=True)
        try:
            (legacy / "old.txt").write_text("carried over")
            moved = state_dir("_selfcheck_migrate")
            assert (moved / "old.txt").read_text() == "carried over"
            # the directory shell stays (see _migrate), but is emptied of content
            assert not (legacy / "old.txt").exists(), "content should have moved"
        finally:
            shutil.rmtree(legacy, ignore_errors=True)

        # existing destination data is never clobbered by a stale legacy copy
        keep = state_file("_selfcheck_keep", "keep.txt")
        keep.write_text("do not overwrite")
        legacy2 = HERMES_ROOT / "_selfcheck_keep"
        legacy2.mkdir(exist_ok=True)
        try:
            (legacy2 / "keep.txt").write_text("stale")
            assert state_file("_selfcheck_keep", "keep.txt").read_text() == "do not overwrite"
            assert legacy2.exists(), "legacy copy stays put when destination exists"
        finally:
            shutil.rmtree(legacy2, ignore_errors=True)

        # a directory holding source is refused outright, not silently moved
        legacy_code = HERMES_ROOT / "_selfcheck_code"
        legacy_code.mkdir(exist_ok=True)
        try:
            (legacy_code / "mod.py").write_text("# source")
            (legacy_code / "state.jsonl").write_text("{}\n")
            try:
                state_dir("_selfcheck_code")
                raise AssertionError("should have refused a source directory")
            except ValueError:
                pass
            assert (legacy_code / "mod.py").exists(), "source must not move"
        finally:
            shutil.rmtree(legacy_code, ignore_errors=True)

        # a git-tracked .gitkeep is left behind, everything else moves
        legacy3 = HERMES_ROOT / "_selfcheck_gitkeep"
        legacy3.mkdir(exist_ok=True)
        try:
            (legacy3 / ".gitkeep").write_text("")
            (legacy3 / "real.json").write_text("{}")
            moved3 = state_dir("_selfcheck_gitkeep")
            assert (moved3 / "real.json").exists(), "content should migrate"
            assert not (moved3 / ".gitkeep").exists(), ".gitkeep should not migrate"
            assert (legacy3 / ".gitkeep").exists(), "tracked placeholder stays in repo"
            assert not (legacy3 / "real.json").exists(), "content should have moved"
        finally:
            shutil.rmtree(legacy3, ignore_errors=True)

    print("meta/paths.py: ok")


if __name__ == "__main__":
    demo()
