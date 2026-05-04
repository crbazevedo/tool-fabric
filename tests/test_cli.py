"""Regression tests for the fabric-lint CLI surface.

W1-1 (2026-05-04) — initial test for the `--version` flag fix. Click's
`@click.version_option()` (no args) raised RuntimeError at runtime because
the entry-point's module is `linter.cli` but the installed package is
`tool-fabric`. Fix: pass `package_name="tool-fabric"`. This file ships
the regression coverage.
"""

from importlib.metadata import version

from click.testing import CliRunner

from linter.cli import cli


def test_version_flag_returns_pyproject_version() -> None:
    """W1-1 regression: `fabric-lint --version` exits 0 and prints the
    pyproject version. Pre-fix, Click's package_name inference failed
    on `linter.cli` (the module) vs `tool-fabric` (the distribution),
    raising RuntimeError mid-process. The fix passes
    `package_name="tool-fabric"` explicitly."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0, (
        f"--version should exit 0, got {result.exit_code}; output={result.output!r}"
    )
    assert "version" in result.output.lower(), (
        f"output should contain 'version', got {result.output!r}"
    )

    pyproject_version = version("tool-fabric")
    assert pyproject_version in result.output, (
        f"output should contain pyproject version {pyproject_version!r}; got {result.output!r}"
    )
