"""
Tests for tool-fabric linter checks.

Covers: E001-E005, W001, W003, W004, W005, I001, I002, I003
and the Jaccard similarity fallback backend.
"""

from __future__ import annotations

import pytest

from linter.checks import (
    Registry,
    Severity,
    Violation,
    check_broken_composition_edges,
    check_concept_cycles,
    check_concept_gaps,
    check_description_quality,
    check_missing_concepts,
    check_missing_cost_hints,
    check_missing_query_tips,
    check_orphan_tools,
    check_pattern_tool_references,
    check_undeclared_overlap,
    check_undefined_alternative_references,
    run_checks,
    _build_similarity_fn,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def make_registry(raw: dict) -> Registry:
    return Registry(raw, source_file="<test>")


def codes(violations: list[Violation]) -> list[str]:
    return [v.code for v in violations]


# ── Jaccard similarity backend ─────────────────────────────────────────────────


def test_jaccard_identical_descriptions():
    """Identical token sets → similarity = 1.0."""
    fn = _build_similarity_fn({"a": "foo bar baz", "b": "foo bar baz"})
    assert fn("a", "b") == pytest.approx(1.0)


def test_jaccard_disjoint_descriptions():
    """Completely disjoint token sets → similarity = 0.0."""
    fn = _build_similarity_fn({"a": "foo bar baz", "b": "qux quux corge"})
    assert fn("a", "b") == pytest.approx(0.0)


def test_jaccard_partial_overlap():
    """Partial overlap → correct Jaccard score."""
    # intersection={a,b,c}=3, union={a,b,c,d,e}=5 → 0.6
    fn = _build_similarity_fn({"x": "a b c", "y": "a b c d e"})
    assert fn("x", "y") == pytest.approx(3 / 5)


def test_jaccard_empty_descriptions():
    """Two empty descriptions → both backends treat as identical (1.0 or 0.0).
    The Jaccard fallback returns 1.0 for two empty sets by convention."""
    fn = _build_similarity_fn({"x": "", "y": ""})
    # Both empty → treated as identical
    assert fn("x", "y") == pytest.approx(1.0)


# ── E001 — Undeclared Overlap ──────────────────────────────────────────────────


def test_e001_identical_descriptions_no_alternatives_triggers_error():
    """Identical descriptions (Jaccard=1.0) without alternatives → E001."""
    desc = "sends a message to a channel and returns the message timestamp"
    registry = make_registry({
        "tools": {
            "tool_a": {"category": "communication", "description": desc, "alternatives": []},
            "tool_b": {"category": "communication", "description": desc, "alternatives": []},
        }
    })
    violations = check_undeclared_overlap(registry)
    assert "E001" in codes(violations)


def test_e001_suppressed_when_alternatives_declared():
    """High-similarity tools with mutual alternatives declared → no E001."""
    desc_a = "sends a message to a Slack channel and returns the message timestamp for threading"
    desc_b = "sends a message to a Slack channel and returns the message timestamp for threading"
    registry = make_registry({
        "tools": {
            "tool_a": {"category": "communication", "description": desc_a, "alternatives": ["tool_b"]},
            "tool_b": {"category": "communication", "description": desc_b, "alternatives": ["tool_a"]},
        }
    })
    violations = check_undeclared_overlap(registry)
    assert "E001" not in codes(violations)


def test_e001_single_tool_no_violations():
    """A registry with only one tool cannot have pairwise overlap."""
    registry = make_registry({
        "tools": {"tool_a": {"category": "utility", "description": "does something unique"}}
    })
    assert check_undeclared_overlap(registry) == []


# ── E002 — Broken Composition Edge ────────────────────────────────────────────


def test_e002_nonexistent_composes_with_target():
    """composes_with references a tool not in the registry → E002."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "utility",
                "description": "does something",
                "composes_with": ["ghost_tool"],
                "output_shape": {"id": "string"},
            }
        }
    })
    violations = check_broken_composition_edges(registry)
    assert any(v.code == "E002" and "ghost_tool" in v.message for v in violations)


def test_e002_no_shared_fields_triggers_error():
    """composes_with target exists but output/input shapes share no fields → E002."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "utility",
                "description": "produces a result",
                "composes_with": ["tool_b"],
                "output_shape": {"result": "string"},
            },
            "tool_b": {
                "category": "utility",
                "description": "consumes a payload",
                "input_shape": {"payload": "string"},
            },
        }
    })
    violations = check_broken_composition_edges(registry)
    assert "E002" in codes(violations)


def test_e002_no_violation_when_shapes_overlap():
    """Output and input share a field by name → no E002."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "utility",
                "description": "produces an id",
                "composes_with": ["tool_b"],
                "output_shape": {"id": "string", "name": "string"},
            },
            "tool_b": {
                "category": "utility",
                "description": "consumes an id",
                "input_shape": {"id": "string"},
            },
        }
    })
    violations = check_broken_composition_edges(registry)
    assert "E002" not in codes(violations)


def test_w003_missing_shapes_on_composed_pair():
    """composes_with declared but at least one shape is missing → W003."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "utility",
                "description": "does something",
                "composes_with": ["tool_b"],
                # no output_shape
            },
            "tool_b": {
                "category": "utility",
                "description": "does something else",
                # no input_shape
            },
        }
    })
    violations = check_broken_composition_edges(registry)
    assert "W003" in codes(violations)


# ── E003 — Concept Gap ────────────────────────────────────────────────────────


def test_e003_undefined_concept_triggers_error():
    """concepts_required references a concept not in concepts section → E003."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "devops",
                "description": "deploys to GitHub",
                "concepts_required": ["github.auth", "missing.concept"],
            }
        },
        "concepts": {
            "github.auth": {"description": "GitHub API token", "prerequisites": []}
        },
    })
    violations = check_concept_gaps(registry)
    assert any(v.code == "E003" and "missing.concept" in v.message for v in violations)


def test_e003_no_violation_when_all_concepts_defined():
    """All concepts_required entries have definitions → no E003."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "devops",
                "description": "deploys to GitHub",
                "concepts_required": ["github.auth"],
            }
        },
        "concepts": {
            "github.auth": {"description": "GitHub API token", "prerequisites": []}
        },
    })
    assert check_concept_gaps(registry) == []


# ── E004 — Circular Concept Dependency ────────────────────────────────────────


def test_e004_direct_cycle_triggers_error():
    """A → B → A is a cycle → E004."""
    registry = make_registry({
        "tools": {},
        "concepts": {
            "a": {"description": "concept a", "prerequisites": ["b"]},
            "b": {"description": "concept b", "prerequisites": ["a"]},
        },
    })
    violations = check_concept_cycles(registry)
    assert "E004" in codes(violations)


def test_e004_three_node_cycle_triggers_error():
    """A → B → C → A is a cycle → E004."""
    registry = make_registry({
        "tools": {},
        "concepts": {
            "a": {"description": "a", "prerequisites": ["b"]},
            "b": {"description": "b", "prerequisites": ["c"]},
            "c": {"description": "c", "prerequisites": ["a"]},
        },
    })
    violations = check_concept_cycles(registry)
    assert "E004" in codes(violations)


def test_e004_no_violation_for_valid_dag():
    """Linear chain A → B → C has no cycle → no E004."""
    registry = make_registry({
        "tools": {},
        "concepts": {
            "a": {"description": "root", "prerequisites": []},
            "b": {"description": "child", "prerequisites": ["a"]},
            "c": {"description": "grandchild", "prerequisites": ["b"]},
        },
    })
    assert check_concept_cycles(registry) == []


def test_e004_diamond_dag_no_cycle():
    """Diamond: A→B, A→C, B→D, C→D — no cycle."""
    registry = make_registry({
        "tools": {},
        "concepts": {
            "a": {"description": "root", "prerequisites": []},
            "b": {"description": "left", "prerequisites": ["a"]},
            "c": {"description": "right", "prerequisites": ["a"]},
            "d": {"description": "bottom", "prerequisites": ["b", "c"]},
        },
    })
    assert check_concept_cycles(registry) == []


# ── E005 — Undeclared Tool in Pattern ─────────────────────────────────────────


def test_e005_pattern_references_ghost_tool():
    """Pattern tool_sequence references a tool not in tools section → E005."""
    registry = make_registry({
        "tools": {"real_tool": {"category": "utility", "description": "does stuff"}},
        "patterns": {
            "bad_pattern": {
                "intent_triggers": ["do the thing"],
                "tool_sequence": ["real_tool", "ghost_tool"],
            }
        },
    })
    violations = check_pattern_tool_references(registry)
    assert any(v.code == "E005" and "ghost_tool" in v.message for v in violations)


def test_e005_parallel_step_references_ghost_tool():
    """Ghost tool in a parallel fan-out step → E005."""
    registry = make_registry({
        "tools": {"real_tool": {"category": "utility", "description": "does stuff"}},
        "patterns": {
            "fan_out": {
                "intent_triggers": ["fan out"],
                "tool_sequence": [["real_tool", "ghost_tool"]],
            }
        },
    })
    violations = check_pattern_tool_references(registry)
    assert "E005" in codes(violations)


def test_e005_no_violation_when_all_tools_declared():
    """All pattern tools are declared → no E005."""
    registry = make_registry({
        "tools": {
            "tool_a": {"category": "utility", "description": "a"},
            "tool_b": {"category": "utility", "description": "b"},
        },
        "patterns": {
            "p": {
                "intent_triggers": ["do"],
                "tool_sequence": ["tool_a", "tool_b"],
            }
        },
    })
    assert check_pattern_tool_references(registry) == []


# ── W001 — Orphan Tool ────────────────────────────────────────────────────────


def test_w001_tool_not_in_any_pattern_is_orphan():
    """Tool referenced in no pattern → W001."""
    registry = make_registry({
        "tools": {
            "used": {"category": "utility", "description": "used in a pattern"},
            "orphan": {"category": "utility", "description": "not used anywhere"},
        },
        "patterns": {
            "p": {"intent_triggers": ["do"], "tool_sequence": ["used"]}
        },
    })
    violations = check_orphan_tools(registry)
    assert any(v.code == "W001" and "orphan" in v.message for v in violations)
    assert not any(v.code == "W001" and "used" in v.message for v in violations)


def test_w001_no_violation_when_all_tools_in_patterns():
    """Every tool appears in a pattern → no W001."""
    registry = make_registry({
        "tools": {
            "tool_a": {"category": "utility", "description": "a"},
            "tool_b": {"category": "utility", "description": "b"},
        },
        "patterns": {
            "p": {"intent_triggers": ["do"], "tool_sequence": [["tool_a", "tool_b"]]}
        },
    })
    assert check_orphan_tools(registry) == []


# ── W005 — Undefined Alternative Reference ────────────────────────────────────


def test_w005_alternative_references_undefined_tool():
    """alternatives references a tool not in the registry → W005."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "project-management",
                "description": "creates an issue",
                "alternatives": ["nonexistent_tool"],
            }
        }
    })
    violations = check_undefined_alternative_references(registry)
    assert any(v.code == "W005" and "nonexistent_tool" in v.message for v in violations)


def test_w005_no_violation_when_all_alternatives_defined():
    """All alternatives are defined → no W005."""
    registry = make_registry({
        "tools": {
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
    })
    assert check_undefined_alternative_references(registry) == []


# ── I001 — Short Description ──────────────────────────────────────────────────


def test_i001_missing_description():
    """No description field → I001 with 'missing' in message."""
    registry = make_registry({
        "tools": {"tool_a": {"category": "utility"}}
    })
    violations = check_description_quality(registry)
    assert any(v.code == "I001" and "missing" in v.message for v in violations)


def test_i001_short_description_triggers_info():
    """Description < 20 words → I001."""
    registry = make_registry({
        "tools": {"tool_a": {"category": "utility", "description": "Does stuff."}}
    })
    violations = check_description_quality(registry)
    assert "I001" in codes(violations)


def test_i001_no_violation_for_adequate_description():
    """Description ≥ 20 words → no I001."""
    desc = (
        "Searches the web for current information and returns ranked results with "
        "titles, URLs, and snippets. Use for facts not in training data. "
        "Do NOT use for internal docs — prefer docs_search."
    )
    registry = make_registry({
        "tools": {"web_search": {"category": "search", "description": desc}}
    })
    assert "I001" not in codes(check_description_quality(registry))


# ── I002 — Missing query_tips ─────────────────────────────────────────────────


def test_i002_alternatives_without_query_tips():
    """alternatives declared but no query_tips → I002."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "utility",
                "description": "does X",
                "alternatives": ["tool_b"],
            }
        }
    })
    violations = check_missing_query_tips(registry)
    assert "I002" in codes(violations)


def test_i002_no_violation_when_query_tips_present():
    """alternatives + query_tips → no I002."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "utility",
                "description": "does X",
                "alternatives": ["tool_b"],
                "query_tips": "Use tool_a when X. Use tool_b when Y.",
            }
        }
    })
    assert "I002" not in codes(check_missing_query_tips(registry))


# ── I003 — Missing cost_hints ─────────────────────────────────────────────────


def test_i003_no_cost_hints_triggers_info():
    """No cost_hints → I003."""
    registry = make_registry({
        "tools": {"tool_a": {"category": "utility", "description": "does stuff"}}
    })
    violations = check_missing_cost_hints(registry)
    assert "I003" in codes(violations)


def test_i003_no_violation_when_cost_hints_present():
    """cost_hints present → no I003."""
    registry = make_registry({
        "tools": {
            "tool_a": {
                "category": "utility",
                "description": "does stuff",
                "cost_hints": {"latency_ms": 100, "idempotent": True},
            }
        }
    })
    assert "I003" not in codes(check_missing_cost_hints(registry))


# ── W004 — Missing concepts_required ─────────────────────────────────────────


def test_w004_non_trivial_category_without_concepts():
    """project-management tool with no concepts_required → W004."""
    registry = make_registry({
        "tools": {
            "github_create_issue": {
                "category": "project-management",
                "description": "creates an issue",
                "concepts_required": [],
            }
        }
    })
    violations = check_missing_concepts(registry)
    assert "W004" in codes(violations)


def test_w004_no_violation_for_trivial_category():
    """search tool with no concepts_required → no W004."""
    registry = make_registry({
        "tools": {
            "web_search": {
                "category": "search",
                "description": "searches the web",
            }
        }
    })
    assert "W004" not in codes(check_missing_concepts(registry))


# ── run_checks integration ─────────────────────────────────────────────────────


def test_run_checks_returns_list():
    """run_checks always returns a list (even on empty registry)."""
    registry = make_registry({"tools": {}, "concepts": {}, "patterns": {}})
    results = run_checks(registry)
    assert isinstance(results, list)


def test_run_checks_clean_registry_has_no_errors():
    """A well-annotated two-tool registry produces no ERROR violations."""
    desc_a = (
        "Searches the web for current information and returns ranked results with "
        "titles and URLs. Use for external facts. Do NOT use for internal docs."
    )
    desc_b = (
        "Searches internal documentation and returns relevant sections with context. "
        "Use for knowledge base queries. Do NOT use for public web content."
    )
    registry = make_registry({
        "tools": {
            "web_search": {
                "category": "search",
                "description": desc_a,
                "concepts_required": [],
                "alternatives": ["docs_search"],
                "composes_with": [],
                "query_tips": "Use for public web. For internal docs use docs_search.",
                "cost_hints": {"latency_ms": 800, "idempotent": True, "side_effects": []},
            },
            "docs_search": {
                "category": "search",
                "description": desc_b,
                "concepts_required": [],
                "alternatives": ["web_search"],
                "composes_with": [],
                "query_tips": "Use for internal docs. For web use web_search.",
                "cost_hints": {"latency_ms": 200, "idempotent": True, "side_effects": []},
            },
        },
        "patterns": {
            "search_fan_out": {
                "intent_triggers": ["search for information"],
                "tool_sequence": [["web_search", "docs_search"]],
                "merge_strategy": "all",
            }
        },
        "concepts": {},
    })
    errors = [v for v in run_checks(registry) if v.severity == Severity.ERROR]
    assert errors == []


def test_run_checks_on_carlos_os_example(tmp_path):
    """The CARLOS-OS example file parses and runs checks without crashing."""
    import yaml
    from pathlib import Path

    example_path = (
        Path(__file__).parent.parent
        / "examples" / "carlos-os" / ".tool-fabric.yaml"
    )
    assert example_path.exists(), f"Example file not found: {example_path}"

    with open(example_path) as f:
        raw = yaml.safe_load(f)

    registry = Registry(raw, source_file=str(example_path))
    results = run_checks(registry)

    # Should not crash. No errors (E001-E005) expected in the fixed example.
    errors = [v for v in results if v.severity == Severity.ERROR]
    assert errors == [], f"Unexpected errors: {[(v.code, v.message) for v in errors]}"
