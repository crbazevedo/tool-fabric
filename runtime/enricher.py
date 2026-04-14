"""
FabricEnricher — enriches MCP tool descriptions with .tool-fabric.yaml metadata.

Given a parsed .tool-fabric.yaml registry and a dict of raw tool descriptions,
produces enriched descriptions that expose:

  1. Original description (trimmed)
  2. query_tips — when to use vs. when not to use this tool
  3. Alternatives — "instead of X, use Y when Z"
  4. Concept definitions — inline glossary for domain concepts required
  5. Pattern hints — which multi-step workflows (fan-out) this tool participates in

The enriched text is designed to be injected into the LLM system prompt or
tool-description field so the model has governance context at selection time.
"""

from __future__ import annotations

from typing import Any


class FabricEnricher:
    """
    Enriches tool descriptions using .tool-fabric.yaml annotations.

    Parameters
    ----------
    registry : dict
        Parsed .tool-fabric.yaml content (the result of yaml.safe_load).

    Examples
    --------
    >>> import yaml
    >>> from runtime.enricher import FabricEnricher
    >>> with open("examples/carlos-os/.tool-fabric.yaml") as f:
    ...     reg = yaml.safe_load(f)
    >>> enricher = FabricEnricher(reg)
    >>> raw = {"slack_send_message": "Sends a message to Slack."}
    >>> enriched = enricher.enrich_descriptions(raw)
    >>> "gmail_send" in enriched["slack_send_message"]  # alternative surfaced
    True
    """

    def __init__(self, registry: dict[str, Any]) -> None:
        self._tools: dict[str, dict] = registry.get("tools") or {}
        self._concepts: dict[str, dict] = registry.get("concepts") or {}
        self._patterns: dict[str, dict] = registry.get("patterns") or {}
        self._tool_to_patterns: dict[str, list[str]] = self._build_tool_to_patterns()

    # ── Index builders ─────────────────────────────────────────────────────

    def _build_tool_to_patterns(self) -> dict[str, list[str]]:
        """Build reverse index: tool_id → list of pattern names that reference it."""
        index: dict[str, list[str]] = {}
        for pattern_name, pdata in self._patterns.items():
            for step in pdata.get("tool_sequence") or []:
                step_tools = [step] if isinstance(step, str) else list(step)
                for tid in step_tools:
                    index.setdefault(tid, []).append(pattern_name)
        return index

    # ── Public API ─────────────────────────────────────────────────────────

    def enrich_descriptions(
        self, raw_descriptions: dict[str, str]
    ) -> dict[str, str]:
        """
        Enrich a dict of {tool_id: raw_description} with fabric metadata.

        Tools not present in the registry are returned with their raw description
        unchanged (enrichment is additive, never destructive).

        Parameters
        ----------
        raw_descriptions : dict[str, str]
            Mapping of tool_id → raw MCP description.

        Returns
        -------
        dict[str, str]
            Same keys, with enriched description values.
        """
        return {
            tid: self.enrich_tool(tid, raw_desc)
            for tid, raw_desc in raw_descriptions.items()
        }

    def enrich_tool(self, tool_id: str, raw_description: str) -> str:
        """
        Enrich a single tool description with fabric metadata.

        Parameters
        ----------
        tool_id : str
            The tool identifier as it appears in .tool-fabric.yaml.
        raw_description : str
            The raw description from the MCP server.

        Returns
        -------
        str
            Multi-paragraph enriched description. Paragraphs are separated
            by blank lines for readability in system prompts.
        """
        parts: list[str] = [raw_description.strip()]
        tdata = self._tools.get(tool_id) or {}

        # ── Layer 2: query_tips ────────────────────────────────────────────
        query_tips = (tdata.get("query_tips") or "").strip()
        if query_tips:
            parts.append(f"Usage guidance: {query_tips}")

        # ── Layer 3: alternatives with disambiguation hints ─────────────────
        alternatives = tdata.get("alternatives") or []
        if alternatives:
            alt_lines: list[str] = []
            for alt_id in alternatives:
                alt_data = self._tools.get(alt_id) or {}
                alt_tips = (alt_data.get("query_tips") or "").strip()
                if alt_tips:
                    alt_lines.append(f"  - {alt_id}: {alt_tips}")
                else:
                    alt_lines.append(f"  - {alt_id}")
            parts.append(
                "Alternatives (use instead when appropriate):\n"
                + "\n".join(alt_lines)
            )

        # ── Layer 4: concept definitions (inline glossary) ─────────────────
        required_concepts = tdata.get("concepts_required") or []
        if required_concepts:
            concept_lines: list[str] = []
            for cid in required_concepts:
                cdata = self._concepts.get(cid) or {}
                cdesc = (cdata.get("description") or "").strip()
                if cdesc:
                    concept_lines.append(f"  - {cid}: {cdesc}")
                else:
                    concept_lines.append(f"  - {cid}")
            if concept_lines:
                parts.append(
                    "Required domain concepts:\n" + "\n".join(concept_lines)
                )

        # ── Layer 5: fan-out pattern hints ─────────────────────────────────
        pattern_names = self._tool_to_patterns.get(tool_id, [])
        if pattern_names:
            pattern_descs: list[str] = []
            for pname in pattern_names:
                pdata = self._patterns.get(pname) or {}
                pdisplay = (pdata.get("name") or pname).strip()
                triggers = pdata.get("intent_triggers") or []
                if triggers:
                    pattern_descs.append(f'  - {pdisplay} (e.g. "{triggers[0]}")')
                else:
                    pattern_descs.append(f"  - {pdisplay}")
            parts.append(
                "This tool participates in multi-step workflows:\n"
                + "\n".join(pattern_descs)
            )

        return "\n\n".join(parts)
