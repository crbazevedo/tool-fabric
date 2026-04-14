# tool-fabric Specification

**Version:** 0.1.0-research  
**Status:** Draft

---

## 1. Motivation

### 1.1 The Scaling Failure

Empirical studies on LLM tool selection show accuracy degrading non-linearly with registry size. At 10 tools, selection accuracy is typically >90%. At 50 tools, it drops below 60%. At 100+ tools with compositional tasks, it frequently falls below 15%.

The cause is not model capability — it is information architecture. A flat list of tool descriptions forces the model to:

1. Hold all N descriptions in context simultaneously
2. Compute pairwise overlap from natural language alone
3. Infer valid sequencing without explicit contracts
4. Resolve ambiguity without disambiguation signals

This is a search problem disguised as a reasoning problem. The model cannot perform well on it because the registry lacks the metadata that would make it tractable.

### 1.2 The Missing Layer

Code linters catch problems that compilers miss: style violations, dead code, unreachable branches. They work because they have access to the structure of the code — not just whether it runs.

Tool registries have no equivalent. They ship with no structural metadata, no overlap declarations, no sequencing contracts. Every failure mode is invisible until inference time, when it manifests as a hallucinated tool call or a missing fan-out.

`tool-fabric` is that missing layer.

---

## 2. Core Concepts

### 2.1 The `.tool-fabric.yaml` File

The central artifact is a `.tool-fabric.yaml` file that lives alongside your tool definitions. It declares four sections:

- **`tools`** — Per-tool annotations (relationships, types, tips)
- **`concepts`** — Domain concept DAG (ontological prerequisites)
- **`patterns`** — Named fan-out recipes for compound intents
- **`properties`** — Registry-level governance assertions

These sections form a directed graph. The linter checks the graph for consistency.

### 2.2 The Concept DAG

Every domain has an ontology. For GitHub tools, that ontology includes: auth credentials, organization, repository, issue, pull request, comment, label, milestone. Some concepts are prerequisites for others — you cannot create an issue without a repository; you cannot create a repository without auth.

tool-fabric makes this ontology explicit as a DAG. Tools declare `concepts_required`; concepts declare `prerequisites`. This enables:

- **Prerequisite chain surfacing:** At inference time, the router can inject only the relevant concept definitions, dramatically reducing context length.
- **Gap detection:** The linter can identify concepts used by tools but not defined in the DAG.
- **Cross-registry coherence:** When merging two registries (e.g., GitHub + Linear), concept overlap is explicit and resolvable.

### 2.3 Compositional Contracts

A tool registry is a type system for agent behavior. `input_shape` and `output_shape` declarations make this type system explicit.

The linter checks:
- Every field in `composes_with` target's `input_shape` is satisfied by the output of the preceding tool
- No `composes_with` edge points to a tool with an incompatible type contract

This catches a class of bugs that only manifest at runtime in untyped registries.

### 2.4 Alternatives Declaration

When two tools address the same intent, one of three things should be true:
1. They are in the same MECE group with an explicit selection criterion
2. One is deprecated in favor of the other
3. One tool is wrong and should be removed

Without explicit alternatives declarations, the router must infer this from description similarity — which it does poorly. Declaring alternatives tells the router the tools are interchangeable for this intent and provides the `query_tips` to select between them.

---

## 3. Linter Rules

### 3.1 Severity Levels

| Level | Meaning |
|-------|---------|
| `error` | Registry will produce incorrect behavior at inference time |
| `warning` | Registry is suboptimal; likely to produce degraded selection accuracy |
| `info` | Quality improvement opportunity; does not affect correctness |

### 3.2 Checks

**E001 — Undeclared Overlap**  
Two tools have description cosine similarity > 0.85 and no `alternatives` declaration. At inference time, the router cannot distinguish them.

**E002 — Broken Composition Edge**  
A tool lists another in `composes_with` but the output_shape → input_shape contract is not satisfied.

**E003 — Concept Gap**  
A tool declares a `concepts_required` entry that is not defined in the `concepts` section.

**E004 — Circular Concept Dependency**  
The concept DAG contains a cycle.

**E005 — Undeclared Tool in Pattern**  
A pattern references a tool_id that is not declared in the `tools` section.

**W001 — Orphan Tool**  
A tool is not referenced in any pattern. It can still be called, but compositional routing will not consider it.

**W002 — Missing Alternatives**  
A tool has no `alternatives` declared and its description similarity to another tool is > 0.70.

**W003 — Missing input_shape / output_shape**  
A tool participates in a `composes_with` relationship but has no type declarations.

**W004 — Missing concepts_required**  
A tool has a non-trivial domain (not `search`, `file-system`, `utility`) but declares no `concepts_required`.

**W005 — Undefined Alternative Reference**  
A tool declares an `alternatives` entry that is not defined in the `tools` section. The router cannot look up the description or `query_tips` of an undefined alternative. Add a stub entry to document the selection criterion, or remove the reference.

**I001 — Short Description**  
A tool description is < 20 words. Likely to cause ambiguity at scale.

**I002 — Missing query_tips**  
A tool has `alternatives` declared but no `query_tips`. The router cannot select between them.

**I003 — Missing cost_hints**  
A tool has no `cost_hints`. The orchestrator cannot make scheduling decisions.

---

## 4. Information-Theoretic Description Optimization

### 4.1 The Problem with Natural Language Descriptions

Tool descriptions written by humans optimize for human readability. This is the wrong objective.

At inference time, the model selects tools by computing relevance between the user query and each description. Descriptions should be optimized for this discriminability — maximizing mutual information between the description and the tool's unique function.

### 4.2 Optimization Principles

**Principle 1: Specificity over generality.**  
"Search for information" (bad) vs. "Search the web for current information not in the training corpus" (good).

**Principle 2: Include negative examples.**  
"Use when the repo is on GitHub. Not for Jira or Linear projects." reduces false positives dramatically.

**Principle 3: State the output, not just the action.**  
"Creates a GitHub issue and returns the issue URL and number" vs. "Create a GitHub issue".

**Principle 4: 20-60 words is the optimal range.**  
Below 20: insufficient discriminability. Above 60: dilutes the signal.

The linter enforces Principle 4 and flags violations of Principles 1-3 via the `query_tips` gap check.

---

## 5. Registry Evaluation Protocol

### 5.1 Three Benchmark Tiers

**Tier 1 — Single-Tool Selection**  
Test: given a single-step intent, does the router select the correct tool?  
Metric: top-1 accuracy  
Baseline: flat registry without tool-fabric annotations  

**Tier 2 — Compositional Selection**  
Test: given a multi-step intent, does the router produce the correct tool sequence?  
Metric: sequence exact match, sequence F1  
Baseline: same  

**Tier 3 — Adversarial Selection**  
Test: given an intent with a near-miss (a semantically similar but incorrect tool), does the router avoid the near-miss?  
Metric: false positive rate  
Baseline: same  

### 5.2 Hypothesis

Registries annotated with tool-fabric metadata will show statistically significant improvement on Tier 2 and Tier 3 benchmarks, with smaller but consistent improvement on Tier 1.

The improvement should be largest in registries with:
- High inter-tool similarity (many alternatives)
- Deep composition chains (3+ steps)
- Cross-domain fan-outs (tools from different categories in the same pattern)

---

## 6. Design Decisions

### 6.1 Why YAML, Not JSON Schema?

YAML is the lingua franca of infrastructure-as-code. Tool registry authors are often DevOps/platform engineers who already maintain YAML configs. Reducing friction of adoption is a priority.

The schema itself is defined as JSON Schema (in `spec/schema.yaml`) and validated against it. This gives us machine-readable validation without sacrificing human authoring ergonomics.

### 6.2 Why a Separate File, Not Inline Annotations?

Tool implementations exist in many forms: Python functions, OpenAPI specs, MCP server configs, LangChain tool objects. Requiring inline annotation changes every existing tool definition format.

A separate `.tool-fabric.yaml` file is a pure governance layer — it can be added to any existing registry without modifying the tools themselves.

### 6.3 Why Cosine Similarity for Overlap Detection?

Cosine similarity on sentence embeddings is a proven, fast heuristic for detecting semantic overlap. It is not perfect, but it is:
- Symmetric (no ordering effects)
- Threshold-tunable (0.85 for errors, 0.70 for warnings)
- Cheap to compute at lint time
- Explainable (the score is a number the author can reason about)

False positives (tools that are similar but intentionally different) are suppressed by explicit `alternatives` declarations.

### 6.4 Why Patterns, Not Just Sequences?

Patterns are named, reusable, and carry semantic intent. They are the unit of compositional reasoning. A pattern is not just "use tool A then tool B" — it is "when the user wants X, do A then B, and merge results with strategy Y."

This makes patterns useful both for documentation and for runtime routing. The pattern name is a signal the model can reason about; the tool_sequence is the execution plan.

---

## 7. Future Work

- **Runtime proxy middleware** — An MCP proxy that injects tool-fabric metadata into the system prompt at inference time, reducing context load while preserving selection accuracy.
- **Registry diffing** — A `fabric-diff` command to compare two registry versions and surface breaking changes.
- **Auto-annotation** — Use an LLM to propose `query_tips`, `alternatives`, and `concepts_required` from existing descriptions.
- **ADK integration** — Native support for Google ADK agent configs as a first-class target format.
