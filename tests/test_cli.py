"""Regression tests for the fabric-lint CLI surface.

W1-1 (2026-05-04) — initial test for the `--version` flag fix. Click's
`@click.version_option()` (no args) raised RuntimeError at runtime because
the entry-point's module is `linter.cli` but the installed package is
`tool-fabric`. Fix: pass `package_name="tool-fabric"`. This file ships
the regression coverage.
"""

import re
from importlib.metadata import PackageNotFoundError, version

import pytest
from click.testing import CliRunner

from linter.cli import cli

# Click >= 8.0's default version output format: `<prog>, version <semver>`.
# Under `CliRunner.invoke(cli, ...)` the prog defaults to the function name
# (`cli`); under the installed script (`fabric-lint`) it's the entry-point
# name. Either is accepted — what we're guarding is the format shape, not
# the prog string.
_CLICK_VERSION_PATTERN = re.compile(
    r"^(?:cli|fabric-lint),\s+version\s+\d+\.\d+\.\d+", re.MULTILINE
)


def test_version_flag_returns_pyproject_version() -> None:
    """W1-1 regression: `fabric-lint --version` exits 0 and prints the
    pyproject version in Click 8.x's default format.

    Pre-fix, Click's package_name inference failed on `linter.cli` (the
    module) vs `tool-fabric` (the distribution), raising RuntimeError
    mid-process. The fix passes `package_name="tool-fabric"` explicitly.

    Cycle-2 hardening (assumption-critic #5 MAJOR-set):
      - Skip cleanly if the package isn't installed as a distribution
        (PackageNotFoundError on source-only / vendored runs).
      - Match Click's exact `<prog>, version <semver>` format rather
        than substring-on-"version".
    """
    try:
        pyproject_version = version("tool-fabric")
    except PackageNotFoundError:
        pytest.skip(
            "tool-fabric is not installed as a distribution; "
            "run `pip install -e .` (or equivalent) before running this test."
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0, (
        f"--version should exit 0, got {result.exit_code}; output={result.output!r}"
    )
    assert _CLICK_VERSION_PATTERN.search(result.output), (
        f"output should match `fabric-lint, version X.Y.Z`; got {result.output!r}"
    )
    assert pyproject_version in result.output, (
        f"output should contain pyproject version {pyproject_version!r}; "
        f"got {result.output!r}"
    )
