#!/usr/bin/env python3
"""
Scale Benchmark: OLD vs NEW tool descriptions × 41 vs 150 tools.

Hypothesis: governance-improved descriptions maintain Haiku accuracy at scale
(150+ tools) while OLD descriptions degrade significantly.

Four conditions:
  1. OLD  descriptions, 41  tools (small  + degraded  = baseline)
  2. OLD  descriptions, 150 tools (large  + degraded  = worst case)
  3. NEW  descriptions, 41  tools (small  + improved)
  4. NEW  descriptions, 150 tools (large  + improved  = governance value)

Usage
-----
    export ANTHROPIC_API_KEY=<key>
    python benchmarks/scale_benchmark.py
    python benchmarks/scale_benchmark.py --output benchmarks/results/scale_results.json

Output
------
    benchmarks/results/scale_results.json

    JSON schema:
      {
        "conditions": [
          {
            "id": str,             # e.g. "old_41"
            "desc_version": str,   # "old" | "new"
            "n_tools": int,
            "model": str,
            "aggregate": { hit@1, hit@3, mrr, precision@3, recall@3 },
            "per_query": [...]
          }, ...
        ],
        "deltas": { ... },
        "summary_table": str
      }
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── Tool selection guide (added to NEW descriptions system prompt) ─────────────

_TOOL_SELECTION_GUIDE = """
=== CARLOS-OS TOOL SELECTION GUIDE ===

KNOWLEDGE QUERIES (what does the system know?)
  search_facts       — BM25 full-text over stored facts. Best for domain-specific knowledge.
  kb_hybrid_search   — BM25 + vector + graph over entities (people, orgs, dates, amounts).
                       PRIMARY entity discovery tool. Use for "who have I been in touch with?"
  kb_search_entities — Substring match. Best for exact name lookup.
  retrieve_fact      — Exact lookup by domain + key.
  search_episodes    — Narrative summaries of past work sessions.
  search_notes_tool  — Substring search over meeting and captured notes.

SITUATION QUERIES (what's happening now?)
  list_situations          — Active cognitive situations with urgency scores.
  get_situation            — Full detail on a specific situation.
  get_situation_trajectory — Confidence/urgency time series.
  search_situations        — Free-text search across situation descriptions.

ACTION QUERIES (what needs doing?)
  list_actionables — Tasks, commitments, deadlines sorted by risk score.
  get_action_queue — Pending HITL items needing immediate human input.

MULTI-SOURCE FAN-OUT PATTERNS:
  "Who is X?" / "Who have I been in touch with about X?"
      → kb_search_entities + kb_hybrid_search
  "What's happening with X?"
      → list_situations + search_facts + kb_hybrid_search
  "What do I need to do about X?"
      → list_actionables + list_situations
  "What do I know about X?"
      → search_facts + kb_hybrid_search + search_notes_tool
""".strip()


# ── 41-tool subset ─────────────────────────────────────────────────────────────

SMALL_TOOL_SET = {
    "search_facts", "retrieve_fact", "store_fact", "list_facts",
    "kb_hybrid_search", "kb_search_entities", "kb_get_entity",
    "kb_get_entity_neighbors", "kb_list_entities_by_type", "kb_get_top_ranked",
    "kb_analytics_summary", "kb_cross_correlations",
    "list_situations", "get_situation", "get_situation_trajectory",
    "search_situations", "create_situation",
    "list_actionables", "claim_actionable", "update_actionable",
    "event_history", "query_events",
    "search_notes_tool", "create_note", "ingest_meeting_transcript_tool",
    "search_decisions", "search_patterns", "search_error_logs",
    "search_episodes", "get_agent_memories", "set_agent_goals",
    "memory_stats", "knowledge_stats",
    "governance_check", "compliance_check", "classify_action", "get_action_queue",
    "get_system_pulse", "post_to_slack", "get_slot_availability", "list_domains",
}

assert len(SMALL_TOOL_SET) == 41, f"Expected 41, got {len(SMALL_TOOL_SET)}"


# ── Test queries (50 total) ─────────────────────────────────────────────────────
#
# Coverage: knowledge, KB/entity, situations, actionables, events, notes, memory,
# governance, system, and multi-tool fan-out queries.
#
# Ground truth: primary tool(s) a correct agent should call first.
# Disambiguation families:
#   A) search_facts vs kb_hybrid_search vs search_notes_tool ("what do I know about X?")
#   B) list_situations vs list_actionables ("what is happening" vs "what to do")
#   C) kb_hybrid_search vs kb_search_entities (fuzzy vs exact entity lookup)
#   D) event_history vs query_events (category+filters vs stream)
#   E) governance_check vs compliance_check vs classify_action

QUERIES: list[dict[str, Any]] = [
    # ── Knowledge / Facts ─────────────────────────────────────────────────
    {
        "id": "q01",
        "query": "What do I know about the Korza investment thesis?",
        "ground_truth": ["search_facts"],
        "notes": "Stored domain-specific knowledge → search_facts not kb_hybrid_search.",
    },
    {
        "id": "q02",
        "query": "Retrieve the fact I stored about the NDA signing date",
        "ground_truth": ["retrieve_fact"],
        "notes": "Exact key lookup → retrieve_fact, not search_facts.",
    },
    {
        "id": "q03",
        "query": "Save the fact that my INSS filing deadline is June 30",
        "ground_truth": ["store_fact"],
        "notes": "Write intent → store_fact.",
    },
    {
        "id": "q04",
        "query": "List all facts I have stored about the Korza deal",
        "ground_truth": ["list_facts"],
        "notes": "Enumerate rather than search → list_facts.",
    },
    {
        "id": "q05",
        "query": "What do I know about our runway and burn rate?",
        "ground_truth": ["search_facts"],
        "notes": "Stored financial knowledge → search_facts.",
    },
    {
        "id": "q06",
        "query": "What facts are stored about the regulatory approval process?",
        "ground_truth": ["search_facts"],
        "notes": "Stored process knowledge → search_facts.",
    },
    {
        "id": "q07",
        "query": "Store this new fact: Carlos closed the Korza series A on April 10",
        "ground_truth": ["store_fact"],
        "notes": "Write fact → store_fact.",
    },
    {
        "id": "q08",
        "query": "What information have I captured about the board members?",
        "ground_truth": ["search_facts"],
        "notes": "Stored captured knowledge; KB might also work but facts first.",
    },

    # ── KB / Entity (the key disambiguation set) ──────────────────────────
    {
        "id": "q09",
        "query": "Who have I been in touch with about Korza?",
        "ground_truth": ["kb_hybrid_search"],
        "notes": "THE failing query pre-governance. Entity discovery, not fact search.",
    },
    {
        "id": "q10",
        "query": "Find all contacts who are investors in the Brazil ecosystem",
        "ground_truth": ["kb_hybrid_search"],
        "notes": "Entity discovery by type — kb_hybrid_search over kb_search_entities.",
    },
    {
        "id": "q11",
        "query": "Show me what I know about Felipe Oliveira and his role at Korza",
        "ground_truth": ["kb_get_entity"],
        "notes": "Named entity detail → kb_get_entity.",
    },
    {
        "id": "q12",
        "query": "What entities are connected to the Korza project in my knowledge graph?",
        "ground_truth": ["kb_get_entity_neighbors"],
        "notes": "Graph traversal → kb_get_entity_neighbors.",
    },
    {
        "id": "q13",
        "query": "Who are the key people I should talk to about the series B round?",
        "ground_truth": ["kb_hybrid_search"],
        "notes": "Semantic entity discovery → kb_hybrid_search.",
    },
    {
        "id": "q14",
        "query": "Find all organizations I have tagged as potential Korza partners",
        "ground_truth": ["kb_search_entities"],
        "notes": "Exact-name/substring entity search → kb_search_entities.",
    },
    {
        "id": "q15",
        "query": "What is the relationship between Korza and the BNDES fund?",
        "ground_truth": ["kb_hybrid_search"],
        "notes": "Relationship query → kb_hybrid_search for semantic match.",
    },
    {
        "id": "q16",
        "query": "Show me all entities of type investor in my knowledge graph",
        "ground_truth": ["kb_list_entities_by_type"],
        "notes": "Type-filtered enumeration → kb_list_entities_by_type.",
    },
    {
        "id": "q17",
        "query": "What does my knowledge graph say about the top-ranked entities related to machine learning?",
        "ground_truth": ["kb_get_top_ranked"],
        "notes": "Ranking query → kb_get_top_ranked.",
    },

    # ── Situations (disambiguation: situations vs actionables) ────────────
    {
        "id": "q18",
        "query": "What is currently going on with the Korza onboarding?",
        "ground_truth": ["list_situations"],
        "notes": "Active monitoring query → list_situations, not list_actionables.",
    },
    {
        "id": "q19",
        "query": "What open situations need my attention right now?",
        "ground_truth": ["list_situations"],
        "notes": "Awareness/monitoring → list_situations.",
    },
    {
        "id": "q20",
        "query": "Walk me through the confidence trend of the compliance situation",
        "ground_truth": ["get_situation_trajectory"],
        "notes": "Time-series trajectory → get_situation_trajectory.",
    },
    {
        "id": "q21",
        "query": "Find situations related to the investor conversations",
        "ground_truth": ["search_situations"],
        "notes": "Keyword-based situation search → search_situations.",
    },
    {
        "id": "q22",
        "query": "What is the current status of the Brazil hub setup?",
        "ground_truth": ["list_situations"],
        "notes": "Status/monitoring → list_situations.",
    },

    # ── Actionables (disambiguation: actionables vs situations) ───────────
    {
        "id": "q23",
        "query": "What do I need to do this week?",
        "ground_truth": ["list_actionables"],
        "notes": "Task/to-do query → list_actionables, not list_situations.",
    },
    {
        "id": "q24",
        "query": "Show me all my pending tasks in the Korza domain",
        "ground_truth": ["list_actionables"],
        "notes": "Task enumeration → list_actionables.",
    },
    {
        "id": "q25",
        "query": "What actionable is currently assigned to the finance agent?",
        "ground_truth": ["list_actionables"],
        "notes": "Filter by assignee → list_actionables.",
    },
    {
        "id": "q26",
        "query": "I am taking ownership of the contract review task",
        "ground_truth": ["claim_actionable"],
        "notes": "Ownership transfer → claim_actionable.",
    },
    {
        "id": "q27",
        "query": "Mark the INSS filing task as complete",
        "ground_truth": ["update_actionable"],
        "notes": "Status update → update_actionable.",
    },
    {
        "id": "q28",
        "query": "What actions are currently queued for human approval?",
        "ground_truth": ["get_action_queue"],
        "notes": "HITL queue → get_action_queue, not list_actionables.",
    },

    # ── Events ────────────────────────────────────────────────────────────
    {
        "id": "q29",
        "query": "What happened in the system over the last 24 hours?",
        "ground_truth": ["event_history"],
        "notes": "Category + time filter → event_history, not query_events.",
    },
    {
        "id": "q30",
        "query": "Query all events in the Korza contract event stream",
        "ground_truth": ["query_events"],
        "notes": "Named stream → query_events, not event_history.",
    },
    {
        "id": "q31",
        "query": "How many events have been processed per stream this week?",
        "ground_truth": ["get_event_metrics"],
        "notes": "Metrics/counts → get_event_metrics.",
    },

    # ── Notes / Transcripts ───────────────────────────────────────────────
    {
        "id": "q32",
        "query": "What was discussed in yesterday's Korza kickoff meeting?",
        "ground_truth": ["search_notes_tool"],
        "notes": "Meeting content search → search_notes_tool, not search_facts.",
    },
    {
        "id": "q33",
        "query": "Ingest the transcript from this morning's investor call",
        "ground_truth": ["ingest_meeting_transcript_tool"],
        "notes": "Ingestion of meeting content → ingest_meeting_transcript_tool.",
    },
    {
        "id": "q34",
        "query": "Show me the notes from the Brazil hub planning session",
        "ground_truth": ["search_notes_tool"],
        "notes": "Meeting note retrieval → search_notes_tool.",
    },
    {
        "id": "q35",
        "query": "Create a note summarizing the pricing decision we just made",
        "ground_truth": ["create_note"],
        "notes": "Write new note → create_note.",
    },

    # ── Memory / Episodes / Decisions ─────────────────────────────────────
    {
        "id": "q36",
        "query": "What decisions have I made about the Korza equity structure?",
        "ground_truth": ["search_decisions"],
        "notes": "Decision history → search_decisions, not search_facts.",
    },
    {
        "id": "q37",
        "query": "What patterns have the agents identified in my finance domain?",
        "ground_truth": ["search_patterns"],
        "notes": "Pattern store → search_patterns.",
    },
    {
        "id": "q38",
        "query": "Look up recent error logs from the orchestrator agent",
        "ground_truth": ["search_error_logs"],
        "notes": "Error log search → search_error_logs.",
    },
    {
        "id": "q39",
        "query": "What work did I do last week on the IP strategy?",
        "ground_truth": ["search_episodes"],
        "notes": "Session narrative → search_episodes, not search_facts or search_notes_tool.",
    },
    {
        "id": "q40",
        "query": "What do the agents remember about my goals for Q2?",
        "ground_truth": ["get_agent_memories"],
        "notes": "Agent memory retrieval → get_agent_memories.",
    },
    {
        "id": "q41",
        "query": "Set my goals for the Korza onboarding workstream",
        "ground_truth": ["set_agent_goals"],
        "notes": "Write agent goals → set_agent_goals.",
    },

    # ── Governance ────────────────────────────────────────────────────────
    {
        "id": "q42",
        "query": "Can I share the IP roadmap with the Korza team without restriction?",
        "ground_truth": ["governance_check"],
        "notes": "Policy check on action → governance_check.",
    },
    {
        "id": "q43",
        "query": "Does sending this contract to an external party require approval?",
        "ground_truth": ["compliance_check"],
        "notes": "Compliance check → compliance_check vs governance_check.",
    },
    {
        "id": "q44",
        "query": "Classify the risk level of moving IP materials to the Korza folder",
        "ground_truth": ["classify_action"],
        "notes": "Risk classification → classify_action.",
    },

    # ── System ────────────────────────────────────────────────────────────
    {
        "id": "q45",
        "query": "What is the overall health of the CARLOS-OS system right now?",
        "ground_truth": ["get_system_pulse"],
        "notes": "System health → get_system_pulse.",
    },
    {
        "id": "q46",
        "query": "Post the sprint summary to the Slack operations channel",
        "ground_truth": ["post_to_slack"],
        "notes": "Slack post → post_to_slack.",
    },
    {
        "id": "q47",
        "query": "Find a free one-hour slot for a meeting this Thursday",
        "ground_truth": ["get_slot_availability"],
        "notes": "Calendar availability → get_slot_availability.",
    },
    {
        "id": "q48",
        "query": "What domains are configured in my CARLOS-OS system?",
        "ground_truth": ["list_domains"],
        "notes": "Domain listing → list_domains.",
    },
    {
        "id": "q49",
        "query": "How many knowledge entities and facts are currently indexed?",
        "ground_truth": ["knowledge_stats"],
        "notes": "Storage stats → knowledge_stats.",
    },
    {
        "id": "q50",
        "query": "Give me an analytics summary of my knowledge graph entity distribution",
        "ground_truth": ["kb_analytics_summary"],
        "notes": "Graph analytics → kb_analytics_summary.",
    },
]

assert len(QUERIES) == 50, f"Expected 50 queries, got {len(QUERIES)}"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _truncate(text: str, max_chars: int = 300) -> str:
    """Keep first paragraph or up to max_chars characters."""
    first_para = text.split("\n\n")[0].strip()
    if len(first_para) <= max_chars:
        return first_para
    return first_para[:max_chars].rstrip() + "…"


def build_tool_pool(
    descriptions: dict[str, Any],
    confusers: dict[str, Any],
    subset: set[str] | None,
) -> dict[str, str]:
    """
    Build the tool pool for a benchmark condition.

    Parameters
    ----------
    descriptions : dict
        Real tool descriptions (old or new).
    confusers : dict
        Synthetic confuser tools.
    subset : set[str] or None
        If given, restrict real tools to this subset (small condition).
        Confusers are always added for the large condition.
    """
    pool: dict[str, str] = {}
    for name, data in descriptions.items():
        if subset is None or name in subset:
            pool[name] = _truncate(data["description"])
    if subset is None:
        # Large condition: add confusers
        for name, data in confusers.items():
            if name.startswith("_"):
                continue
            pool[name] = _truncate(data["description"])
    return pool


def make_selector_prompt(
    tools: dict[str, str],
    use_guide: bool,
) -> str:
    """Build the system prompt for the Haiku tool selector."""
    lines = []
    if use_guide:
        lines.append(_TOOL_SELECTION_GUIDE)
        lines.append("")

    lines.append("You are a tool selection agent for CARLOS-OS.")
    lines.append(
        "Given a user query, identify the single best tool to call first. "
        "If multiple tools are genuinely required (fan-out), list them comma-separated."
    )
    lines.append(
        "Respond with ONLY the tool name(s). No explanation. No other text."
    )
    lines.append("")
    lines.append("Available tools:")
    for name in sorted(tools):
        lines.append(f"  {name}: {tools[name]}")
    return "\n".join(lines)


def llm_select(
    client: Any,
    model: str,
    system_prompt: str,
    query: str,
    retries: int = 3,
) -> str:
    """Call the LLM and return the selected tool name(s)."""
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=60,
                system=system_prompt,
                messages=[{"role": "user", "content": query}],
            )
            return resp.content[0].text.strip().lower()
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"API failed after {retries} tries: {exc}") from exc
    return ""


def parse_tool_names(raw: str) -> list[str]:
    """Parse comma-separated tool names from Haiku response."""
    parts = [p.strip().strip("'\"") for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def compute_metrics(
    predicted: list[str],
    ground_truth: list[str],
) -> dict[str, Any]:
    gt_set = set(ground_truth)
    k = 3

    hit_at_1 = int(bool(predicted) and predicted[0] in gt_set)

    # hit@3: any of top-3 in ground truth
    top3 = predicted[:k]
    hit_at_3 = int(any(p in gt_set for p in top3))

    # MRR over single-tool predictions (treat response as ranked list length 1)
    mrr = 0.0
    for rank, p in enumerate(predicted, start=1):
        if p in gt_set:
            mrr = 1.0 / rank
            break

    # precision/recall @3 (treat predicted as unordered top-3)
    tp = sum(1 for p in top3 if p in gt_set)
    precision_3 = tp / k
    recall_3 = tp / len(gt_set) if gt_set else 0.0

    return {
        "hit@1": hit_at_1,
        "hit@3": hit_at_3,
        "mrr": round(mrr, 4),
        "precision@3": round(precision_3, 4),
        "recall@3": round(recall_3, 4),
        "predicted": predicted,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results)
    if not n:
        return {}
    return {
        "n_queries": n,
        "hit@1": round(sum(r["hit@1"] for r in results) / n, 4),
        "hit@3": round(sum(r["hit@3"] for r in results) / n, 4),
        "mrr": round(sum(r["mrr"] for r in results) / n, 4),
        "precision@3": round(sum(r["precision@3"] for r in results) / n, 4),
        "recall@3": round(sum(r["recall@3"] for r in results) / n, 4),
    }


# ── Benchmark runner ───────────────────────────────────────────────────────────


def run_condition(
    client: Any,
    model: str,
    condition_id: str,
    desc_version: str,
    descriptions: dict[str, Any],
    confusers: dict[str, Any],
    use_subset: bool,
    use_guide: bool,
    queries: list[dict[str, Any]],
) -> dict[str, Any]:
    subset = SMALL_TOOL_SET if use_subset else None
    tools = build_tool_pool(descriptions, confusers, subset)
    system_prompt = make_selector_prompt(tools, use_guide=use_guide)

    per_query = []
    for i, q in enumerate(queries):
        raw = llm_select(client, model, system_prompt, q["query"])
        predicted = parse_tool_names(raw)
        metrics = compute_metrics(predicted, q["ground_truth"])
        per_query.append({
            "id": q["id"],
            "query": q["query"],
            "ground_truth": q["ground_truth"],
            "notes": q.get("notes", ""),
            **metrics,
        })
        if (i + 1) % 10 == 0:
            interim = aggregate(per_query)
            print(
                f"  [{condition_id}] {i+1}/{len(queries)} "
                f"hit@1={interim['hit@1']:.3f} mrr={interim['mrr']:.4f}"
            )

    return {
        "id": condition_id,
        "desc_version": desc_version,
        "n_tools": len(tools),
        "model": model,
        "use_guide": use_guide,
        "aggregate": aggregate(per_query),
        "per_query": per_query,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scale benchmark: OLD vs NEW descriptions × 41 vs 150 tools."
    )
    parser.add_argument(
        "--data-dir",
        default="benchmarks/data",
        help="Directory containing old_descriptions.json, new_descriptions.json, confuser_tools.json",
    )
    parser.add_argument(
        "--output",
        default="benchmarks/results/scale_results.json",
        help="Output path for JSON results.",
    )
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        choices=["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-6"],
        help="Model to use for tool selection.",
    )
    parser.add_argument(
        "--conditions",
        nargs="+",
        choices=["old_41", "old_150", "new_41", "new_150"],
        default=["old_41", "old_150", "new_41", "new_150"],
        help="Which conditions to run.",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 1

    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
        return 1

    client = anthropic.Anthropic(api_key=api_key)

    data_dir = Path(args.data_dir)
    old_descs = json.loads((data_dir / "old_descriptions.json").read_text())
    new_descs = json.loads((data_dir / "new_descriptions.json").read_text())
    confusers = json.loads((data_dir / "confuser_tools.json").read_text())

    # Strip _meta key from confusers
    confusers = {k: v for k, v in confusers.items() if not k.startswith("_")}

    print(f"\nScale Benchmark — model={args.model} — {len(QUERIES)} queries × {len(args.conditions)} conditions")
    print(f"OLD tools: {len(old_descs)}, NEW tools: {len(new_descs)}, Confusers: {len(confusers)}")
    print(f"Small pool: {len(SMALL_TOOL_SET)} tools | Large pool: {len(old_descs) + len(confusers)} tools")
    print()

    condition_map = {
        "old_41":  dict(desc_version="old",  descriptions=old_descs, use_subset=True,  use_guide=False),
        "old_150": dict(desc_version="old",  descriptions=old_descs, use_subset=False, use_guide=False),
        "new_41":  dict(desc_version="new",  descriptions=new_descs, use_subset=True,  use_guide=True),
        "new_150": dict(desc_version="new",  descriptions=new_descs, use_subset=False, use_guide=True),
    }

    results = []
    for cid in args.conditions:
        cfg = condition_map[cid]
        print(f"Running condition: {cid} ...")
        result = run_condition(
            client=client,
            model=args.model,
            condition_id=cid,
            queries=QUERIES,
            confusers=confusers,
            **cfg,
        )
        results.append(result)
        agg = result["aggregate"]
        print(
            f"  → hit@1={agg['hit@1']:.4f}  hit@3={agg['hit@3']:.4f}"
            f"  mrr={agg['mrr']:.4f}  n_tools={result['n_tools']}\n"
        )

    # ── Compute deltas ──────────────────────────────────────────────────────
    result_by_id = {r["id"]: r for r in results}
    deltas = {}
    pairs = [
        ("scale_effect_old",  "old_41",  "old_150",  "OLD descriptions: accuracy drop at scale"),
        ("scale_effect_new",  "new_41",  "new_150",  "NEW descriptions: accuracy drop at scale"),
        ("govern_effect_41",  "old_41",  "new_41",   "Governance lift at 41 tools"),
        ("govern_effect_150", "old_150", "new_150",  "Governance lift at 150 tools"),
    ]
    for key, a_id, b_id, label in pairs:
        if a_id in result_by_id and b_id in result_by_id:
            a = result_by_id[a_id]["aggregate"]
            b = result_by_id[b_id]["aggregate"]
            deltas[key] = {
                "label": label,
                "from": a_id,
                "to": b_id,
                "hit@1_delta": round(b["hit@1"] - a["hit@1"], 4),
                "mrr_delta": round(b["mrr"] - a["mrr"], 4),
                "hit@3_delta": round(b["hit@3"] - a["hit@3"], 4),
            }

    # ── Summary table ───────────────────────────────────────────────────────
    header = f"{'Condition':<12} {'n_tools':>8} {'hit@1':>8} {'hit@3':>8} {'mrr':>8} {'p@3':>8} {'r@3':>8}"
    rows = [header, "-" * len(header)]
    for r in results:
        a = r["aggregate"]
        rows.append(
            f"{r['id']:<12} {r['n_tools']:>8} {a['hit@1']:>8.4f} {a['hit@3']:>8.4f}"
            f" {a['mrr']:>8.4f} {a['precision@3']:>8.4f} {a['recall@3']:>8.4f}"
        )
    summary_table = "\n".join(rows)

    print("\n" + summary_table)

    if deltas:
        print("\nKey deltas:")
        for key, d in deltas.items():
            sign = "+" if d["hit@1_delta"] >= 0 else ""
            print(f"  {d['label']}: hit@1 {sign}{d['hit@1_delta']:+.4f}, MRR {d['mrr_delta']:+.4f}")

    # ── Save ────────────────────────────────────────────────────────────────
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "model": args.model,
        "conditions": results,
        "deltas": deltas,
        "summary_table": summary_table,
        "n_queries": len(QUERIES),
        "small_tool_count": len(SMALL_TOOL_SET),
    }
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults written to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
