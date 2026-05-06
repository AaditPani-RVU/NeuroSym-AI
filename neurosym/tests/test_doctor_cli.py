"""Tests for the doctor CLI and Typer entrypoint — 0.3.1 coverage."""

from __future__ import annotations

import subprocess
import sys

from typer.testing import CliRunner

from neurosym.cli_tui import app

runner = CliRunner()


# ── doctor (argparse __main__) ────────────────────────────────────────────────


def test_doctor_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "neurosym", "doctor"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"doctor exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_doctor_prints_version():
    from neurosym.version import __version__

    result = subprocess.run(
        [sys.executable, "-m", "neurosym", "doctor"],
        capture_output=True,
        text=True,
    )
    assert __version__ in result.stdout


def test_doctor_prints_optional_deps():
    result = subprocess.run(
        [sys.executable, "-m", "neurosym", "doctor"],
        capture_output=True,
        text=True,
    )
    assert "Optional dependencies" in result.stdout
    # At least these always-present runtime deps must show OK
    for dep in ("pydantic", "typer", "rich"):
        assert dep in result.stdout


def test_doctor_prints_rule_packs():
    result = subprocess.run(
        [sys.executable, "-m", "neurosym", "doctor"],
        capture_output=True,
        text=True,
    )
    assert "Rule packs" in result.stdout


def test_doctor_prints_benchmark():
    result = subprocess.run(
        [sys.executable, "-m", "neurosym", "doctor"],
        capture_output=True,
        text=True,
    )
    # Benchmark either runs (shows "cases=") or gracefully degrades
    assert ("cases=" in result.stdout) or ("benchmark unavailable" in result.stdout)


# ── Typer entrypoint ──────────────────────────────────────────────────────────


def test_typer_help_exits_zero():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_typer_help_lists_run_command():
    result = runner.invoke(app, ["--help"])
    assert "run" in result.output


def test_typer_no_args_shows_help():
    """no_args_is_help=True means invoking with no args prints help text."""
    result = runner.invoke(app, [])
    # Typer exits 2 via CliRunner for no-args-is-help; the important check is
    # that help content is printed, not that the exit code is 0.
    assert "Usage" in result.output or "Commands" in result.output


def test_argparse_no_subcommand_exits_nonzero():
    """Argparse entrypoint requires a subcommand — omitting one must exit non-zero."""
    result = subprocess.run(
        [sys.executable, "-m", "neurosym"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
