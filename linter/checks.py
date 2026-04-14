"""
Individual lint check implementations for tool-fabric.

Each check is a function that receives a Registry and returns a list of Violations.
Checks are registered via the @check decorator and run by run_checks().
"""

from __future__ import annotations

import enum
import math
import re
from dataclasses import dataclass, field
from typing import Any


# ── Data model ────────────────────────────────────────────────────────────────


class Severity(enum.IntEnum):
    INFO = 1
    WARNING = 2
    ERROR = 3


@dataclass
class Violation:
    code: str
    severity: Severity
    message: str
    tool_id: str | None = None
    pattern_id: str | None = None
    concept_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.name,
            "message": self.message,
            "tool_id": self.tool_id,
            "pattern_id": self.pattern_id,
            "concept_id": self.concept_id,
        }


@dataclass
class LintResult:
    violations: list[Violation] = field(default_factory=list)

    @property
    def errors(self):
        return [v for v in self.violations if v.severity == Severity.ERROR]

    @property
    def warnings(self):
        return [v for v in self.violations if v.severity == Severity.WARNING]

    @property
    def infos(self):
        return [v for v in self.violations if v.severity == Severity.INFO]

    def passed(self, min_severity: Severity = Severity.ERROR) -> bool:
        return not any(v.severity >= min_severity for v in self.violations)


@dataclass
class Registry:
    raw: dict[str, Any]
    source_file: str = "<unknown>"

    @property
    def tools(self) -> dict[str, dict]:
        return self.raw.get("tools") or {}

    @property
    def concepts(self) -> dict[str, dict]:
        return self.raw.get("concepts") or {}

    @property
    def patterns(self) -> dict[str, dict]:
        return self.raw.get("patterns") or {}

    @property
    def properties(self) -> dict[str, Any]:
        return self.raw.get("properties") or {}


# ── Check registry ────────────────────────────────────────────────────────────

_CHECKS: list = []


def check(fn):
    """Register a check function."""
    _CHECKS.append(fn)
    return fn


def run_checks(registry: Registry) -> list[Violation]:
    violations = []
    for fn in _CHECKS:
        violations.extend(fn(registry))
    return violations


# ── E001 — Undeclared Overlap ─────────────────────────────────────────────────


@check
def check_undeclared_overlap(registry: Registry) -> list[Violation]:
    """
    E001: Two tools have high description similarity but no alternatives declaration.

    Algorithm:
    - Attempt to load sentence-transformers; fall back to word-overlap Jaccard
      if the library is not installed.
    - Compute pairwise similarity for all (tool_a, tool_b) pairs.
    - For pairs above the error threshold (0.85), check if either tool declares
      the other in alternatives. If not, emit ERROR.
    - For pairs above the warning threshold (0.70), emit WARNING.

    Similarity backend:
    - Primary: sentence-transformers all-MiniLM-L6-v2 (cosine)
    - Fallback: Jaccard on lowercased word tokens
    """
    tools = registry.tools
    if len(tools) < 2:
        return []

    tool_ids = list(tools.keys())
    descriptions = {
        tid: (tools[tid].get("description") or "").strip()
        for tid in tool_ids
    }

    similarity = _build_similarity_fn(descriptions)
    alternatives_map = _build_alternatives_map(tools)

    violations = []
    seen = set()

    for i, a in enumerate(tool_ids):
        for b in tool_ids[i + 1:]:
            pair = frozenset({a, b})
            if pair in seen:
                continue
            seen.add(pair)

            score = similarity(a, b)

            declared = (
                b in alternatives_map.get(a, set())
                or a in alternatives_map.get(b, set())
            )

            if score >= 0.85 and not declared:
                violations.append(Violation(
                    code="E001",
                    severity=Severity.ERROR,
                    message=(
                        f"Undeclared overlap: '{a}' ↔ '{b}' similarity={score:.2f}. "
                        f"Declare alternatives or add query_tips to disambiguate."
                    ),
                    tool_id=a,
                ))
            elif score >= 0.70 and not declared:
                violations.append(Violation(
                    code="W002",
                    severity=Severity.WARNING,
                    message=(
                        f"Possible overlap: '{a}' ↔ '{b}' similarity={score:.2f}. "
                        f"Consider declaring alternatives."
                    ),
                    tool_id=a,
                ))

    return violations


def _build_similarity_fn(descriptions: dict[str, str]):
    """Return a similarity(a, b) → float function, using best available backend."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")
        tool_ids = list(descriptions.keys())
        texts = [descriptions[tid] for tid in tool_ids]
        embeddings = model.encode(texts, normalize_embeddings=True)
        emb_map = {tid: embeddings[i] for i, tid in enumerate(tool_ids)}

        def cosine(a: str, b: str) -> float:
            return float(np.dot(emb_map[a], emb_map[b]))

        return cosine

    except ImportError:
        # Fallback: Jaccard similarity on word tokens
        token_map = {
            tid: set(desc.lower().split())
            for tid, desc in descriptions.items()
        }

        def jaccard(a: str, b: str) -> float:
            sa, sb = token_map[a], token_map[b]
            if not sa and not sb:
                return 1.0
            intersection = len(sa & sb)
            union = len(sa | sb)
            return intersection / union if union else 0.0

        return jaccard


def _build_alternatives_map(tools: dict) -> dict[str, set[str]]:
    return {
        tid: set(tdata.get("alternatives") or [])
        for tid, tdata in tools.items()
    }


# ── E002 — Broken Composition Edge ────────────────────────────────────────────


@check
def check_broken_composition_edges(registry: Registry) -> list[Violation]:
    """
    E002: A tool lists another in composes_with but the output_shape → input_shape
    contract is not satisfied.

    Algorithm:
    - For each tool A with composes_with = [B, C, ...]:
      - Check that each target tool_id exists in the registry.
      - If A has output_shape and B has input_shape, verify that all required
        fields of B's input_shape are present in A's output_shape with
        compatible types.
    - Emit ERROR for missing required fields; WARNING for type mismatches.

    Note: input_shape fields are treated as optional unless explicitly marked
    required (future: support required[] annotation). For now, we check that
    at least one output field matches at least one input field by name.
    """
    tools = registry.tools
    violations = []

    for tool_id, tdata in tools.items():
        composes_with = tdata.get("composes_with") or []
        output_shape = tdata.get("output_shape") or {}

        for target_id in composes_with:
            if target_id not in tools:
                violations.append(Violation(
                    code="E002",
                    severity=Severity.ERROR,
                    message=(
                        f"Composition edge broken: '{tool_id}' → '{target_id}': "
                        f"target tool '{target_id}' not found in registry."
                    ),
                    tool_id=tool_id,
                ))
                continue

            target_data = tools[target_id]
            input_shape = target_data.get("input_shape") or {}

            if not output_shape or not input_shape:
                # Warn about missing type declarations if composition is declared
                violations.append(Violation(
                    code="W003",
                    severity=Severity.WARNING,
                    message=(
                        f"Composition '{tool_id}' → '{target_id}' declared but "
                        f"{'output_shape' if not output_shape else 'input_shape'} is missing. "
                        f"Cannot validate contract."
                    ),
                    tool_id=tool_id,
                ))
                continue

            # Check for at least one matching field (name-based)
            output_fields = set(output_shape.keys())
            input_fields = set(input_shape.keys())
            overlap = output_fields & input_fields

            if not overlap:
                violations.append(Violation(
                    code="E002",
                    severity=Severity.ERROR,
                    message=(
                        f"Composition contract failure: '{tool_id}' → '{target_id}': "
                        f"no shared fields between output {list(output_fields)} "
                        f"and input {list(input_fields)}."
                    ),
                    tool_id=tool_id,
                ))

    return violations


# ── E003 — Concept Gap ────────────────────────────────────────────────────────


@check
def check_concept_gaps(registry: Registry) -> list[Violation]:
    """
    E003: A tool declares concepts_required entries that are not defined in
    the concepts section.

    Algorithm:
    - Collect all concept_ids from tools[*].concepts_required
    - Collect all defined concept_ids from concepts section
    - Any used-but-not-defined concept_id is an E003 error
    """
    tools = registry.tools
    defined_concepts = set(registry.concepts.keys())
    violations = []

    for tool_id, tdata in tools.items():
        required = tdata.get("concepts_required") or []
        for concept_id in required:
            if concept_id not in defined_concepts:
                violations.append(Violation(
                    code="E003",
                    severity=Severity.ERROR,
                    message=(
                        f"Concept gap: '{tool_id}' requires concept '{concept_id}' "
                        f"which is not defined in the concepts section."
                    ),
                    tool_id=tool_id,
                    concept_id=concept_id,
                ))

    return violations


# ── E004 — Circular Concept Dependency ────────────────────────────────────────


@check
def check_concept_cycles(registry: Registry) -> list[Violation]:
    """
    E004: The concept DAG contains a cycle.

    Algorithm:
    - Build adjacency list from concepts[*].prerequisites
    - Run DFS cycle detection (color marking)
    - Report each back-edge as an E004 error
    """
    concepts = registry.concepts
    violations = []

    # Build adjacency list: concept → its prerequisites
    adj = {
        cid: set(cdata.get("prerequisites") or [])
        for cid, cdata in concepts.items()
    }

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {cid: WHITE for cid in adj}

    def dfs(node: str, path: list[str]) -> bool:
        color[node] = GRAY
        for neighbor in adj.get(node, set()):
            if neighbor not in color:
                continue  # undefined concept — caught by E003
            if color[neighbor] == GRAY:
                cycle_path = path + [neighbor]
                violations.append(Violation(
                    code="E004",
                    severity=Severity.ERROR,
                    message=(
                        f"Circular concept dependency detected: "
                        f"{' → '.join(cycle_path)}"
                    ),
                    concept_id=node,
                ))
                return True
            if color[neighbor] == WHITE:
                if dfs(neighbor, path + [neighbor]):
                    return True
        color[node] = BLACK
        return False

    for cid in adj:
        if color[cid] == WHITE:
            dfs(cid, [cid])

    return violations


# ── E005 — Undeclared Tool in Pattern ─────────────────────────────────────────


@check
def check_pattern_tool_references(registry: Registry) -> list[Violation]:
    """
    E005: A pattern references a tool_id that is not declared in tools section.

    Algorithm:
    - Flatten all tool_ids from patterns[*].tool_sequence (handling both
      sequential strings and parallel arrays)
    - Check each against registry.tools
    """
    tools = registry.tools
    patterns = registry.patterns
    violations = []

    for pattern_id, pdata in patterns.items():
        tool_sequence = pdata.get("tool_sequence") or []
        for step in tool_sequence:
            # Step is either a string (sequential) or list (parallel)
            step_tools = [step] if isinstance(step, str) else step
            for tid in step_tools:
                if tid not in tools:
                    violations.append(Violation(
                        code="E005",
                        severity=Severity.ERROR,
                        message=(
                            f"Pattern '{pattern_id}' references undeclared tool '{tid}'."
                        ),
                        pattern_id=pattern_id,
                        tool_id=tid,
                    ))

    return violations


# ── W001 — Orphan Tool ────────────────────────────────────────────────────────


@check
def check_orphan_tools(registry: Registry) -> list[Violation]:
    """
    W001: A tool is not referenced in any pattern.

    Orphan tools can still be called directly but are not accessible via
    compositional routing. This is a warning, not an error, since some tools
    are legitimately standalone.
    """
    tools = registry.tools
    patterns = registry.patterns
    violations = []

    referenced = set()
    for pdata in patterns.values():
        for step in (pdata.get("tool_sequence") or []):
            step_tools = [step] if isinstance(step, str) else step
            referenced.update(step_tools)

    for tool_id in tools:
        if tool_id not in referenced:
            violations.append(Violation(
                code="W001",
                severity=Severity.WARNING,
                message=(
                    f"Orphan tool: '{tool_id}' is not referenced in any pattern. "
                    f"Consider adding it to a pattern or documenting why it is standalone."
                ),
                tool_id=tool_id,
            ))

    return violations


# ── W004 — Missing concepts_required ─────────────────────────────────────────


@check
def check_missing_concepts(registry: Registry) -> list[Violation]:
    """
    W004: A tool with a non-trivial domain category has no concepts_required.

    Tools in categories like 'utility', 'search', or 'file-system' may
    legitimately have no concept prerequisites. Other categories (project-management,
    communication, code, devops, ai-inference) should declare them.
    """
    TRIVIAL_CATEGORIES = {"utility", "search", "file-system", "formatting"}
    tools = registry.tools
    violations = []

    for tool_id, tdata in tools.items():
        category = (tdata.get("category") or "").lower()
        required = tdata.get("concepts_required") or []
        if category not in TRIVIAL_CATEGORIES and not required:
            violations.append(Violation(
                code="W004",
                severity=Severity.WARNING,
                message=(
                    f"'{tool_id}' (category: {category!r}) has no concepts_required. "
                    f"Declare domain concepts to enable prerequisite chain surfacing."
                ),
                tool_id=tool_id,
            ))

    return violations


# ── I001 — Short Description ──────────────────────────────────────────────────


@check
def check_description_quality(registry: Registry) -> list[Violation]:
    """
    I001: Tool description is shorter than 20 words.
    Likely to cause selection ambiguity at scale.
    """
    tools = registry.tools
    violations = []

    for tool_id, tdata in tools.items():
        desc = (tdata.get("description") or "").strip()
        if not desc:
            violations.append(Violation(
                code="I001",
                severity=Severity.INFO,
                message=f"'{tool_id}': description is missing.",
                tool_id=tool_id,
            ))
        elif len(desc.split()) < 20:
            violations.append(Violation(
                code="I001",
                severity=Severity.INFO,
                message=(
                    f"'{tool_id}': description has {len(desc.split())} words "
                    f"(target: 20-60). Short descriptions reduce selection accuracy."
                ),
                tool_id=tool_id,
            ))

    return violations


# ── I002 — Missing query_tips for alternatives ────────────────────────────────


@check
def check_missing_query_tips(registry: Registry) -> list[Violation]:
    """
    I002: A tool has alternatives declared but no query_tips.
    The router cannot select between alternatives without a selection criterion.
    """
    tools = registry.tools
    violations = []

    for tool_id, tdata in tools.items():
        alternatives = tdata.get("alternatives") or []
        query_tips = (tdata.get("query_tips") or "").strip()
        if alternatives and not query_tips:
            violations.append(Violation(
                code="I002",
                severity=Severity.INFO,
                message=(
                    f"'{tool_id}' has alternatives {alternatives} but no query_tips. "
                    f"Add query_tips to help the router select between them."
                ),
                tool_id=tool_id,
            ))

    return violations


# ── I003 — Missing cost_hints ─────────────────────────────────────────────────


@check
def check_missing_cost_hints(registry: Registry) -> list[Violation]:
    """
    I003: A tool has no cost_hints.
    The orchestrator cannot make scheduling or rate-limit decisions.
    """
    tools = registry.tools
    violations = []

    for tool_id, tdata in tools.items():
        if not tdata.get("cost_hints"):
            violations.append(Violation(
                code="I003",
                severity=Severity.INFO,
                message=(
                    f"'{tool_id}': no cost_hints declared. "
                    f"Add latency_ms, idempotent, and side_effects."
                ),
                tool_id=tool_id,
            ))

    return violations


# ── I004 — Uncovered Concept ──────────────────────────────────────────────────

# Synonym clusters for common registry vocabulary.
# When words from the same cluster appear in descriptions across tools in the
# same MECE group, it signals inconsistent terminology (W006).
_SYNONYM_CLUSTERS: list[frozenset[str]] = [
    frozenset({"issue", "ticket", "task"}),
    frozenset({"message", "email", "notification"}),
    frozenset({"status", "state", "condition", "situation"}),
    frozenset({"auth", "authentication", "credentials", "token"}),
    frozenset({"repository", "repo"}),
    frozenset({"retrieve", "fetch", "get"}),
    frozenset({"send", "post", "deliver"}),
    frozenset({"create", "make", "generate"}),
]


def _synonym_cluster_for(word: str) -> frozenset[str] | None:
    w = word.lower()
    for cluster in _SYNONYM_CLUSTERS:
        if w in cluster:
            return cluster
    return None


@check
def check_concept_coverage(registry: Registry) -> list[Violation]:
    """
    I004: A concept defined in the concept DAG is not referenced by any tool.

    Algorithm:
    - Collect all concept_ids from concepts section.
    - Collect all concept_ids referenced in tools[*].concepts_required.
    - Any defined-but-unreferenced concept is flagged as an I004 info:
      either a missing tool (coverage gap) or a stale concept (cleanup needed).
    """
    defined_concepts = set(registry.concepts.keys())
    referenced: set[str] = set()

    for tdata in registry.tools.values():
        for cid in (tdata.get("concepts_required") or []):
            referenced.add(cid)

    violations = []
    for cid in sorted(defined_concepts - referenced):
        violations.append(Violation(
            code="I004",
            severity=Severity.INFO,
            message=(
                f"Completeness gap: concept '{cid}' is defined in the DAG but "
                f"no tool declares it in concepts_required. "
                f"Add a tool that requires it, or remove the concept."
            ),
            concept_id=cid,
        ))

    return violations


# ── W006 — Vocabulary Incoherence ─────────────────────────────────────────────


@check
def check_vocabulary_coherence(registry: Registry) -> list[Violation]:
    """
    W006: Tools in the same MECE group use inconsistent terminology.

    Algorithm:
    - For each mece_group in properties.mece_groups:
      - Collect and tokenize descriptions for all tools in the group.
      - For each synonym cluster, record which terms each tool uses.
      - If multiple distinct synonyms from the same cluster appear across
        different tools in the group, emit WARNING.

    Rationale (formal framework §3.5):
    If the concept DAG names a concept 'X', all tool descriptions should refer
    to X consistently. Mixed synonyms increase H(T|D) by adding ambiguity that
    purely statistical selection cannot resolve.
    """
    mece_groups = (registry.properties.get("mece_groups") or [])
    tools = registry.tools
    violations = []

    for group in mece_groups:
        intent_class = group.get("intent_class", "unnamed group")
        group_tool_ids = group.get("tools") or []

        # Collect word sets per tool in this group
        tool_words: dict[str, set[str]] = {}
        for tid in group_tool_ids:
            if tid in tools:
                desc = (tools[tid].get("description") or "").strip().lower()
                tool_words[tid] = set(re.findall(r"\b[a-z]+\b", desc))

        if len(tool_words) < 2:
            continue

        # Map each synonym cluster → {tool_id: [matched words]}
        cluster_hits: dict[frozenset, dict[str, list[str]]] = {}
        for tid, words in tool_words.items():
            for word in words:
                cluster = _synonym_cluster_for(word)
                if cluster is None:
                    continue
                cluster_hits.setdefault(cluster, {}).setdefault(tid, []).append(word)

        # Flag clusters where different tools use different synonyms
        for cluster, tool_to_terms in cluster_hits.items():
            if len(tool_to_terms) < 2:
                continue  # Only one tool uses this cluster — no inconsistency
            all_terms = {t for terms in tool_to_terms.values() for t in terms}
            if len(all_terms) <= 1:
                continue  # All tools use the same term — consistent

            tool_list = ", ".join(
                f"'{tid}'→{sorted(set(ts))}"
                for tid, ts in sorted(tool_to_terms.items())
            )
            violations.append(Violation(
                code="W006",
                severity=Severity.WARNING,
                message=(
                    f"Vocabulary inconsistency in MECE group '{intent_class}': "
                    f"mixed synonyms {sorted(all_terms)} detected. "
                    f"Per-tool usage: {tool_list}. "
                    f"Use the concept DAG's canonical term throughout."
                ),
            ))

    return violations


# ── W007 — Minimality Violation ───────────────────────────────────────────────


@check
def check_mergeable_tools(registry: Registry) -> list[Violation]:
    """
    W007: Two tools declared as alternatives have identical input/output shapes.

    Algorithm:
    - For each pair (A, B) where B ∈ alternatives(A):
      - Compare input_shape keys+types and output_shape keys+types.
      - If both shapes are structurally identical, emit WARNING.

    Rationale (formal framework §3.5 — Minimality):
    If two tools have the same intent distribution (same shapes, same purpose)
    they inflate H(T|D) without covering additional intents. They should either
    be merged or distinguished by a shape-level field or query_tips.
    """
    tools = registry.tools
    alternatives_map = _build_alternatives_map(tools)
    violations = []
    seen: set[frozenset] = set()

    for a, a_alts in alternatives_map.items():
        for b in a_alts:
            if b not in tools:
                continue
            pair = frozenset({a, b})
            if pair in seen:
                continue
            seen.add(pair)

            a_in = tools[a].get("input_shape") or {}
            b_in = tools[b].get("input_shape") or {}
            a_out = tools[a].get("output_shape") or {}
            b_out = tools[b].get("output_shape") or {}

            if not (a_in and a_out and b_in and b_out):
                continue  # Can't compare without shapes

            input_match = (
                set(a_in.keys()) == set(b_in.keys())
                and all(a_in[k] == b_in[k] for k in a_in)
            )
            output_match = (
                set(a_out.keys()) == set(b_out.keys())
                and all(a_out[k] == b_out[k] for k in a_out)
            )

            if input_match and output_match:
                violations.append(Violation(
                    code="W007",
                    severity=Severity.WARNING,
                    message=(
                        f"Minimality violation: '{a}' and '{b}' are declared as "
                        f"alternatives and have identical input/output shapes "
                        f"(input: {sorted(a_in.keys())}, output: {sorted(a_out.keys())}). "
                        f"Consider merging into one tool or adding a distinguishing field."
                    ),
                    tool_id=a,
                ))

    return violations
