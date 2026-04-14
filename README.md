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
Validates your registry against governance rules before deployment:

```bash
pip install tool-fabric
fabric-lint .tool-fabric.yaml

# Output:
# ERROR   [overlap] github_create_issue ↔ github_open_issue: cosine=0.94, no alternatives declared
# WARNING [orphan]  slack_react_message not referenced in any pattern
# INFO    [quality] search_web: description <20 words, no examples
# 3 errors, 12 warnings
```

### 3. Concept DAG — Ontological Prerequisites
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
| **Compositional completeness** | Every `composes_with` edge has a matching `output_shape → input_shape` contract |
| **Concept closure** | Every `concepts_required` entry has a definition in the concept DAG |

These properties are evaluated by `fabric-lint` and can be asserted in CI.

---

## Quick Start

```bash
pip install tool-fabric

# Scaffold a new registry
fabric-lint init > .tool-fabric.yaml

# Validate an existing registry
fabric-lint check .tool-fabric.yaml

# Generate a human-readable report
fabric-lint report .tool-fabric.yaml --format markdown > REGISTRY_AUDIT.md
```

See `examples/carlos-os/.tool-fabric.yaml` for a fully annotated registry with 95 tools.

---

## Status

**Research preview.** The schema and linter are functional. The runtime proxy middleware is under active development.

Benchmarks for tool selection accuracy improvement are defined in `benchmarks/README.md`. Empirical results pending.

---

## Repository Structure

```
tool-fabric/
├── spec/
│   ├── schema.yaml        # JSON Schema for .tool-fabric.yaml
│   └── SPEC.md            # Human-readable spec + design rationale
├── linter/
│   ├── __init__.py
│   ├── cli.py             # fabric-lint entry point
│   └── checks.py          # Individual check implementations
├── runtime/               # MCP proxy middleware (planned)
├── benchmarks/
│   └── README.md          # Benchmark protocol: 3 tiers
├── examples/
│   └── carlos-os/
│       └── .tool-fabric.yaml  # 95-tool CARLOS-OS registry
├── docs/
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## Contributing

This project emerged from practical work on CARLOS-OS, a multi-agent personal OS with 95 tools across 6 domains. The failure modes documented here are real — not hypothetical.

Issues and PRs welcome. See `spec/SPEC.md` for the theoretical grounding.

---

## License

MIT
