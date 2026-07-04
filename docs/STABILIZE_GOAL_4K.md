HERMES — Stabilize-to-Proven. Prove & harden what exists; BUILD NOTHING NEW. Success = reproducible evidence on disk, never your own assessment that it "should work."

PROHIBITED: new modules/skills/integrations/stages/"improvements" — not one; touching Stage 5/opt-in breadth; elegance refactors before all gates green. The urge to ADD so progress feels visible IS this project's failure mode — resist it, prove what exists instead.

INVARIANTS (never violate): 1) nothing bypasses Apollo or verify.sh — security lives at the hook layer, never a prompt; 2) sensitive → Tier 1/2 only, Chinese APIs have no code path; 3) never auto-apply — curator proposals, security-logic edits, doc-claim changes are PROPOSED by you and MERGED by a human, never self-approved; 4) patterns, not copied code; 5) every optional layer degrades gracefully; 6) prove on REAL local disk, never the FUSE/Cowork mount; 7) this loop runs on the CLI host, not Cowork.

GATES — always work the lowest unmet; a gate is GREEN only when the stated evidence exists on disk and re-runs green. Never self-certify, skip, or reorder.

G0 Real traffic: (a) logs/reasoning_seed.jsonl gains ≥1 entry from a GENUINE request with latency_ms>0; (b) Mnemos on real local disk: init+write+search round-trips, a memory written in process A retrieved in separate process B; (c) ReasoningBank: one real reward logged, retrieve_top_k() surfaces it before a similar new task; (d) Curator loop closes once WITH a human: real recurring failure → pending/ proposal → human approve → approved/, not re-proposed after. EVIDENCE: literal log lines + command transcript saved as a proof file under logs/.

G1 Docs tell the truth (right after G0): NO tracked file — whole tree, never a hand-picked list — claims "proven" for anything not gated green, and every stated test count matches the live `python3 test_hermes.py` tail; verify with `git grep -nE "[0-9]+ tests|proven"`; HERMES_GOAL/HERMES_MAP reconciled to actual build state. EVIDENCE: diff + live test-count line + clean sweep output.

G2 Orchestrator behaviorally tested: a golden set of ≥25 (request → expected tier, expected sub-skill) cases runs GREEN through brain.py + a real routing resolver inside test_hermes.py; assertIn() substring checks on SKILL.md do NOT count. EVIDENCE: pytest output.

G3 Execution surface hardened: cron/scheduler.py and delegation/agenda.py no longer rely on a regex denylist alone for shell=True — argv vector or command allowlist; threat model written into docs/DECISIONS.md. EVIDENCE: code change + test proving a known denylist-bypass string no longer executes.

G4 Each external path answered once for real, or honestly marked unverified: Ollama Tier 2 chat, one search backend (Tavily/Firecrawl), one MCP server via Connect, one `claude -p` delegation child. Unexercised paths say "unverified" in status output — never implied working. EVIDENCE: captured real response per path, or explicit unverified marker.

DONE = all five gates GREEN with evidence on disk. Then STOP and report. Do not invent G5.

EACH RUN: 1) read gate status from EVIDENCE ON DISK — not memory, not prior claims; 2) take the next concrete chunk toward the lowest unmet gate; 3) verify by running the actual command/test and pasting its REAL output; 4) pass → record evidence and advance; fail → gate stays open; 5) end with exactly one status line.

STOP-AND-SURFACE: same gate blocked after 5 genuine attempts (rate-limit retries don't count) → STOP and hand the specific blocker to the human. Never skip a gate, fabricate evidence, or substitute a feature for an unfinished proof. ANTI-DRIFT: editing any file not in service of the lowest unmet gate = drift; return to the gate.

STATUS LINE (end every run with EXACTLY one, nothing after):
HERMES_STABILIZE: DONE — all gates green, evidence at <paths>
HERMES_STABILIZE: CONTINUE — gate <N>: <what you just proved> / next: <single next step>
HERMES_STABILIZE: BLOCKED — gate <N>: <specific blocker>, needs human
