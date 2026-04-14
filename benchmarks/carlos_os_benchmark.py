#!/usr/bin/env python3
"""
CARLOS-OS Benchmark: Tool Selection Accuracy (Baseline vs. Fabric-Enriched)

Measures how often a TF-IDF cosine-similarity selector picks the correct
tool(s) given a natural-language query, before and after .tool-fabric.yaml
enrichment.

The selector is intentionally simple (TF-IDF, no LLM) so that results
isolate the effect of description quality, not model capability.  The
"before" condition uses raw MCP descriptions; the "after" condition uses
FabricEnricher-augmented descriptions.

Usage
-----
    # From repo root:
    python benchmarks/carlos_os_benchmark.py
    python benchmarks/carlos_os_benchmark.py examples/carlos-os/.tool-fabric.yaml
    python benchmarks/carlos_os_benchmark.py --output /tmp/results.json

Output
------
    benchmarks/results/carlos_os_results.json  (default)

    JSON schema:
      {
        "registry": str,
        "n_tools": int,
        "n_queries": int,
        "baseline":  { "aggregate": {...}, "per_query": [...] },
        "enriched":  { "aggregate": {...}, "per_query": [...] },
        "delta":     { metric: float, ... },
        "summary":   { "hit@1_lift": str, "mrr_lift": str }
      }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

# Ensure repo root is on sys.path when run as a script from any directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from runtime.enricher import FabricEnricher  # noqa: E402


# ── Test queries ───────────────────────────────────────────────────────────────
#
# 20 queries drawn from realistic CARLOS-OS usage.  Ground-truth tool sets are
# verified against the CARLOS-OS .tool-fabric.yaml; no query is trivially
# solvable by exact keyword match (e.g. we do NOT include "use bash_execute").
#
# Four intentional disambiguation families:
#   A) GitHub vs Linear (q01–q02, q14, q20)
#   B) Slack vs Gmail (q03–q04, q17–q18)
#   C) bash vs python (q05, q09)
#   D) web_search vs web_fetch (q07, q16)
#   E) calendar_find_slot vs calendar_create_event (q11–q12, q19)

TEST_QUERIES: list[dict[str, Any]] = [
    {
        "id": "q01",
        "query": "Create a bug report in GitHub for the authentication issue",
        "ground_truth": ["github_create_issue"],
        "notes": "Simple single-tool; baseline should get this right.",
    },
    {
        "id": "q02",
        "query": "Track this feature request in our Linear sprint backlog",
        "ground_truth": ["linear_create_issue"],
        "notes": "GitHub vs Linear disambiguation — tests query_tips.",
    },
    {
        "id": "q03",
        "query": "Send a notification to the engineering Slack channel about the deployment",
        "ground_truth": ["slack_send_message"],
        "notes": "Slack vs Gmail — 'Slack channel' is the key signal.",
    },
    {
        "id": "q04",
        "query": "Send a formal email to the client about the project status update",
        "ground_truth": ["gmail_send"],
        "notes": "Gmail vs Slack — 'formal email' + 'client' tips it.",
    },
    {
        "id": "q05",
        "query": "Run a shell command to check the disk space on the server",
        "ground_truth": ["bash_execute"],
        "notes": "bash vs python — 'shell command' is the signal.",
    },
    {
        "id": "q06",
        "query": "Open a pull request for the feature branch I just pushed to GitHub",
        "ground_truth": ["github_create_pr"],
        "notes": "Distinct intent — no close alternative in the registry.",
    },
    {
        "id": "q07",
        "query": "Search online to find the latest release notes for scikit-learn",
        "ground_truth": ["web_search"],
        "notes": "web_search vs web_fetch — 'search online' tips it; URL not known.",
    },
    {
        "id": "q08",
        "query": "Read the contents of the pyproject.toml configuration file",
        "ground_truth": ["file_read"],
        "notes": "Distinct file-system read intent.",
    },
    {
        "id": "q09",
        "query": "Execute a Python script to aggregate and transform the CSV data",
        "ground_truth": ["python_execute"],
        "notes": "bash vs python — 'Python script' is the disambiguating signal.",
    },
    {
        "id": "q10",
        "query": "Ask Claude to summarize these meeting notes into a list of action items",
        "ground_truth": ["claude_invoke"],
        "notes": "LLM selection — claude vs gemini vs gpt.",
    },
    {
        "id": "q11",
        "query": "Find a free time slot for a one-hour meeting next Tuesday",
        "ground_truth": ["calendar_find_slot"],
        "notes": "find_slot vs create_event — 'find a slot' signals search.",
    },
    {
        "id": "q12",
        "query": "Create a new Google Calendar event for the team standup at 9am tomorrow",
        "ground_truth": ["calendar_create_event"],
        "notes": "create_event vs find_slot — 'create an event' signals write.",
    },
    {
        "id": "q13",
        "query": "Log this month's API cost as a transaction in the Notion budget tracker",
        "ground_truth": ["notion_update_budget"],
        "notes": "Finance domain — Notion budget update.",
    },
    {
        "id": "q14",
        "query": "Check whether there is already a Linear issue tracking this bug",
        "ground_truth": ["linear_search_issues"],
        "notes": "Search-before-create — 'check' and 'already' signal search intent.",
    },
    {
        "id": "q15",
        "query": "Add the tech-debt label to GitHub issue number 42",
        "ground_truth": ["github_add_label"],
        "notes": "Narrow GitHub sub-operation — labels.",
    },
    {
        "id": "q16",
        "query": "Fetch the full page content of this documentation URL I already have",
        "ground_truth": ["web_fetch"],
        "notes": "web_fetch vs web_search — 'URL I already have' + 'full content'.",
    },
    {
        "id": "q17",
        "query": "Draft an email to the investor but do not send it yet — save as draft",
        "ground_truth": ["gmail_create_draft"],
        "notes": "gmail_create_draft vs gmail_send — 'do not send' is the key signal.",
    },
    {
        "id": "q18",
        "query": "Post a threaded reply to that Slack message with today's test results",
        "ground_truth": ["slack_send_message_thread"],
        "notes": "slack thread vs channel — 'threaded reply' is the signal.",
    },
    {
        "id": "q19",
        "query": "Find an available time slot and then book a calendar meeting event",
        "ground_truth": ["calendar_find_slot", "calendar_create_event"],
        "notes": "Multi-tool: sequential find-then-create pattern.",
    },
    {
        "id": "q20",
        "query": "Search existing GitHub issues for authentication problems before filing a new one",
        "ground_truth": ["github_search_issues"],
        "notes": "github_search vs github_create — 'search existing' is the signal.",
    },
]


# ── TF-IDF selector ────────────────────────────────────────────────────────────


def build_selector(descriptions: dict[str, str]):
    """
    Build a TF-IDF cosine-similarity selector over the given tool descriptions.

    Parameters
    ----------
    descriptions : dict[str, str]
        Mapping of tool_id → description text (raw or enriched).

    Returns
    -------
    callable
        A function ``selector(query: str) -> list[tuple[str, float]]``
        that returns all tools ranked by cosine similarity (highest first).
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    tool_ids = list(descriptions.keys())
    corpus = [descriptions[tid] for tid in tool_ids]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        stop_words="english",
        min_df=1,
    )
    tfidf_matrix = vectorizer.fit_transform(corpus)

    def selector(query: str) -> list[tuple[str, float]]:
        query_vec = vectorizer.transform([query])
        scores = cosine_similarity(query_vec, tfidf_matrix).flatten()
        return sorted(
            zip(tool_ids, scores.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )

    return selector


# ── Metrics ────────────────────────────────────────────────────────────────────


def compute_metrics(
    ranked: list[tuple[str, float]],
    ground_truth: list[str],
) -> dict[str, Any]:
    """
    Compute per-query metrics given a ranked tool list and ground truth.

    Metrics
    -------
    hit@1
        1 if the top-ranked tool is in ground truth, else 0.
    hit@k
        1 if at least one of the top-k tools is in ground truth (k = |gt|).
    precision@k
        Fraction of top-k results that are in ground truth.
    recall@k
        Fraction of ground-truth tools found in top-k.
    mrr
        Reciprocal rank of the first correct result (0 if none found).
    """
    k = max(len(ground_truth), 1)
    gt_set = set(ground_truth)
    top_k_ids = [tid for tid, _ in ranked[:k]]

    hit_at_1 = int(bool(ranked) and ranked[0][0] in gt_set)
    hit_at_k = int(any(tid in gt_set for tid in top_k_ids))
    precision_at_k = sum(1 for tid in top_k_ids if tid in gt_set) / k
    recall_at_k = sum(1 for tid in top_k_ids if tid in gt_set) / len(gt_set)

    mrr = 0.0
    for rank, (tid, _) in enumerate(ranked, start=1):
        if tid in gt_set:
            mrr = 1.0 / rank
            break

    return {
        "hit@1": hit_at_1,
        "hit@k": hit_at_k,
        "precision@k": round(precision_at_k, 4),
        "recall@k": round(recall_at_k, 4),
        "mrr": round(mrr, 4),
        "k": k,
        "top_prediction": ranked[0][0] if ranked else None,
        "top_score": round(ranked[0][1], 4) if ranked else 0.0,
    }


def aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate metrics across all per-query results."""
    n = len(results)
    if n == 0:
        return {}
    return {
        "n_queries": n,
        "hit@1": round(sum(r["hit@1"] for r in results) / n, 4),
        "hit@k": round(sum(r["hit@k"] for r in results) / n, 4),
        "mrr": round(sum(r["mrr"] for r in results) / n, 4),
        "avg_precision@k": round(sum(r["precision@k"] for r in results) / n, 4),
        "avg_recall@k": round(sum(r["recall@k"] for r in results) / n, 4),
    }


# ── Description builders ───────────────────────────────────────────────────────


def get_raw_descriptions(registry: dict[str, Any]) -> dict[str, str]:
    """Extract {tool_id: raw_description} from a parsed registry."""
    return {
        tid: (tdata.get("description") or "").strip()
        for tid, tdata in (registry.get("tools") or {}).items()
    }


def get_enriched_descriptions(registry: dict[str, Any]) -> dict[str, str]:
    """Build enriched descriptions using FabricEnricher."""
    enricher = FabricEnricher(registry)
    raw = get_raw_descriptions(registry)
    return enricher.enrich_descriptions(raw)


# ── Benchmark runner ───────────────────────────────────────────────────────────


def run_benchmark(
    registry: dict[str, Any],
    queries: list[dict[str, Any]],
    use_enriched: bool,
) -> list[dict[str, Any]]:
    """
    Run all queries through the TF-IDF selector and compute per-query metrics.

    Parameters
    ----------
    registry : dict
        Parsed .tool-fabric.yaml content.
    queries : list
        Test queries with 'id', 'query', 'ground_truth', optional 'notes'.
    use_enriched : bool
        Use FabricEnricher descriptions if True, raw descriptions if False.

    Returns
    -------
    list of per-query result dicts.
    """
    descriptions = (
        get_enriched_descriptions(registry)
        if use_enriched
        else get_raw_descriptions(registry)
    )
    mode = "enriched" if use_enriched else "baseline"
    selector = build_selector(descriptions)

    results = []
    for q in queries:
        ranked = selector(q["query"])
        metrics = compute_metrics(ranked, q["ground_truth"])
        results.append(
            {
                "id": q["id"],
                "query": q["query"],
                "ground_truth": q["ground_truth"],
                "mode": mode,
                "notes": q.get("notes", ""),
                **metrics,
            }
        )
    return results


# ── CLI ────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CARLOS-OS tool-fabric benchmark: baseline vs. enriched TF-IDF accuracy."
    )
    parser.add_argument(
        "registry",
        nargs="?",
        default="examples/carlos-os/.tool-fabric.yaml",
        help="Path to .tool-fabric.yaml (default: examples/carlos-os/.tool-fabric.yaml)",
    )
    parser.add_argument(
        "--output",
        default="benchmarks/results/carlos_os_results.json",
        help="Output path for JSON results.",
    )
    args = parser.parse_args(argv)

    registry_path = Path(args.registry)
    if not registry_path.exists():
        print(f"Registry not found: {registry_path}", file=sys.stderr)
        return 1

    with open(registry_path) as f:
        registry = yaml.safe_load(f)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    baseline_results = run_benchmark(registry, TEST_QUERIES, use_enriched=False)
    enriched_results = run_benchmark(registry, TEST_QUERIES, use_enriched=True)

    baseline_agg = aggregate_metrics(baseline_results)
    enriched_agg = aggregate_metrics(enriched_results)

    numeric_keys = [k for k in baseline_agg if k != "n_queries"]
    delta = {
        k: round(enriched_agg[k] - baseline_agg[k], 4)
        for k in numeric_keys
        if k in enriched_agg
    }

    output = {
        "registry": str(registry_path),
        "n_tools": len(registry.get("tools") or {}),
        "n_queries": len(TEST_QUERIES),
        "baseline": {"aggregate": baseline_agg, "per_query": baseline_results},
        "enriched": {"aggregate": enriched_agg, "per_query": enriched_results},
        "delta": delta,
        "summary": {
            "hit@1_lift": f"{delta.get('hit@1', 0):+.1%}",
            "mrr_lift": f"{delta.get('mrr', 0):+.4f}",
        },
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # ── Print summary table ─────────────────────────────────────────────────
    n_tools = output["n_tools"]
    n_q = len(TEST_QUERIES)
    print(f"\ntool-fabric CARLOS-OS Benchmark")
    print(f"Registry : {registry_path}  ({n_tools} tools, {n_q} queries)")
    print()
    print(f"{'Metric':<20} {'Baseline':>10} {'Enriched':>10} {'Delta':>10}")
    print("-" * 55)
    for metric in ["hit@1", "hit@k", "mrr", "avg_precision@k", "avg_recall@k"]:
        b = baseline_agg.get(metric, 0.0)
        e = enriched_agg.get(metric, 0.0)
        d = delta.get(metric, 0.0)
        sign = "+" if d >= 0 else ""
        print(f"{metric:<20} {b:>10.4f} {e:>10.4f} {sign}{d:>9.4f}")
    print()
    print(f"hit@1 lift : {output['summary']['hit@1_lift']}")
    print(f"MRR lift   : {output['summary']['mrr_lift']}")
    print(f"\nResults written to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
