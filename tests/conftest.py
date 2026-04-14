"""
Pytest configuration for tool-fabric tests.

Adds the repo root to sys.path so that `linter`, `runtime`, and `benchmarks`
are importable without installation.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
