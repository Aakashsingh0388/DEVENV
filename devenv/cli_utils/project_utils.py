"""
project_utils.py -- Project-related utility functions.

This module contains shared functions for project scanning, validation,
and common operations used across commands.
"""

import typer
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, TextColumn

from .cli_utils import console


def _handle_error(message: str, exit_code: int = 1) -> None:
    """Print an error message and exit."""
    console.print(f"[bold red]Error:[/bold red] {message}")
    raise typer.Exit(code=exit_code)


def _validate_directory(path: str) -> Path:
    """Validate and return resolved path."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        _handle_error(f"'{project_path}' is not a directory.")
    return project_path


def _run_scan(project_path: Path):
    """Run a full scan with a Rich progress spinner."""
    from ..scanner import full_scan
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Scanning project directory...", total=None)
        return full_scan(str(project_path))