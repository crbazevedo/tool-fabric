# tool-fabric Benchmarks

Three benchmark tiers for evaluating the effect of tool-fabric annotations on LLM tool selection accuracy.

---

## Overview

The hypothesis is that registries annotated with tool-fabric metadata improve tool selection accuracy, particularly for compositional and adversarial tasks. These benchmarks are designed to test that hypothesis empirically.

Each tier uses the same evaluation protocol:
1. Run baseline (flat registry, no annotations)
2. Run treated (same registry with .tool-fabric.yaml annotations injected into system prompt)
3. Compute delta on the primary metric

---

## Tier 1 — Single-Tool Selection

**Purpose:** Establish baseline accuracy for simple, single-step intents.

**Setup:**
- Registry: 50 tools, 5 categories (10 tools each)
- Test set: 200 single-step intents, each with exactly one correct tool
- Model: claude-sonnet-4-6 (temperature=0)

**Metrics:**
- Top-1 accuracy (primary)
- Top-3 accuracy
- Mean reciprocal rank (MRR)

**Variants:**
- Low-overlap registry (tools are semantically distinct)
- High-overlap registry (5 tool pairs with cosine similarity > 0.80)

**Expected outcome:** Small improvement on low-overlap. Significant improvement on high-overlap where `alternatives` and `query_tips` are injected.

**Baseline reference:** Flat registry with only tool name + description in system prompt.

---

## Tier 2 — Compositional Selection

**Purpose:** Test accuracy on multi-step intents requiring correct tool sequencing.

**Setup:**
- Registry: same 50-tool registry as Tier 1
- Test set: 100 compositional intents requiring 2-4 tool steps
- Ground truth: exact tool sequences verified by human raters
- Model: claude-sonnet-4-6 (temperature=0)

**Metrics:**
- Sequence exact match (SEM): fraction of sequences where all steps are correct
- Sequence F1: token-level F1 between predicted and ground truth sequences
- Step accuracy: fraction of individual steps that are correct (position-independent)

**Variants:**
- In-pattern intents (intent has a matching pattern in .tool-fabric.yaml)
- Out-of-pattern intents (intent requires novel composition)

**Expected outcome:** Significant improvement on in-pattern intents where the pattern is injected. Neutral or slight improvement on out-of-pattern.

**Hypothesis:** Pattern injection replaces N tool selection decisions with 1 pattern recognition decision, reducing error accumulation.

---

## Tier 3 — Adversarial Selection

**Purpose:** Test false positive rate when near-miss tools are present.

**Setup:**
- Registry: 20 tool pairs where pair members have cosine similarity > 0.80
- Test set: 100 intents, each targeting one member of a pair
- The wrong tool in each pair is the near-miss
- Model: claude-sonnet-4-6 (temperature=0)

**Metrics:**
- False positive rate (FPR): fraction of calls that select the near-miss
- Precision: true positives / (true positives + false positives)

**Variants:**
- No annotations (baseline)
- With `alternatives` + `query_tips` only
- With full tool-fabric annotations (concepts, patterns, properties)

**Expected outcome:** Largest improvement in this tier, since alternatives + query_tips directly address the disambiguation failure.

**Design note:** Each near-miss pair should be manually verified to ensure the two tools genuinely overlap and are genuinely different in the test intents. Near-miss pairs must not be strawman cases where the tools are trivially distinguishable.

---

## Test Set Construction

Test intents are constructed by:
1. Writing a ground-truth tool call for each intent
2. Verifying with a second human rater (inter-rater agreement > 0.9)
3. Checking that the intent is not solvable by description keyword matching alone

Intents that can be solved by simple keyword matching are excluded — they do not discriminate between annotated and unannotated registries.

---

## Evaluation Harness

The evaluation harness will be implemented in `benchmarks/eval.py` (planned). It will:
- Accept a registry file and test set JSON
- Run the model with the specified prompt strategy
- Compute all metrics and output a results JSON
- Compare against a baseline and compute delta with confidence intervals

---

## Planned Test Sets

| File | Description | Status |
|------|-------------|--------|
| `tier1_low_overlap.json` | 200 single-step intents, distinct tools | Planned |
| `tier1_high_overlap.json` | 200 single-step intents, overlapping tools | Planned |
| `tier2_in_pattern.json` | 100 compositional intents matching patterns | Planned |
| `tier2_out_of_pattern.json` | 100 compositional intents, no pattern | Planned |
| `tier3_adversarial.json` | 100 near-miss selection intents | Planned |

---

## Current Status

Benchmarks are defined but not yet executed. The evaluation harness and test sets are under construction.

If you run these benchmarks against your own registry, please share results as a GitHub issue. The goal is to build an empirical evidence base for tool-fabric's effectiveness across different registry sizes and domains.
