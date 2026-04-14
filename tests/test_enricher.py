"""
Tests for runtime.enricher.FabricEnricher.

Uses a minimal synthetic registry so tests are fast and self-contained.
"""

import pytest
from runtime.enricher import FabricEnricher


# ── Fixtures ───────────────────────────────────────────────────────────────────

MINIMAL_REGISTRY: dict = {
    "tools": {
        "tool_a": {
            "category": "communication",
            "description": "Sends a message to service A.",
            "alternatives": ["tool_b"],
            "concepts_required": ["service.auth"],
            "query_tips": "Use for service A. Prefer tool_b for service B.",
        },
        "tool_b": {
            "category": "communication",
            "description": "Sends a message to service B.",
            "alternatives": ["tool_a"],
            "concepts_required": [],
            "query_tips": "Use for service B. Prefer tool_a for service A.",
        },
        "tool_standalone": {
            "category": "utility",
            "description": "A standalone utility with no alternatives or concepts.",
            "alternatives": [],
            "concepts_required": [],
        },
    },
    "concepts": {
        "service.auth": {
            "description": "Authenticated session with the external service.",
            "prerequisites": [],
            "examples": ["API_KEY env var set"],
            "scope": "global",
        }
    },
    "patterns": {
        "notify_both": {
            "name": "Notify via A then B",
            "intent_triggers": ["notify both services", "send to A and B"],
            "tool_sequence": ["tool_a", "tool_b"],
            "merge_strategy": "all",
        }
    },
}


@pytest.fixture
def enricher() -> FabricEnricher:
    return FabricEnricher(MINIMAL_REGISTRY)


# ── Unit tests ─────────────────────────────────────────────────────────────────


class TestToolToPatternIndex:
    def test_tool_a_in_index(self, enricher):
        assert "notify_both" in enricher._tool_to_patterns["tool_a"]

    def test_tool_b_in_index(self, enricher):
        assert "notify_both" in enricher._tool_to_patterns["tool_b"]

    def test_standalone_not_in_index(self, enricher):
        assert "tool_standalone" not in enricher._tool_to_patterns


class TestEnrichTool:
    def test_raw_description_preserved(self, enricher):
        result = enricher.enrich_tool("tool_a", "Sends a message to service A.")
        assert "Sends a message to service A." in result

    def test_query_tips_included(self, enricher):
        result = enricher.enrich_tool("tool_a", "Sends a message to service A.")
        assert "service A" in result
        assert "service B" in result

    def test_alternative_name_included(self, enricher):
        result = enricher.enrich_tool("tool_a", "Sends a message to service A.")
        assert "tool_b" in result

    def test_alternative_query_tips_included(self, enricher):
        """Alternative's own query_tips should appear to aid disambiguation."""
        result = enricher.enrich_tool("tool_a", "Sends a message to service A.")
        # tool_b's query_tips mention "service B"
        assert "service B" in result

    def test_concept_id_included(self, enricher):
        result = enricher.enrich_tool("tool_a", "Sends a message to service A.")
        assert "service.auth" in result

    def test_concept_definition_included(self, enricher):
        result = enricher.enrich_tool("tool_a", "Sends a message to service A.")
        assert "Authenticated session with the external service." in result

    def test_pattern_name_included(self, enricher):
        result = enricher.enrich_tool("tool_a", "Sends a message to service A.")
        assert "Notify via A then B" in result

    def test_pattern_trigger_included(self, enricher):
        result = enricher.enrich_tool("tool_a", "Sends a message to service A.")
        assert "notify both services" in result

    def test_standalone_tool_no_extras(self, enricher):
        """Tool with no alternatives, concepts, or patterns gets raw description only."""
        result = enricher.enrich_tool("tool_standalone", "A standalone utility.")
        assert result.strip() == "A standalone utility."

    def test_unknown_tool_returns_raw(self, enricher):
        """Unknown tool IDs should not raise — just return raw description."""
        result = enricher.enrich_tool("does_not_exist", "Some raw text.")
        assert "Some raw text." in result

    def test_enriched_longer_than_raw(self, enricher):
        raw = "Sends a message to service A."
        enriched = enricher.enrich_tool("tool_a", raw)
        assert len(enriched) > len(raw)

    def test_no_tools_with_empty_alternatives_list(self, enricher):
        """tool_b has no concepts_required — no concept section should appear."""
        result = enricher.enrich_tool("tool_b", "Sends to B.")
        assert "Required domain concepts" not in result


class TestEnrichDescriptions:
    def test_returns_all_keys(self, enricher):
        raw = {"tool_a": "Desc A", "tool_b": "Desc B", "tool_standalone": "Desc C"}
        enriched = enricher.enrich_descriptions(raw)
        assert set(enriched.keys()) == {"tool_a", "tool_b", "tool_standalone"}

    def test_values_are_strings(self, enricher):
        raw = {"tool_a": "Desc A"}
        enriched = enricher.enrich_descriptions(raw)
        assert isinstance(enriched["tool_a"], str)

    def test_enriched_contains_raw(self, enricher):
        raw = {"tool_a": "Desc A"}
        enriched = enricher.enrich_descriptions(raw)
        assert "Desc A" in enriched["tool_a"]

    def test_empty_input_returns_empty(self, enricher):
        assert enricher.enrich_descriptions({}) == {}


class TestEdgeCases:
    def test_empty_registry(self):
        enricher = FabricEnricher({})
        result = enricher.enrich_tool("anything", "Raw text.")
        assert "Raw text." in result

    def test_missing_tools_key(self):
        enricher = FabricEnricher({"concepts": {}, "patterns": {}})
        result = enricher.enrich_tool("tool_a", "Raw.")
        assert "Raw." in result

    def test_parallel_step_in_pattern(self):
        """Parallel steps (lists within tool_sequence) must be indexed correctly."""
        registry = {
            "tools": {"t1": {"description": "T1"}, "t2": {"description": "T2"}},
            "concepts": {},
            "patterns": {
                "parallel_pat": {
                    "name": "Parallel pattern",
                    "intent_triggers": ["do both"],
                    "tool_sequence": [["t1", "t2"]],
                }
            },
        }
        enricher = FabricEnricher(registry)
        assert "parallel_pat" in enricher._tool_to_patterns["t1"]
        assert "parallel_pat" in enricher._tool_to_patterns["t2"]
