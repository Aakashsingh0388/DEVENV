"""
cli.py -- Main Typer CLI entry point that wires everything together.

This is the orchestration layer that imports and registers all CLI commands
from the commands/ directory. It does not contain business logic itself.
"""

from typing import Optional

import typer

from . import __version__
from .commands import (
    scan, install, setup, run, doctor, info, summary
)
from .cli_utils.cli_utils import console

# ── Typer app ───────────────────────────────────────────────────────────
app = typer.Typer(
    name="devenv",
    help="DEVENV -- Automatic project environment setup and dependency installer.",
    add_completion=False,
    no_args_is_help=True,
)


# ── Version callback ────────────────────────────────────────────────────
def _version_callback(value: bool) -> None:
    """Print the version string and exit immediately."""
    if value:
        console.print(f"devenv v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """DEVENV -- Automatic Project Environment Setup & Dependency Installer."""


# ── Register commands ───────────────────────────────────────────────────
app.command()(scan.scan)
app.command()(install.install)
app.command()(install.init)  # Legacy alias
app.command()(setup.setup)
app.command()(run.run)
app.command()(doctor.doctor)
app.command()(info.info)
app.command()(summary.summary)


# Allow ``python devenv/cli.py`` invocation during development.
if __name__ == "__main__":
    app()