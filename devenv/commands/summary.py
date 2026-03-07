"""
summary.py -- Quick project summary command.

This command provides a concise overview of the project including
language, runtime version, package manager, dependencies, and services.
"""

import typer
from pathlib import Path

from ..cli_utils.cli_utils import print_banner
from ..cli_utils.project_utils import _validate_directory


def summary(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory.",
    ),
) -> None:
    """
    Display a quick project summary with all key information.

    Provides a concise overview including:
    - Language and framework
    - Runtime version
    - Package manager
    - Dependency count
    - Required services
    - Docker status

    Example output:

        Project Summary

        Language:        Node.js (Next.js)
        Runtime:         Node v20.10.0
        Package Manager: pnpm
        Dependencies:    53 packages

        Services:
          PostgreSQL
          Redis

        Docker:
          Dockerfile detected
    """
    project_path = _validate_directory(path)

    print_banner()

    try:
        from ..project_summary import generate_project_summary, print_project_summary

        summary_data = generate_project_summary(project_path)
        print_project_summary(summary_data)

    except ImportError:
        # Fallback to basic info if module not available
        console.print("[yellow]Summary module not available. Use 'devenv info' instead.[/yellow]")
        raise typer.Exit(code=1)