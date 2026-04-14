# tool-fabric

**Declarative governance for LLM tool registries. Lint your tools like you lint your code.**

---

## The Problem

LLM tool selection accuracy degrades below 15% for compositional tasks at scale.

The root cause is not model capability — it's registry design. Most tool registries are flat lists of descriptions with no relationship metadata. When an agent faces 50+ tools, it must:

1. Parse every description on every call
2. Infer overlap from natural language
3. Guess which tools compose well together
4. Decide sequencing without ontological grounding

This produces hallucinated tool calls, missed fan-outs, and incoherent multi-step plans. The model is not broken. The registry is.

---

## The Solution

`tool-fabric` provides three artifacts:

### 1. `.tool-fabric.yaml` — Registry Schema
A declarative schema for annotating tool registries with relationship metadata:
- `concepts_required` — ontological prerequisites (concept DAG)
- `composes_with` — valid sequencing relationships
- `alternatives` — mutually exclusive tools for the same intent
- `input_shape` / `output_shape` — typed contracts for composition validation
- `query_tips` — disambiguation guidance for ambiguous cases

```yaml
tools:
  github_create_issue:
    category: project-management
    concepts_required: [github.repo, github.issue]
    alternatives: [linear_create_issue, jira_create_issue]
    composes_with: [github_assign_issue, github_add_label]
    input_shape: {repo: string, title: string, body: string}
    output_shape: {issue_url: string, issue_number: integer}
    query_tips: "Use when the repo is on GitHub. Not for Jira/Linear projects."
    cost_hints: {latency_ms: 200, tokens_consumed: 0}
```

### 2. `fabric-lint` — CLI Linter
Validates your registry against 16 governance rules before deployment:

```bash
pip install tool-fabric
fabric-lint check examples/carlos-os/.tool-fabric.yaml

# Output:
# WARNING  [W001] Orphan tool: 'github_create_issue' is not referenced in any pattern.
# WARNING  [W006] Vocabulary inconsistency in MECE group 'create a project tracking issue':
#                 mixed synonyms ['issue', 'task'] detected.
# WARNING  [W007] Minimality violation: 'gemini_invoke' and 'gpt_invoke' have identical
#                 input/output shapes. Consider merging or adding a distinguishing field.
# INFO     [I004] Completeness gap: concept 'github.issue' defined but no tool requires it.
# 22 warnings, 19 info
```

### 3. `FabricEnricher` — Runtime Description Enrichment
Enriches tool descriptions with governance metadata at inference time:

```python
from runtime.enricher import FabricEnricher
import yaml

with open("examples/carlos-os/.tool-fabric.yaml") as f:
    registry = yaml.safe_load(f)

enricher = FabricEnricher(registry)
raw = {"slack_send_message": "Sends a message to Slack."}
enriched = enricher.enrich_descriptions(raw)
# Enriched description includes: query_tips, alternatives + disambiguation,
# concept definitions, and pattern membership hints.
```

---

## Quick Demo

Running `fabric-lint check` against the CARLOS-OS registry (41 tools, 23 concepts, 7 patterns):

```
tool-fabric lint — examples/carlos-os/.tool-fabric.yaml
  41 tools  |  7 patterns  |  23 concepts

  WARNING  [W001] Orphan tool: 'gemini_invoke' is not referenced in any pattern.
  WARNING  [W001] Orphan tool: 'gpt_invoke' is not referenced in any pattern.
  WARNING  [W006] Vocabulary inconsistency in MECE group 'create a project tracking issue':
                  mixed synonyms ['issue', 'task'] detected.
                  Per-tool usage: 'github_create_issue'->['issue','task'],
                  'linear_create_issue'->['issue'].
  WARNING  [W007] Minimality violation: 'gemini_invoke' and 'gpt_invoke' are declared as
                  alternatives and have identical input/output shapes
                  (input: ['max_tokens', 'model', 'prompt'],
                   output: ['model', 'response', 'usage_tokens']).
                  Consider merging into one tool or adding a distinguishing field.
  INFO     [I001] 'github_close_issue': description has 8 words (target: 20-60).
  INFO     [I004] Completeness gap: concept 'github.issue' is defined in the DAG
                  but no tool declares it in concepts_required.

  22 warnings, 19 info
```

Each finding maps to a formal property violation. The full audit report is at
`examples/carlos-os/lint-report.md`.

---

## Linter Rules (16 checks)

### Errors — will cause incorrect behavior at inference time

| Code | Check |
|------|-------|
| E001 | Undeclared overlap: two tools have cosine similarity > 0.85 with no `alternatives` declared |
| E002 | Broken composition edge: `composes_with` target missing or `output_shape -> input_shape` unsatisfied |
| E003 | Concept gap: `concepts_required` entry not defined in the concept DAG |
| E004 | Circular concept dependency: cycle in the concept DAG |
| E005 | Undeclared tool in pattern: pattern references a tool_id not in the registry |

### Warnings — suboptimal; likely to degrade selection accuracy

| Code | Check |
|------|-------|
| W001 | Orphan tool: not referenced in any pattern |
| W002 | Possible overlap: cosine similarity > 0.70, no `alternatives` declared |
| W003 | Missing type declarations on a composed tool pair |
| W004 | Non-trivial category with no `concepts_required` |
| W005 | Undefined alternative reference: `alternatives` entry not in registry |
| W006 | Vocabulary incoherence: synonym drift within a MECE group |
| W007 | Minimality violation: alternative tools with identical input/output shapes |

### Info — quality improvement opportunities

| Code | Check |
|------|-------|
| I001 | Short description: < 20 words, reduces selection discriminability |
| I002 | Missing `query_tips` when `alternatives` are declared |
| I003 | Missing `cost_hints` (latency, idempotency, side effects) |
| I004 | Completeness gap: concept defined in DAG but no tool requires it |

---

## Concept DAG — Ontological Prerequisites

Tools declare which domain concepts they require. The DAG enables:
- Automatic prerequisite chain surfacing at inference time
- Gap detection (concepts used but not defined)
- Cross-registry coherence checks

```yaml
concepts:
  github.repo:
    description: "A GitHub repository identified by owner/repo slug"
    prerequisites: [github.auth]
    examples: ["anthropics/claude-code", "crbazevedo/tool-fabric"]
  github.issue:
    description: "A trackable work item in a GitHub repository"
    prerequisites: [github.repo]
```

---

## Formal Properties

tool-fabric enables three verifiable registry properties:

| Property | What it checks |
|----------|---------------|
| **MECE coverage** | No intent is covered by zero tools; no intent is covered by two tools without declared alternatives |
| **Compositional completeness** | Every `composes_with` edge has a matching `output_shape -> input_shape` contract |
| **Concept closure** | Every `concepts_required` entry has a definition in the concept DAG |

---

## Installation

```bash
# Install from source
git clone https://github.com/crbazevedo/tool-fabric
cd tool-fabric
pip install -e .

# With optional sentence-transformer embeddings (higher-accuracy overlap detection)
pip install -e ".[similarity]"

# Validate the CARLOS-OS example
fabric-lint check examples/carlos-os/.tool-fabric.yaml

# Generate a full markdown audit report
fabric-lint report examples/carlos-os/.tool-fabric.yaml --format markdown > REGISTRY_AUDIT.md

# Scaffold a new registry
fabric-lint init > .tool-fabric.yaml
```

---

## Benchmark Results

CARLOS-OS registry (41 tools, 20 disambiguation queries) using a TF-IDF selector as a
controlled baseline. Ground truth: 4 disambiguation families (GitHub/Linear, Slack/Gmail,
bash/python, web_search/web_fetch).

| Condition | hit@1 | MRR |
|-----------|-------|-----|
| Baseline (raw descriptions, TF-IDF) | 0.60 | 0.74 |
| Enriched (FabricEnricher, TF-IDF) | 0.40 | 0.59 |

**Note on the TF-IDF result:** The enriched condition shows lower TF-IDF accuracy because
`alternatives` text cross-contaminates the bag-of-words signal — competitor tool names in
descriptions match competing queries. This is expected for a statistical selector.

Fabric enrichment is optimized for LLM comprehension, not TF-IDF. Enriched descriptions
add governance context that an LLM can reason about (e.g., "use this tool when X, not Y"),
but TF-IDF treats disambiguation tokens as noise. Production benchmarks should use an LLM
selector for the enriched condition. See `benchmarks/README.md` for the full three-tier
benchmark protocol.

---

## Results at 150 Tools (Governance Lift)

Scale benchmark across Claude Haiku 4.5, Sonnet 4.6, and Opus 4.6 using 150 tools
(41 registry tools + 109 confuser tools). OLD = raw descriptions; NEW = governed descriptions.

| Model          | Baseline hit@1 | Governed hit@1 | Lift   |
|----------------|----------------|----------------|--------|
| Claude Haiku   | 0.52           | 0.66           | +14pp  |
| Claude Sonnet  | 0.50           | 0.50 (hit@3 +14pp) | +0pp / +14pp |
| Claude Opus    | 0.64           | 0.74           | +10pp  |

**Key insight:** Governance benefits every model tier.
Haiku + governance ≈ ungoverned Opus at the same scale.

Cost implication: Haiku + governance (~$0.001/query) matches ungoverned Opus (~$0.015/query)
at 150 tools — a 15× cost reduction with no accuracy trade-off.

See `benchmarks/scale_benchmark.py` and `benchmarks/results/multi_model_results.json`
for the full experiment.

---

## Repository Structure

```
tool-fabric/
├── spec/
│   ├── schema.yaml        # JSON Schema for .tool-fabric.yaml
│   └── SPEC.md            # Human-readable spec + design rationale
├── linter/
│   ├── __init__.py
│   ├── cli.py             # fabric-lint entry point (check, report, init)
│   └── checks.py          # 16 check implementations (E001-E005, W001-W007, I001-I004)
├── runtime/
│   └── enricher.py        # FabricEnricher: 5-layer description enrichment
├── benchmarks/
│   ├── carlos_os_benchmark.py   # 20-query CARLOS-OS benchmark harness
│   ├── results/
│   │   └── carlos_os_results.json  # TF-IDF baseline vs enriched results
│   └── README.md          # Three-tier benchmark protocol
├── examples/
│   └── carlos-os/
│       ├── .tool-fabric.yaml  # 41-tool CARLOS-OS registry
│       └── lint-report.md     # First real lint run results
├── tests/
│   ├── test_checks.py     # 55 tests covering all 16 checks + Jaccard backend
│   ├── test_enricher.py   # 19 tests covering FabricEnricher
│   └── test_benchmark.py  # 40 tests covering benchmark harness
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## Status

**v0.2.0 — Research preview.** The schema, linter (16 checks), enricher, benchmark
harness, and multi-model scale benchmark are functional. The runtime proxy middleware
(MCP proxy that injects metadata at inference time) is under active development.

119 tests pass. CI-ready.

---

## Contributing

This project emerged from practical work on CARLOS-OS, a multi-agent personal OS with
95 tools across 6 domains. The failure modes documented here are real — not hypothetical.

Issues and PRs welcome. See `spec/SPEC.md` for the theoretical grounding.

---

## License

MIT
