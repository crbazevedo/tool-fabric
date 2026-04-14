"""
tool-fabric linter

Validates .tool-fabric.yaml registries against governance rules.
Catches overlap, orphan tools, broken composition edges, and concept gaps
before they reach inference time.
"""

__version__ = "0.1.0"
__all__ = ["Registry", "LintResult", "Violation", "run_checks"]

from .checks import (
    Registry,
    LintResult,
    Violation,
    run_checks,
)
