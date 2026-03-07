"""
cli_utils.py -- Shared CLI utilities and display functions.

This module contains common functions used across CLI commands,
including banners, status messages, and Rich formatting helpers.
"""

from pathlib import Path
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .. import __version__

# Shared console instance
console = Console()


def print_banner() -> None:
    """Print the DEVENV banner."""
    console.print(
        Panel(
            f"[bold bright_cyan]DEVENV  v{__version__}[/bold bright_cyan]\n"
            "[dim]Automatic Project Environment Setup[/dim]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()


def print_no_projects() -> None:
    """Print message when no projects are detected."""
    console.print(
        Panel(
            "[yellow]No supported projects detected in this directory.[/yellow]\n\n"
            "[dim]DEVENV supports:[/dim]\n"
            "  • Node.js (package.json)\n"
            "  • Python (requirements.txt, pyproject.toml)\n"
            "  • Go (go.mod)\n"
            "  • Rust (Cargo.toml)\n"
            "  • Java (pom.xml, build.gradle)\n"
            "  • PHP (composer.json)\n"
            "  • Ruby (Gemfile)\n"
            "  • .NET (*.csproj)\n"
            "  • Terraform (main.tf)\n"
            "  • Docker (Dockerfile, docker-compose.yml)\n\n"
            "[dim]Try running in a different directory or check for typos in dependency files.[/dim]",
            title="[bold yellow]No Projects Found[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


def print_multiple_languages(languages: List[str]) -> None:
    """Print message when multiple languages are detected."""
    lang_list = ", ".join(sorted(languages))
    console.print(
        f"[blue]ℹ Detected multiple languages: {lang_list}[/blue]\n"
        "[dim]Processing each language stack independently...[/dim]\n"
    )


def print_detection_summary(
    language: str,
    package_manager: str,
    dependency_file: str,
    runtime_installed: bool,
    runtime_version: str = None,
) -> None:
    """Print a summary of detection results."""
    status = "[green]✓[/green]" if runtime_installed else "[red]✗[/red]"
    version = f" {runtime_version}" if runtime_version else " (installed)"
    
    if not runtime_installed:
        version = " (not found)"

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Label", style="dim", min_width=15)
    table.add_column("Value", style="white")

    table.add_row(" Language:", f"[bold]{language}[/bold]")
    table.add_row(" Package Manager:", f"[bold]{package_manager}[/bold]")
    table.add_row(" Dependency File:", f"[dim]{dependency_file}[/dim]")
    table.add_row(" Runtime:", f"{status} {language}{version}")

    console.print(table)


def print_runtime_missing(language: str, command: str) -> None:
    """Print message when runtime is missing."""
    console.print(
        f"[red]✗ {language} runtime not found[/red]\n"
        f"[dim]Install {language} first or run 'devenv setup' for automatic installation[/dim]\n"
    )


def print_install_start() -> None:
    """Print installation start message."""
    console.print("[bold cyan]Installing dependencies...[/bold cyan]")


def print_install_success() -> None:
    """Print installation success message."""
    console.print("[green]✓ Dependencies installed successfully[/green]")


def print_install_error(error: str) -> None:
    """Print installation error message."""
    console.print(f"[bold red]✗ Installation failed:[/bold red] {error}")


def print_skipped() -> None:
    """Print skipped message."""
    console.print("[yellow]⚠ Installation skipped by user[/yellow]")