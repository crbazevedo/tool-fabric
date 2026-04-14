"""
tool-fabric runtime enricher.

Enriches MCP tool descriptions with .tool-fabric.yaml metadata so that
LLMs see alternatives cross-references, concept definitions, and fan-out
pattern hints alongside the raw description.

This is the "before/after" that the benchmark measures:
  Before: LLM sees only the raw MCP description.
  After:  LLM sees the enriched description with full fabric context.
"""

from .enricher import FabricEnricher

__all__ = ["FabricEnricher"]
