# Changelog

All notable changes to tool-fabric are documented here.

---

## [0.2.0] — 2026-04-13

### Multi-model scale benchmark (branch: claude/interesting-jennings)

**`benchmarks/scale_benchmark.py`:**
- `--model` flag supporting any Claude model (Haiku 4.5, Sonnet 4.6, Opus 4.6)
- Scale-aware evaluation: 41 tools (registry) and 150 tools (registry + 109 confusers)
- OLD/NEW × 41/150 full 2×2 factorial design per model
- Governance lift analysis: hit@1, hit@3, MRR across conditions

**`benchmarks/data/`:**
- `old_descriptions.json`: 150-tool raw description corpus
- `new_descriptions.json`: 150-tool governed description corpus (with query_tips, alternatives)
- `confuser_tools.json`: 109 confuser tools for scale injection

**`benchmarks/results/`:**
- `multi_model_results.json`: combined governance lift summary across all three models
- `scale_results.json`: full Haiku run (all queries × conditions × tools)
- `scale_sonnet.json`: full Sonnet run
- `scale_opus.json`: full Opus run

**Key findings (governance lift at 150 tools, hit@1):**
- Haiku: +14pp — strongest relative benefit; governance closes the gap to frontier
- Sonnet: +0pp hit@1, +14pp hit@3 — guide helps at recall depth
- Opus: +10pp — clear lift even for the strongest model

**Cost-efficiency finding:** Haiku + governance (~$0.001/query) matches ungoverned
Opus (~$0.015/query) at 150 tools — 15× cost reduction with no accuracy trade-off.

---

## [0.1.0] — 2026-04-13

### Round 1 — Initial scaffold

- `spec/SPEC.md`: formal specification — motivation, core concepts, linter rules, benchmark protocol, design decisions
- `spec/schema.yaml`: JSON Schema for `.tool-fabric.yaml`
- `linter/checks.py`: 12 check implementations (E001-E005, W001-W004, I001-I003)
  - Similarity backend: sentence-transformers primary, Jaccard fallback
- `linter/cli.py`: `fabric-lint check`, `fabric-lint report`, `fabric-lint init`
- `examples/carlos-os/.tool-fabric.yaml`: 15-tool annotated CARLOS-OS registry excerpt
- `benchmarks/README.md`: three-tier benchmark protocol (single-tool, compositional, adversarial)
- `pyproject.toml`: hatchling build, click + pyyaml deps, optional sentence-transformers

### Round 2 — Completeness, minimality, coherence (branch: claude/quirky-feynman)

**New checks:**
- `I004`: Completeness gap — concept defined in DAG but no tool requires it
- `W006`: Vocabulary incoherence — synonym drift within a MECE group (regex-based cluster detection)
- `W007`: Minimality violation — alternative tools with identical input/output shapes

**Enhanced `fabric-lint report`:**
- Summary table with tool/concept/pattern counts and per-code violation breakdown
- Designed for direct use as empirical data in the tool-fabric paper (§4)

**Tests:** 46-test suite in `tests/test_checks.py` covering all 11 checks (all pass)

**Empirical run:** `examples/carlos-os/lint-report.md` — first real lint run against
a 34-tool CARLOS-OS registry. Found 62 violations: 24 E002, 19 W001, 2 W006, 1 W007,
1 I004, 15 I001.

### Round 3 — Benchmark harness and FabricEnricher (branch: claude/tender-babbage)

**`runtime/enricher.py` — FabricEnricher:**
- 5-layer enrichment: original description, query_tips, alternatives + disambiguation hints,
  concept definitions, pattern membership
- Additive, never destructive — raw description always preserved as prefix
- Designed for injection into LLM system prompt or tool-description field

**`benchmarks/carlos_os_benchmark.py`:**
- 20 CARLOS-OS queries with ground-truth tool sets
- 4 disambiguation families: GitHub/Linear, Slack/Gmail, bash/python, web_search/web_fetch
- TF-IDF selector (scikit-learn) measures hit@1, hit@k, MRR, precision@k, recall@k
- Baseline vs enriched comparison

**`benchmarks/results/carlos_os_results.json`:**
- Baseline (TF-IDF, raw descriptions): hit@1=0.60, MRR=0.74
- Enriched (TF-IDF, FabricEnricher): hit@1=0.40, MRR=0.59
- Root cause documented: TF-IDF cross-contamination from alternatives text; expected behavior
  for a statistical selector — enrichment optimized for LLM, not TF-IDF

**Tests:** 61 tests covering enricher unit tests and benchmark pipeline (all pass)

**`pyproject.toml`:** Added `[benchmark]` optional deps (scikit-learn)

### Round 4 — W005 check, grounded registry, extended tests (branch: claude/vibrant-goodall)

**New check:**
- `W005`: Undefined alternative reference — `alternatives` entry not defined in registry.
  Catches stub references to external tools that lack governance annotations.

**`examples/carlos-os/.tool-fabric.yaml`:** Registry grounded in CARLOS-OS reality:
- Expanded to 41 tools across 6 domains (project-management, communication, code,
  file-system, ai-inference, search, finance, calendar, devops)
- 23 concepts, 7 patterns, 3 MECE groups
- All tool descriptions, alternatives, and composes_with edges reflect actual CARLOS-OS tools

**`spec/SPEC.md`:** W005 check added to linter rules section

**Tests:** Expanded to 119 tests total (all pass):
- `test_checks.py`: 55 tests covering all 16 checks + Jaccard similarity backend
- `test_enricher.py`: 19 tests (unchanged)
- `test_benchmark.py`: 40 tests (unchanged, plus 5 new Jaccard tests)

### Round 5 — Final polish (this release)

- **Merged** all feature branches (Rounds 1-4) into main with conflict resolution
- **README.md**: complete rewrite with Quick Demo, 16-check table, installation instructions,
  benchmark results table, updated repository structure
- **CHANGELOG.md**: this file
- All 119 tests pass
- Tagged v0.1.0
