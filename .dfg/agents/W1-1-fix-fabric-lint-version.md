---
id: W1-1
role: bug-fixer
name: Fix broken `fabric-lint --version` (Click package_name inference)
purpose: >
  The `@click.version_option()` decorator at `linter/cli.py:36` has no
  arguments, so Click attempts to infer the package name from the entry
  point's module ('linter') — but the installed package is 'tool-fabric'.
  Calling `fabric-lint --version` therefore raises:

      RuntimeError: 'linter' is not installed. Try passing
                    'package_name' instead.

  This unit ships the minimal fix — pass `package_name="tool-fabric"`
  to the decorator — and a regression test in `tests/test_cli.py` that
  invokes the CLI with `--version` and asserts a clean exit + version
  string output.

wave: W1
squad_id: linter-cli
unit: W1-1
depends_on: []
blocks: []
governance_tier: VT1
sized: S
hardening_max_cycles: 2
prompt_version: 1
read_contract:
  must_read:
    - linter/cli.py
    - pyproject.toml
  may_read:
    - tests/test_checks.py
    - tests/conftest.py
output_contract:
  files:
    - linter/cli.py
    - tests/test_cli.py
  acceptance: >
    1. `fabric-lint --version` exits 0 and prints a string of the form
       "fabric-lint, version <SEMVER>" (Click default format) where
       <SEMVER> matches the version in `pyproject.toml`.
    2. A regression test in `tests/test_cli.py` invokes the CLI with
       `--version` (via `click.testing.CliRunner`) and asserts:
         - exit_code == 0
         - "version" in result.output (case-insensitive)
         - the pyproject version string appears in result.output
    3. No other behaviour change — `fabric-lint check`, `report`, `init`
       continue to work identically.
---

# W1-1 — Fix broken `fabric-lint --version`

## Reproduction (from main, pre-fix)

```bash
$ pip install -e .
$ fabric-lint --version
Traceback (most recent call last):
  ...
RuntimeError: 'linter' is not installed. Try passing 'package_name' instead.
```

The error is raised by Click's `version_option_callback` (Click ≥ 8.0)
when the auto-inferred package name does not match an installed
distribution.

## Fix

Single-line change in `linter/cli.py`:

```diff
 @click.group()
-@click.version_option()
+@click.version_option(package_name="tool-fabric")
 def cli():
     """Declarative governance for LLM tool registries."""
```

Alternative considered: read version from `importlib.metadata.version` and
pass via `version=` parameter. Rejected — adds an import and is the
same data path Click takes internally; `package_name=` is the canonical
fix.

## Regression test

```python
# tests/test_cli.py
from click.testing import CliRunner
from linter.cli import cli


def test_version_flag_returns_pyproject_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    # Click's default format: "<prog>, version <ver>"
    assert "version" in result.output.lower()
    # Ensure the pyproject version (0.2.0 at time of fix) shows up.
    # Read from package metadata for forward-compat.
    from importlib.metadata import version

    assert version("tool-fabric") in result.output
```

## Anti-goals

- Do NOT introduce a new dependency.
- Do NOT change the version string format (preserve Click's default
  `<prog>, version <ver>`).
- Do NOT touch `pyproject.toml` — version source remains the project
  metadata.

## Empirical receipt expected

```bash
$ pip install -e .
$ fabric-lint --version
fabric-lint, version 0.2.0
$ pytest tests/test_cli.py -v
tests/test_cli.py::test_version_flag_returns_pyproject_version PASSED
```

## Composes with

- PR #1 (bootstrap) — this is the deliberately-small first wave delivering
  on the harness chain end-to-end.
- W1 wave-gate criteria (`.dfg/plan.yaml` waves[0].gate.criteria).
