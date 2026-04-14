"""
Unit tests for tool-fabric lint checks.

Fixture conventions:
- Use Registry(raw={...}) directly — no file I/O needed.
- Each test function covers a single check, with a passing case and failing case.
- Tests exercise the checks via run_checks() as well as the individual functions
  to ensure they are properly registered.

Covers: E001-E005, W001, W003-W007, I001-I004 and the Jaccard similarity backend.
"""

from __future__ import annotations

import pytest

from linter.checks import (
    Registry,
    Severity,
    Violation,
    check_broken_composition_edges,
    check_concept_coverage,
    check_concept_cycles,
    check_concept_gaps,
    check_description_quality,
    check_mergeable_tools,
    check_missing_concepts,
    check_missing_cost_hints,
    check_missing_query_tips,
    check_orphan_tools,
    check_pattern_tool_references,
    check_undeclared_overlap,
    check_undefined_alternative_references,
    check_vocabulary_coherence,
    run_checks,
    _build_similarity_fn,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_registry(tools=None, concepts=None, patterns=None, properties=None) -> Registry:
    return Registry(raw={
        "tools": tools or {},
        "concepts": concepts or {},
        "patterns": patterns or {},
        "properties": properties or {},
    })


def codes(violations: list[Violation]) -> list[str]:
    return [v.code for v in violations]


# ── Jaccard similarity backend ─────────────────────────────────────────────────


class TestJaccardSimilarity:
    def test_identical_descriptions(self):
        """Identical token sets → similarity = 1.0."""
        fn = _build_similarity_fn({"a": "foo bar baz", "b": "foo bar baz"})
        assert fn("a", "b") == pytest.approx(1.0)

    def test_disjoint_descriptions(self):
        """Completely disjoint token sets → similarity = 0.0."""
        fn = _build_similarity_fn({"a": "foo bar baz", "b": "qux quux corge"})
        assert fn("a", "b") == pytest.approx(0.0)

    def test_partial_overlap(self):
        """Partial overlap → correct Jaccard score."""
        # intersection={a,b,c}=3, union={a,b,c,d,e}=5 → 0.6
        fn = _build_similarity_fn({"x": "a b c", "y": "a b c d e"})
        assert fn("x", "y") == pytest.approx(3 / 5)

    def test_empty_descriptions(self):
        """Both empty → similarity = 1.0 (both cover same empty set)."""
        fn = _build_similarity_fn({"a": "", "b": ""})
        assert fn("a", "b") == pytest.approx(1.0)


# ── E001 — Undeclared Overlap ─────────────────────────────────────────────────


class TestUndeclaredOverlap:
    def test_no_violation_when_declared(self):
        tools = {
            "search_github": {
                "description": "Searches GitHub issues by query string and returns matching items.",
                "alternatives": ["search_linear"],
            },
            "search_linear": {
                "description": "Searches Linear issues by query string and returns matching items.",
                "alternatives": ["search_github"],
            },
        }
        violations = check_undeclared_overlap(make_registry(tools=tools))
        assert not any(v.code == "E001" for v in violations)

    def test_no_violation_low_similarity(self):
        tools = {
            "create_event": {
                "description": "Creates a calendar event on Google Calendar.",
                "alternatives": [],
            },
            "send_email": {
                "description": "Sends an email via Gmail to external recipients.",
                "alternatives": [],
            },
        }
        violations = check_undeclared_overlap(make_registry(tools=tools))
        assert "E001" not in codes(violations)

    def test_warning_moderate_similarity_undeclared(self):
        # Identical descriptions, no alternatives declared → should get E001 or W002
        tools = {
            "tool_a": {
                "description": "Searches issues by query string and returns matching items quickly.",
                "alternatives": [],
            },
            "tool_b": {
                "description": "Searches issues by query string and returns matching items quickly.",
                "alternatives": [],
            },
        }
        violations = check_undeclared_overlap(make_registry(tools=tools))
        # Jaccard of identical descriptions is 1.0 → E001
        assert any(v.code in ("E001", "W002") for v in violations)

    def test_single_tool_no_violation(self):
        tools = {
            "only_tool": {"description": "Does one unique thing.", "alternatives": []},
        }
        assert check_undeclared_overlap(make_registry(tools=tools)) == []


# ── E002 — Broken Composition Edge ────────────────────────────────────────────


class TestBrokenCompositionEdges:
    def test_missing_target_tool(self):
        tools = {
            "tool_a": {
                "composes_with": ["nonexistent_tool"],
                "output_shape": {"result": "string"},
            },
        }
        violations = check_broken_composition_edges(make_registry(tools=tools))
        assert "E002" in codes(violations)

    def test_no_shared_fields(self):
        tools = {
            "tool_a": {
                "composes_with": ["tool_b"],
                "output_shape": {"result": "string"},
            },
            "tool_b": {
                "composes_with": [],
                "input_shape": {"data": "object"},
                "output_shape": {},
            },
        }
        violations = check_broken_composition_edges(make_registry(tools=tools))
        assert "E002" in codes(violations)

    def test_valid_composition(self):
        tools = {
            "tool_a": {
                "composes_with": ["tool_b"],
                "output_shape": {"result": "string", "count": "integer"},
            },
            "tool_b": {
                "composes_with": [],
                "input_shape": {"result": "string"},
                "output_shape": {"processed": "boolean"},
            },
        }
        violations = check_broken_composition_edges(make_registry(tools=tools))
        assert "E002" not in codes(violations)

    def test_missing_shape_emits_w003(self):
        tools = {
            "tool_a": {
                "composes_with": ["tool_b"],
                "output_shape": {},
            },
            "tool_b": {
                "input_shape": {"x": "string"},
                "output_shape": {"y": "string"},
            },
        }
        violations = check_broken_composition_edges(make_registry(tools=tools))
        assert "W003" in codes(violations)


# ── E003 — Concept Gap ────────────────────────────────────────────────────────


class TestConceptGaps:
    def test_undefined_concept_required(self):
        tools = {
            "tool_a": {"concepts_required": ["undefined.concept"]},
        }
        violations = check_concept_gaps(make_registry(tools=tools))
        assert "E003" in codes(violations)
        assert any(v.concept_id == "undefined.concept" for v in violations)

    def test_defined_concept_no_violation(self):
        tools = {
            "tool_a": {"concepts_required": ["auth.token"]},
        }
        concepts = {"auth.token": {"description": "Auth token.", "prerequisites": []}}
        violations = check_concept_gaps(make_registry(tools=tools, concepts=concepts))
        assert "E003" not in codes(violations)

    def test_no_concepts_required_no_violation(self):
        tools = {"tool_a": {"concepts_required": []}}
        violations = check_concept_gaps(make_registry(tools=tools))
        assert violations == []


# ── E004 — Circular Concept Dependency ────────────────────────────────────────


class TestConceptCycles:
    def test_cycle_detected(self):
        concepts = {
            "A": {"prerequisites": ["B"]},
            "B": {"prerequisites": ["C"]},
            "C": {"prerequisites": ["A"]},
        }
        violations = check_concept_cycles(make_registry(concepts=concepts))
        assert "E004" in codes(violations)

    def test_no_cycle(self):
        concepts = {
            "A": {"prerequisites": []},
            "B": {"prerequisites": ["A"]},
            "C": {"prerequisites": ["B"]},
        }
        violations = check_concept_cycles(make_registry(concepts=concepts))
        assert "E004" not in codes(violations)

    def test_self_loop_detected(self):
        concepts = {"A": {"prerequisites": ["A"]}}
        violations = check_concept_cycles(make_registry(concepts=concepts))
        assert "E004" in codes(violations)

    def test_diamond_dag_no_cycle(self):
        # A → B, A → C, B → D, C → D — valid diamond, no cycle
        concepts = {
            "A": {"prerequisites": ["B", "C"]},
            "B": {"prerequisites": ["D"]},
            "C": {"prerequisites": ["D"]},
            "D": {"prerequisites": []},
        }
        violations = check_concept_cycles(make_registry(concepts=concepts))
        assert "E004" not in codes(violations)


# ── E005 — Undeclared Tool in Pattern ─────────────────────────────────────────


class TestPatternToolReferences:
    def test_undeclared_tool_in_sequence(self):
        patterns = {
            "p1": {"tool_sequence": ["tool_a", "missing_tool"]},
        }
        tools = {"tool_a": {}}
        violations = check_pattern_tool_references(make_registry(tools=tools, patterns=patterns))
        assert "E005" in codes(violations)
        assert any(v.tool_id == "missing_tool" for v in violations)

    def test_all_tools_declared(self):
        patterns = {
            "p1": {"tool_sequence": ["tool_a", ["tool_b", "tool_c"]]},
        }
        tools = {"tool_a": {}, "tool_b": {}, "tool_c": {}}
        violations = check_pattern_tool_references(make_registry(tools=tools, patterns=patterns))
        assert "E005" not in codes(violations)

    def test_parallel_step_missing_tool(self):
        patterns = {
            "p1": {"tool_sequence": [["tool_a", "ghost"]]},
        }
        tools = {"tool_a": {}}
        violations = check_pattern_tool_references(make_registry(tools=tools, patterns=patterns))
        assert "E005" in codes(violations)

    def test_no_violation_when_all_tools_declared(self):
        patterns = {"p1": {"tool_sequence": ["tool_a"]}}
        tools = {"tool_a": {}}
        violations = check_pattern_tool_references(make_registry(tools=tools, patterns=patterns))
        assert "E005" not in codes(violations)


# ── W001 — Orphan Tool ────────────────────────────────────────────────────────


class TestOrphanTools:
    def test_orphan_detected(self):
        tools = {"tool_a": {}, "tool_b": {}}
        patterns = {"p1": {"tool_sequence": ["tool_a"]}}
        violations = check_orphan_tools(make_registry(tools=tools, patterns=patterns))
        assert "W001" in codes(violations)
        assert any(v.tool_id == "tool_b" for v in violations)

    def test_no_orphan_when_all_referenced(self):
        tools = {"tool_a": {}, "tool_b": {}}
        patterns = {"p1": {"tool_sequence": ["tool_a", "tool_b"]}}
        violations = check_orphan_tools(make_registry(tools=tools, patterns=patterns))
        assert "W001" not in codes(violations)

    def test_no_patterns_all_orphans(self):
        tools = {"tool_a": {}, "tool_b": {}}
        violations = check_orphan_tools(make_registry(tools=tools))
        assert len([v for v in violations if v.code == "W001"]) == 2


# ── W004 — Missing concepts_required ─────────────────────────────────────────


class TestMissingConcepts:
    def test_non_trivial_category_without_concepts(self):
        tools = {
            "tool_a": {"category": "communication", "concepts_required": []},
        }
        violations = check_missing_concepts(make_registry(tools=tools))
        assert "W004" in codes(violations)

    def test_trivial_category_exempt(self):
        tools = {
            "tool_a": {"category": "search", "concepts_required": []},
        }
        violations = check_missing_concepts(make_registry(tools=tools))
        assert "W004" not in codes(violations)

    def test_non_trivial_with_concepts_no_violation(self):
        tools = {
            "tool_a": {"category": "devops", "concepts_required": ["github.auth"]},
        }
        violations = check_missing_concepts(make_registry(tools=tools))
        assert "W004" not in codes(violations)

    def test_no_violation_for_trivial_category(self):
        tools = {
            "tool_a": {"category": "file-system", "concepts_required": []},
        }
        violations = check_missing_concepts(make_registry(tools=tools))
        assert "W004" not in codes(violations)


# ── W005 — Undefined Alternative Reference ────────────────────────────────────


class TestUndefinedAlternativeReferences:
    def test_alternative_references_undefined_tool(self):
        """alternatives references a tool not in the registry → W005."""
        tools = {
            "tool_a": {
                "category": "project-management",
                "description": "creates an issue",
                "alternatives": ["nonexistent_tool"],
            }
        }
        violations = check_undefined_alternative_references(make_registry(tools=tools))
        assert any(v.code == "W005" and "nonexistent_tool" in v.message for v in violations)

    def test_no_violation_when_all_alternatives_defined(self):
        """All alternatives are defined → no W005."""
        tools = {
            "tool_a": {
                "category": "utility",
                "description": "does X",
                "alternatives": ["tool_b"],
            },
            "tool_b": {
                "category": "utility",
                "description": "does X differently",
                "alternatives": ["tool_a"],
            },
        }
        assert check_undefined_alternative_references(make_registry(tools=tools)) == []

    def test_no_alternatives_no_violation(self):
        """No alternatives declared → no W005."""
        tools = {"tool_a": {"category": "utility", "alternatives": []}}
        assert check_undefined_alternative_references(make_registry(tools=tools)) == []


# ── I001 — Short Description ──────────────────────────────────────────────────


class TestDescriptionQuality:
    def test_missing_description(self):
        tools = {"tool_a": {}}
        violations = check_description_quality(make_registry(tools=tools))
        assert "I001" in codes(violations)

    def test_short_description(self):
        tools = {"tool_a": {"description": "Does something."}}
        violations = check_description_quality(make_registry(tools=tools))
        assert "I001" in codes(violations)

    def test_adequate_description(self):
        tools = {
            "tool_a": {
                "description": (
                    "Searches GitHub issues by query string and returns a ranked "
                    "list of matching issues, pull requests, and discussions. "
                    "Use before creating a new issue to check for duplicates."
                )
            }
        }
        violations = check_description_quality(make_registry(tools=tools))
        assert "I001" not in codes(violations)

    def test_missing_description_message_contains_missing(self):
        tools = {"tool_a": {"category": "utility"}}
        violations = check_description_quality(make_registry(tools=tools))
        assert any(v.code == "I001" and "missing" in v.message for v in violations)


# ── I002 — Missing query_tips for alternatives ────────────────────────────────


class TestMissingQueryTips:
    def test_alternatives_without_query_tips(self):
        tools = {
            "tool_a": {"alternatives": ["tool_b"], "query_tips": ""},
        }
        violations = check_missing_query_tips(make_registry(tools=tools))
        assert "I002" in codes(violations)

    def test_alternatives_with_query_tips(self):
        tools = {
            "tool_a": {"alternatives": ["tool_b"], "query_tips": "Use when X, not Y."},
        }
        violations = check_missing_query_tips(make_registry(tools=tools))
        assert "I002" not in codes(violations)

    def test_no_alternatives_no_violation(self):
        tools = {"tool_a": {"alternatives": [], "query_tips": ""}}
        violations = check_missing_query_tips(make_registry(tools=tools))
        assert "I002" not in codes(violations)


# ── I003 — Missing cost_hints ─────────────────────────────────────────────────


class TestMissingCostHints:
    def test_missing_cost_hints(self):
        tools = {"tool_a": {}}
        violations = check_missing_cost_hints(make_registry(tools=tools))
        assert "I003" in codes(violations)

    def test_cost_hints_present(self):
        tools = {
            "tool_a": {"cost_hints": {"latency_ms": 100, "idempotent": True, "side_effects": []}},
        }
        violations = check_missing_cost_hints(make_registry(tools=tools))
        assert "I003" not in codes(violations)


# ── I004 — Uncovered Concept ──────────────────────────────────────────────────


class TestConceptCoverage:
    def test_uncovered_concept_flagged(self):
        concepts = {
            "auth.token": {"description": "Auth token.", "prerequisites": []},
            "orphaned.concept": {"description": "Nothing uses this.", "prerequisites": []},
        }
        tools = {
            "tool_a": {"concepts_required": ["auth.token"]},
        }
        violations = check_concept_coverage(make_registry(tools=tools, concepts=concepts))
        assert "I004" in codes(violations)
        assert any(v.concept_id == "orphaned.concept" for v in violations)

    def test_all_concepts_covered(self):
        concepts = {
            "auth.token": {"description": "Auth token.", "prerequisites": []},
        }
        tools = {
            "tool_a": {"concepts_required": ["auth.token"]},
        }
        violations = check_concept_coverage(make_registry(tools=tools, concepts=concepts))
        assert "I004" not in codes(violations)

    def test_no_concepts_no_violation(self):
        violations = check_concept_coverage(make_registry())
        assert "I004" not in codes(violations)

    def test_multiple_uncovered_concepts(self):
        concepts = {
            "a": {"description": ".", "prerequisites": []},
            "b": {"description": ".", "prerequisites": []},
            "c": {"description": ".", "prerequisites": []},
        }
        tools = {}  # No tools reference any concept
        violations = check_concept_coverage(make_registry(tools=tools, concepts=concepts))
        i004 = [v for v in violations if v.code == "I004"]
        assert len(i004) == 3


# ── W006 — Vocabulary Incoherence ─────────────────────────────────────────────


class TestVocabularyCoherence:
    def test_mixed_synonyms_in_mece_group(self):
        tools = {
            "send_slack": {
                "description": (
                    "Sends a message to a Slack channel for team notifications "
                    "and async communication. Use for internal messaging."
                ),
            },
            "send_email": {
                "description": (
                    "Sends an email to external recipients via Gmail. "
                    "Use for formal communications and email threads."
                ),
            },
        }
        properties = {
            "mece_groups": [
                {
                    "intent_class": "send a message",
                    "tools": ["send_slack", "send_email"],
                }
            ]
        }
        violations = check_vocabulary_coherence(make_registry(tools=tools, properties=properties))
        assert "W006" in codes(violations)

    def test_consistent_vocabulary_no_violation(self):
        tools = {
            "create_github_issue": {
                "description": (
                    "Creates a new issue in GitHub repository for tracking bugs "
                    "and feature requests. Use for GitHub-hosted projects."
                ),
            },
            "create_linear_issue": {
                "description": (
                    "Creates a new issue in a Linear project for sprint tracking. "
                    "Use for Linear-managed team projects."
                ),
            },
        }
        properties = {
            "mece_groups": [
                {
                    "intent_class": "create a tracking issue",
                    "tools": ["create_github_issue", "create_linear_issue"],
                }
            ]
        }
        violations = check_vocabulary_coherence(make_registry(tools=tools, properties=properties))
        # Both use "issue" consistently — W006 should not fire for the issue cluster
        assert not any(
            v.code == "W006" and "issue" in v.message
            for v in violations
        )

    def test_no_mece_groups_no_violation(self):
        tools = {"tool_a": {"description": "Does something useful."}}
        violations = check_vocabulary_coherence(make_registry(tools=tools))
        assert "W006" not in codes(violations)

    def test_single_tool_in_group_no_violation(self):
        tools = {"tool_a": {"description": "Sends a notification to the team."}}
        properties = {
            "mece_groups": [{"intent_class": "notify", "tools": ["tool_a"]}]
        }
        violations = check_vocabulary_coherence(make_registry(tools=tools, properties=properties))
        assert "W006" not in codes(violations)


# ── W007 — Minimality Violation ───────────────────────────────────────────────


class TestMergeableTools:
    def test_identical_shapes_flagged(self):
        tools = {
            "tool_a": {
                "alternatives": ["tool_b"],
                "input_shape": {"model": "string", "prompt": "string"},
                "output_shape": {"response": "string", "usage_tokens": "integer"},
            },
            "tool_b": {
                "alternatives": ["tool_a"],
                "input_shape": {"model": "string", "prompt": "string"},
                "output_shape": {"response": "string", "usage_tokens": "integer"},
            },
        }
        violations = check_mergeable_tools(make_registry(tools=tools))
        assert "W007" in codes(violations)

    def test_different_input_shapes_no_violation(self):
        tools = {
            "tool_a": {
                "alternatives": ["tool_b"],
                "input_shape": {"repo": "string", "title": "string"},
                "output_shape": {"issue_url": "string"},
            },
            "tool_b": {
                "alternatives": ["tool_a"],
                "input_shape": {"team_id": "string", "title": "string"},
                "output_shape": {"issue_url": "string"},
            },
        }
        violations = check_mergeable_tools(make_registry(tools=tools))
        assert "W007" not in codes(violations)

    def test_different_output_shapes_no_violation(self):
        tools = {
            "tool_a": {
                "alternatives": ["tool_b"],
                "input_shape": {"query": "string"},
                "output_shape": {"results": "array", "total_count": "integer"},
            },
            "tool_b": {
                "alternatives": ["tool_a"],
                "input_shape": {"query": "string"},
                "output_shape": {"items": "array"},  # different field name
            },
        }
        violations = check_mergeable_tools(make_registry(tools=tools))
        assert "W007" not in codes(violations)

    def test_missing_shapes_no_false_positive(self):
        tools = {
            "tool_a": {"alternatives": ["tool_b"]},
            "tool_b": {"alternatives": ["tool_a"]},
        }
        violations = check_mergeable_tools(make_registry(tools=tools))
        assert "W007" not in codes(violations)

    def test_pair_counted_once(self):
        tools = {
            "tool_a": {
                "alternatives": ["tool_b"],
                "input_shape": {"x": "string"},
                "output_shape": {"y": "string"},
            },
            "tool_b": {
                "alternatives": ["tool_a"],
                "input_shape": {"x": "string"},
                "output_shape": {"y": "string"},
            },
        }
        violations = check_mergeable_tools(make_registry(tools=tools))
        # Should fire exactly once for the pair, not twice
        assert codes(violations).count("W007") == 1


# ── run_checks — integration ──────────────────────────────────────────────────


class TestRunChecks:
    def test_all_checks_registered(self):
        """run_checks() runs all checks including the new ones."""
        # A registry that will trigger I004 (orphaned concept) and I001 (short desc)
        reg = make_registry(
            tools={"tool_a": {"description": "Short.", "concepts_required": []}},
            concepts={"orphan.concept": {"description": "unused", "prerequisites": []}},
        )
        violations = run_checks(reg)
        found_codes = set(codes(violations))
        assert "I004" in found_codes  # orphaned concept
        assert "I001" in found_codes  # short description

    def test_clean_registry_no_errors(self):
        """A well-formed minimal registry produces no ERROR violations."""
        reg = make_registry(
            tools={
                "tool_a": {
                    "category": "utility",
                    "description": (
                        "Performs a utility operation and returns the result. "
                        "Use when you need to process data without side effects."
                    ),
                    "concepts_required": [],
                    "alternatives": [],
                    "composes_with": [],
                    "cost_hints": {"latency_ms": 50, "idempotent": True, "side_effects": []},
                }
            },
            patterns={"p1": {"tool_sequence": ["tool_a"]}},
        )
        violations = run_checks(reg)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert errors == []

    def test_returns_list(self):
        """run_checks always returns a list."""
        reg = make_registry()
        assert isinstance(run_checks(reg), list)
