#!/usr/bin/env python3
"""
integrations/synapse.py — codebase knowledge graph (Stage 5, opt-in, on demand).

Pattern source (reimplemented fresh, no code copied): Extractions/graphify —
a tree-sitter, 29-language, LLM-backed, NetworkX/Leiden-clustering tool with
an MCP server, git hooks, and six model backends. This is the one item
EXTRACTION_COVERAGE.md listed as a genuine open gap (⚠ graphify — deferred
until real need appears). "Implement now, use only when needed" (per the
2026-08-05 directive) means: reimplement the two actually-useful questions
— "which files import which" and "which functions call which" — with
stdlib only, not graphify's production/multi-user machinery. No tree-sitter
(needs per-language grammars), no NetworkX (a plain dict graph is enough at
this scale), no LLM fallback, no clustering, no MCP server. Python's own
`ast` module covers HERMES's own codebase, which is what this tool exists
to look at in the first place.

Fallback (Invariant #5): there isn't a degraded mode to fall back TO — this
is already the minimum. `ast` is stdlib, so nothing is ever "unavailable";
a file that fails to parse (syntax error, non-UTF8) is skipped and counted,
never crashes the run.

Scope, deliberately: calls resolve within a file, or to a name explicitly
brought in via `from X import Y` in that file — nothing smarter. A call to
something reached any other way (star imports, dynamic dispatch, re-exports)
is recorded as an `external:<name>` node rather than guessed at — graphify's
own confidence-tier system (EXTRACTED/INFERRED/AMBIGUOUS) exists to handle
exactly the ambiguity that real cross-file inference runs into; skipping it
is the point, not an oversight. Good enough to answer "what would break if I
change this" for a personal-project codebase; not a substitute for reading
the code. Two passes over the files (collect every definition + import
alias first, then resolve calls) so resolution doesn't depend on directory
scan order — a call in `caller.py` to something in `callee.py` must resolve
the same way whichever file happens to sort first.

Dormant until called (Stage 5 convention, SKILL.md §3): nothing here runs
on its own. Apollo routes to it only when a request actually asks for a
dependency map / call graph / "what calls this" / "what would break".

CLI:
    python3 integrations/synapse.py build [path] [--out FILE] [--top N]
    python3 integrations/synapse.py status
"""
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meta.paths import state_file  # noqa: E402

DEFAULT_GRAPH_PATH = state_file("integrations", "synapse_graph.json")


def _iter_py_files(root: Path):
    for p in sorted(root.rglob("*.py")):
        # occam: same exclusions as repopack.py's pack() — no point graphing
        # dependency caches or virtualenvs, they aren't "our" code
        if any(part in ("__pycache__", ".venv", "venv", "node_modules", ".git")
               for part in p.parts):
            continue
        yield p


def _module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join(parts) if parts else path.stem


class _FileVisitor(ast.NodeVisitor):
    """Walks one file's AST, tracking a scope stack so nested functions/
    methods get a qualified name (Class.method) instead of colliding.

    Two modes, same class (occam: one visitor, not two near-duplicates):
    `record_edges=False` (pass 1) only fills `local_defs` and this file's
    `import_aliases` — no edges yet, because a call may reference a def in
    a file not parsed yet. `record_edges=True` (pass 2) does the real work,
    with `local_defs` already complete across every file."""

    def __init__(self, file_id: str, rel_path: str, local_modules: dict,
                 local_defs: dict, record_edges: bool = True):
        self.file_id = file_id
        self.rel_path = rel_path
        self.local_modules = local_modules  # module dotted-name -> "file:<rel>"
        self.local_defs = local_defs        # (rel_path, qualname) -> def_id, global across files
        self.record_edges = record_edges
        self.import_aliases = {}  # local name -> source rel_path, this file only
        self.scope = []  # stack of qualname parts
        self.nodes = []
        self.edges = []
        if record_edges:
            self.nodes.append({"id": file_id, "type": "file", "name": rel_path,
                                "file": rel_path, "lineno": None})

    def _qualname(self, name):
        return ".".join(self.scope + [name])

    def _current_container_id(self):
        if not self.scope:
            return self.file_id
        return f"def:{self.rel_path}:{'.'.join(self.scope)}"

    def _external(self, name):
        node_id = f"external:{name}"
        if not any(n["id"] == node_id for n in self.nodes):
            self.nodes.append({"id": node_id, "type": "external", "name": name,
                                "file": None, "lineno": None})
        return node_id

    def visit_Import(self, node):
        if self.record_edges:
            for alias in node.names:
                self._add_import(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            if self.record_edges:
                self._add_import(node.module)
            target = self.local_modules.get(node.module) or \
                self.local_modules.get(node.module.split(".")[0])
            if target:
                target_rel = target[len("file:"):]
                for alias in node.names:
                    self.import_aliases[alias.asname or alias.name] = target_rel
        self.generic_visit(node)

    def _add_import(self, dotted: str):
        top = dotted.split(".")[0]
        target = self.local_modules.get(dotted) or self.local_modules.get(top)
        to_id = target if target else self._external(dotted)
        self.edges.append({"from": self.file_id, "to": to_id, "type": "imports"})

    def _resolve(self, name: str) -> str:
        """A bare name: same-file def, else a def in a file it was
        explicitly `from`-imported out of, else external."""
        same_file = self.local_defs.get((self.rel_path, name))
        if same_file:
            return same_file
        src_rel = self.import_aliases.get(name)
        if src_rel:
            imported = self.local_defs.get((src_rel, name))
            if imported:
                return imported
        return self._external(name) if self.record_edges else None

    def _visit_def(self, node, kind):
        qual = self._qualname(node.name)
        def_id = f"def:{self.rel_path}:{qual}"
        self.local_defs[(self.rel_path, qual)] = def_id  # both passes: pass 1 needs this populated
        if self.record_edges:
            parent_id = self._current_container_id()
            self.nodes.append({"id": def_id, "type": kind, "name": qual,
                                "file": self.rel_path, "lineno": node.lineno})
            self.edges.append({"from": parent_id, "to": def_id, "type": "contains"})
            if kind == "class":
                for base in node.bases:
                    base_name = base.id if isinstance(base, ast.Name) else None
                    if base_name:
                        base_id = self._resolve(base_name)
                        self.edges.append({"from": def_id, "to": base_id, "type": "inherits"})
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self._visit_def(node, "function")

    def visit_AsyncFunctionDef(self, node):
        self._visit_def(node, "function")

    def visit_ClassDef(self, node):
        self._visit_def(node, "class")

    def visit_Call(self, node):
        if self.record_edges and self.scope:
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in ("self", "cls"):
                name = node.func.attr
            if name:
                caller_id = self._current_container_id()
                callee_id = self._resolve(name)
                self.edges.append({"from": caller_id, "to": callee_id, "type": "calls"})
        self.generic_visit(node)


def build_graph(root: str = None) -> dict:
    root = Path(root).resolve() if root else Path(__file__).resolve().parent.parent
    files = list(_iter_py_files(root))
    local_modules = {_module_name(root, p): f"file:{p.relative_to(root)}" for p in files}
    local_defs = {}
    skipped = []
    parsed = {}
    aliases_by_file = {}

    # Pass 1 — collect every definition and import alias, no edges yet.
    for path in files:
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError) as e:
            skipped.append({"file": rel, "reason": str(e)})
            continue
        parsed[rel] = tree
        collector = _FileVisitor(f"file:{rel}", rel, local_modules, local_defs, record_edges=False)
        collector.visit(tree)
        aliases_by_file[rel] = collector.import_aliases

    # Pass 2 — build the actual graph; local_defs is now complete.
    nodes_by_id = {}
    edges = []
    for rel, tree in parsed.items():
        visitor = _FileVisitor(f"file:{rel}", rel, local_modules, local_defs, record_edges=True)
        visitor.import_aliases = aliases_by_file[rel]
        visitor.visit(tree)
        for n in visitor.nodes:
            nodes_by_id[n["id"]] = n  # last write wins; external nodes are identical anyway
        edges.extend(visitor.edges)

    return {
        "root": str(root),
        "files_scanned": len(files) - len(skipped),
        "files_skipped": skipped,
        "nodes": list(nodes_by_id.values()),
        "edges": edges,
    }


def hubs(graph: dict, top_n: int = 10) -> list:
    """Highest in-degree nodes among OUR OWN code — graphify calls these
    'god nodes'; same idea, plain degree count instead of Leiden community
    detection. External nodes (builtins, stdlib, third-party calls) are
    excluded: `print`/`len`/`assertEqual` topping the list every time tells
    you nothing about this codebase's actual structure."""
    by_id = {n["id"]: n for n in graph["nodes"]}
    in_degree = {}
    for e in graph["edges"]:
        if e["type"] == "contains":
            continue  # structural nesting, not a dependency — always 1, never informative
        target = by_id.get(e["to"])
        if target is None or target["type"] == "external":
            continue
        in_degree[e["to"]] = in_degree.get(e["to"], 0) + 1
    ranked = sorted(in_degree.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for node_id, degree in ranked[:top_n]:
        n = by_id[node_id]
        out.append({"id": node_id, "name": n["name"], "type": n["type"], "in_degree": degree})
    return out


def status() -> dict:
    return {
        "backend": "stdlib ast — always available, no fallback needed",
        "last_graph": str(DEFAULT_GRAPH_PATH) if DEFAULT_GRAPH_PATH.exists() else None,
        "scope": "resolves same-file calls and explicit `from X import Y` calls; "
                 "anything else recorded as an external node, not chased (see module docstring)",
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "status":
        print(json.dumps(status(), indent=2))
    elif args and args[0] == "build":
        rest = args[1:]
        path_arg = None
        out_arg = str(DEFAULT_GRAPH_PATH)
        top_n = 10
        i = 0
        while i < len(rest):
            if rest[i] == "--out" and i + 1 < len(rest):
                out_arg = rest[i + 1]
                i += 2
            elif rest[i] == "--top" and i + 1 < len(rest):
                top_n = int(rest[i + 1])
                i += 2
            elif not rest[i].startswith("--"):
                path_arg = rest[i]
                i += 1
            else:
                i += 1
        graph = build_graph(path_arg)
        Path(out_arg).write_text(json.dumps(graph, indent=2))
        summary = {
            "root": graph["root"],
            "files_scanned": graph["files_scanned"],
            "files_skipped": len(graph["files_skipped"]),
            "nodes": len(graph["nodes"]),
            "edges": len(graph["edges"]),
            "written_to": out_arg,
            "hubs": hubs(graph, top_n),
        }
        print(json.dumps(summary, indent=2))
    else:
        print("usage: synapse.py build [path] [--out FILE] [--top N] | status", file=sys.stderr)
        sys.exit(2)
