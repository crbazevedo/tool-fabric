# tool-fabric — Vision &amp; Trajectory

**Authored by:** dfg-harness discovery agent (autonomous)
**Date:** 2026-05-04
**Scope:** Initial discovery pass; basis for the v0.3.0 plan decomposition.

---

## §1 — What this is

`tool-fabric` is a **declarative governance layer for LLM tool registries** —
*"lint your tools like you lint your code."*

It ships three artifacts:

1. **`.tool-fabric.yaml`** — schema with `concepts_required`, `composes_with`,
   `alternatives`, typed `input_shape` / `output_shape`, `query_tips`, `cost_hints`.
2. **`fabric-lint`** — CLI linter with **16 governance rules** (5 errors, 7
   warnings, 4 info) catching orphan tools, broken composition edges, concept
   gaps, vocabulary drift, minimality violations.
3. **`FabricEnricher`** — runtime that enriches raw tool descriptions with
   governance metadata at inference time.

## §2 — The problem it solves

LLM tool selection accuracy collapses non-linearly with registry size:

| Tools | Selection accuracy (typical) |
|---|---|
| 10 | &gt; 90% |
| 50 | &lt; 60% |
| 100+ compositional | &lt; 15% |

The cause is **information architecture, not model capability**. A flat list
of NL descriptions forces the model into a search problem disguised as
reasoning. `tool-fabric` is the missing structural metadata layer.

## §3 — Empirical receipts (v0.2.0)

Multi-model benchmark (Haiku 4.5 / Sonnet 4.6 / Opus 4.6 × OLD/NEW × 41/150 tools).
Numbers below are **as cited in `CHANGELOG.md` v0.2.0 entry**; raw runs in
`benchmarks/results/{multi_model_results,scale_results,scale_sonnet,scale_opus}.json`
are authoritative and any contradiction with this section should be
treated as the table being stale.

| Metric (150-tool, hit@1 governance lift) | Value (per CHANGELOG) |
|---|---|
| Haiku +pp | **+14** |
| Sonnet (hit@1) | +0 |
| Sonnet (hit@3) | +14 |
| Opus +pp | **+10** |

**Cost-efficiency receipt (per CHANGELOG):** Haiku + governance
(~$0.001/query) ≈ Opus ungoverned (~$0.015/query) at 150 tools — **15×
cost reduction with no accuracy trade-off**. This is the same value
proposition as dfg-harness (governance &gt; scale) in a different domain.

**Provenance:** Numbers in this section were lifted from
`CHANGELOG.md` v0.2.0 entry by the dfg-harness discovery agent on
2026-05-04. They have NOT been independently re-run from the raw
result files in this PR's scope; W6 (benchmark expansion) is the
appropriate wave for re-running and amending.

## §4 — Current surface

LOC counts measured at HEAD on 2026-05-04 via `wc -l`. Test count cited
from CHANGELOG ("36-test suite"); not independently audited in this pass.

| Component | LOC (`wc -l`) | Status |
|---|---|---|
| `linter/checks.py` (linter rules) | 815 | shipped |
| `linter/cli.py` (check / report / init) | 241 | shipped |
| `runtime/enricher.py` (FabricEnricher) | 162 | shipped |
| `spec/SPEC.md` (formal spec) | — | drafted |
| `spec/schema.yaml` (JSON Schema) | — | shipped |
| `tests/` (test_checks / test_enricher / test_benchmark) | — | 36 tests (per CHANGELOG) |
| `examples/carlos-os/` (annotated 41-tool registry) | — | shipped |
| `benchmarks/scale_benchmark.py` (multi-model harness) | — | shipped |

Note: README §"Linter Rules (16 checks)" enumerates 16 rules. CHANGELOG
v0.1.0 says "12 check implementations (E001-E005, W001-W004, I001-I003)".
The delta (4 rules) is presumed shipped in v0.2.0 / round-2/3/4 work
based on commit titles, but not audited per-rule in this discovery pass.
**W2 (linter completeness — error rules)** is the right wave to verify
which rules are shipped vs planned.

**Stack:** Python 3.10+, Click + PyYAML core; optional sentence-transformers
+ scikit-learn + numpy for similarity / benchmarks. Hatchling build.

## §5 — Audience

- **Tool-registry authors** (MCP server maintainers, internal-tool curators)
- **AI-platform engineers** consolidating cross-vendor tool catalogs
- **Researchers** studying compositional tool-use failure modes
- **Open-source ecosystems** (Anthropic MCP, LangChain, LlamaIndex) that
  want a portable governance contract independent of any specific runtime

## §6 — Visible vector (where it's going)

Inferred from CHANGELOG + commit cadence + recent activity:

1. **Stabilize linter rules.** v0.2 closed 12+ checks; goal is the full 16
   in v0.3 with empirical-validated thresholds.
2. **Empirical case for governance &gt; scale.** Already strong; bigger registry
   sizes (500, 1000 tools), more model families, more compositional task types.
3. **Ecosystem integration.** MCP server registries, LangChain `Tool` adapters,
   LlamaIndex `FunctionTool` — produce `.tool-fabric.yaml` from each.
4. **Runtime adopters.** FabricEnricher integrations into agent runtimes
   (Claude Code, Cursor, Cline, etc.) — prove the runtime layer is
   pluggable across hosts.
5. **Conformance &amp; certification.** "tool-fabric clean" badge for registries
   passing all governance rules; visible in catalog discovery.

## §7 — Near-term horizon (v0.3 — next 4-6 weeks)

| Theme | Outcome |
|---|---|
| **Linter completeness** | All 16 rules shipped + cross-rule consistency tests; 50+ tests total |
| **Schema v2** | Nested concept hierarchies; per-tool `since` (versioning); `deprecated_by` field |
| **Benchmark expansion** | 500-tool scale; 4+ model families; long-tail compositional tasks |
| **Adoption surface** | First external registry imports `.tool-fabric.yaml`; `fabric-lint github-action` |
| **Doc / DX** | `fabric-lint` man page; quickstart &lt;5 minutes; troubleshooting guide |

## §8 — Far-term horizon (v0.4+ — next quarter)

- **Conformance certification** + tool-fabric badge ecosystem
- **MCP registry import/export** — round-trip with the MCP spec
- **Runtime registry queries** — `fabric-query "create issue on github"` →
  ranked tool list with disambiguation
- **Policy attestation** — registries can declare safety properties
  (read-only, idempotent, network-egress) and the linter verifies
- **Federated registries** — multi-author, multi-namespace governance with
  conflict resolution

## §9 — Risks the plan must absorb

| Risk | Mitigation in v0.3 |
|---|---|
| Sentence-transformers dependency drag (slow, large) | Keep Jaccard fallback path tested; add `--no-embeddings` mode |
| Schema drift across versions | Codify migration; `schema_version` already in YAML |
| Benchmark cherry-picking concern | Pre-register task suites; release raw run data |
| Adoption: lock-in fears | Make schema portable (vendor-neutral wording); clear MCP/LangChain/LlamaIndex import paths |
| Solo maintainer cadence | dfg-harness instrumentation (this exercise) compounds discipline; ratchet open-issue density |

## §10 — Composition with dfg-harness

`tool-fabric` becomes the first external repo where dfg-harness governs
work end-to-end:

- `.dfg/plan.yaml` decomposes v0.3 into phases / sprints / waves / units.
- Per-PR dual-critic gates the linter rules (each rule lands as one unit).
- Pain-to-hook ratchet absorbs surfaced gaps as next-iteration hooks.
- Substrate-coherence verify keeps state.json in sync with canonical events.
- Cumulative DISCIPLINE-CHANGELOG provides an auditable trail of how the
  v0.3 release was actually built — the same shape used to deliver
  dfg-harness v0.3.0 itself.

This document is the seed. The plan that follows decomposes the v0.3
horizon into executable units.
