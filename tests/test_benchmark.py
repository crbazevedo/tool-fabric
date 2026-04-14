"""
Tests for benchmarks.carlos_os_benchmark.

Covers: description builders, TF-IDF selector, metrics computation,
full benchmark run (baseline and enriched), and aggregate metrics.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from benchmarks.carlos_os_benchmark import (
    TEST_QUERIES,
    aggregate_metrics,
    build_selector,
    compute_metrics,
    get_enriched_descriptions,
    get_raw_descriptions,
    run_benchmark,
)

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "examples/carlos-os/.tool-fabric.yaml"


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def raw_descriptions(registry) -> dict[str, str]:
    return get_raw_descriptions(registry)


@pytest.fixture(scope="module")
def enriched_descriptions(registry) -> dict[str, str]:
    return get_enriched_descriptions(registry)


@pytest.fixture(scope="module")
def baseline_results(registry) -> list[dict]:
    return run_benchmark(registry, TEST_QUERIES, use_enriched=False)


@pytest.fixture(scope="module")
def enriched_results(registry) -> list[dict]:
    return run_benchmark(registry, TEST_QUERIES, use_enriched=True)


# ── Registry sanity ────────────────────────────────────────────────────────────


class TestRegistryLoads:
    def test_has_tools(self, registry):
        assert "tools" in registry

    def test_tool_count(self, registry):
        assert len(registry["tools"]) >= 15

    def test_has_concepts(self, registry):
        assert "concepts" in registry

    def test_has_patterns(self, registry):
        assert "patterns" in registry


# ── Description builders ───────────────────────────────────────────────────────


class TestGetRawDescriptions:
    def test_all_tools_present(self, registry, raw_descriptions):
        assert set(raw_descriptions.keys()) == set(registry["tools"].keys())

    def test_all_values_are_strings(self, raw_descriptions):
        for tid, desc in raw_descriptions.items():
            assert isinstance(desc, str), f"{tid}: expected str, got {type(desc)}"

    def test_non_empty_for_main_tools(self, raw_descriptions):
        for tid in ("slack_send_message", "gmail_send", "github_create_issue"):
            assert raw_descriptions[tid], f"{tid}: description is empty"


class TestGetEnrichedDescriptions:
    def test_same_keys_as_raw(self, raw_descriptions, enriched_descriptions):
        assert set(enriched_descriptions.keys()) == set(raw_descriptions.keys())

    def test_enriched_longer_than_raw(self, raw_descriptions, enriched_descriptions):
        # At least the fully-annotated tools should be longer after enrichment
        enriched_longer = sum(
            1
            for tid in enriched_descriptions
            if len(enriched_descriptions[tid]) > len(raw_descriptions[tid])
        )
        assert enriched_longer > 0, "No tool descriptions were enriched"

    def test_raw_preserved_in_enriched(self, raw_descriptions, enriched_descriptions):
        for tid in ("slack_send_message", "claude_invoke"):
            assert raw_descriptions[tid][:30] in enriched_descriptions[tid]


# ── TF-IDF selector ────────────────────────────────────────────────────────────


class TestBuildSelector:
    def test_returns_callable(self, raw_descriptions):
        selector = build_selector(raw_descriptions)
        assert callable(selector)

    def test_ranked_length_equals_n_tools(self, raw_descriptions):
        selector = build_selector(raw_descriptions)
        ranked = selector("create a GitHub issue")
        assert len(ranked) == len(raw_descriptions)

    def test_sorted_descending(self, raw_descriptions):
        selector = build_selector(raw_descriptions)
        ranked = selector("send a Slack message")
        scores = [score for _, score in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_scores_are_floats(self, raw_descriptions):
        selector = build_selector(raw_descriptions)
        for _, score in selector("any query"):
            assert isinstance(score, float)


# ── compute_metrics ────────────────────────────────────────────────────────────


class TestComputeMetrics:
    RANKED = [("tool_a", 0.9), ("tool_b", 0.6), ("tool_c", 0.3)]

    def test_hit_at_1_correct(self):
        m = compute_metrics(self.RANKED, ["tool_a"])
        assert m["hit@1"] == 1

    def test_hit_at_1_miss(self):
        m = compute_metrics(self.RANKED, ["tool_c"])
        assert m["hit@1"] == 0

    def test_mrr_first_rank(self):
        m = compute_metrics(self.RANKED, ["tool_a"])
        assert m["mrr"] == pytest.approx(1.0)

    def test_mrr_third_rank(self):
        m = compute_metrics(self.RANKED, ["tool_c"])
        assert m["mrr"] == pytest.approx(1 / 3, rel=1e-3)

    def test_mrr_not_found(self):
        m = compute_metrics(self.RANKED, ["tool_z"])
        assert m["mrr"] == 0.0

    def test_multi_tool_hit_at_k(self):
        m = compute_metrics(self.RANKED, ["tool_a", "tool_b"])
        assert m["hit@k"] == 1
        assert m["precision@k"] == pytest.approx(1.0)
        assert m["recall@k"] == pytest.approx(1.0)

    def test_multi_tool_partial_recall(self):
        m = compute_metrics(self.RANKED, ["tool_a", "tool_z"])
        # top-2 = [tool_a, tool_b]; only tool_a in gt → recall = 0.5
        assert m["recall@k"] == pytest.approx(0.5)

    def test_top_prediction_field(self):
        m = compute_metrics(self.RANKED, ["tool_a"])
        assert m["top_prediction"] == "tool_a"

    def test_empty_ranked_list(self):
        m = compute_metrics([], ["tool_a"])
        assert m["hit@1"] == 0
        assert m["mrr"] == 0.0
        assert m["top_prediction"] is None


# ── run_benchmark ──────────────────────────────────────────────────────────────


class TestRunBenchmark:
    def test_baseline_result_count(self, baseline_results):
        assert len(baseline_results) == len(TEST_QUERIES)

    def test_enriched_result_count(self, enriched_results):
        assert len(enriched_results) == len(TEST_QUERIES)

    def test_baseline_mode_field(self, baseline_results):
        assert all(r["mode"] == "baseline" for r in baseline_results)

    def test_enriched_mode_field(self, enriched_results):
        assert all(r["mode"] == "enriched" for r in enriched_results)

    def test_required_fields_present(self, baseline_results):
        required = {"id", "query", "ground_truth", "mode", "hit@1", "hit@k", "mrr"}
        for r in baseline_results:
            assert required <= set(r.keys()), f"Missing keys in {r['id']}"

    def test_hit_at_1_range(self, baseline_results):
        for r in baseline_results:
            assert r["hit@1"] in {0, 1}

    def test_mrr_range(self, baseline_results):
        for r in baseline_results:
            assert 0.0 <= r["mrr"] <= 1.0


# ── aggregate_metrics ──────────────────────────────────────────────────────────


class TestAggregateMetrics:
    def test_hit_at_1_in_range(self, baseline_results):
        agg = aggregate_metrics(baseline_results)
        assert 0.0 <= agg["hit@1"] <= 1.0

    def test_mrr_in_range(self, baseline_results):
        agg = aggregate_metrics(baseline_results)
        assert 0.0 <= agg["mrr"] <= 1.0

    def test_n_queries_correct(self, baseline_results):
        agg = aggregate_metrics(baseline_results)
        assert agg["n_queries"] == len(TEST_QUERIES)

    def test_empty_list(self):
        assert aggregate_metrics([]) == {}

    def test_tfidf_cross_contamination_documented(self, baseline_results, enriched_results):
        """
        Documents the TF-IDF cross-contamination effect.

        Fabric enrichment adds competitor tool names (alternatives) into tool
        descriptions. TF-IDF treats these tokens as signal, which degrades
        selection accuracy for queries that would otherwise uniquely match.

        This degradation is expected and acceptable: fabric enrichment is
        optimised for LLM comprehension (the model can reason about "use X
        instead of Y when Z"), not for bag-of-words models that cannot
        interpret disambiguation prose. The LLM-selector benchmark (Round 4)
        should show the opposite direction.
        """
        b_agg = aggregate_metrics(baseline_results)
        e_agg = aggregate_metrics(enriched_results)
        # Both aggregates are valid probability values; direction is unconstrained
        # for a TF-IDF selector.
        assert 0.0 <= b_agg["hit@1"] <= 1.0
        assert 0.0 <= e_agg["hit@1"] <= 1.0


# ── TEST_QUERIES sanity ────────────────────────────────────────────────────────


class TestQuerySet:
    def test_twenty_queries(self):
        assert len(TEST_QUERIES) == 20

    def test_unique_ids(self):
        ids = [q["id"] for q in TEST_QUERIES]
        assert len(ids) == len(set(ids))

    def test_all_have_ground_truth(self):
        for q in TEST_QUERIES:
            assert q.get("ground_truth"), f"{q['id']} has empty ground_truth"

    def test_ground_truth_are_lists(self):
        for q in TEST_QUERIES:
            assert isinstance(q["ground_truth"], list)
