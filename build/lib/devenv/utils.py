"""
utils.py -- Shared constants, data structures, and Rich display helpers.

This module centralises:
  - The mapping between dependency files and programming languages.
  - Glob-based dependency patterns (e.g. ``*.csproj``).
  - Runtime version-check commands for each language.
  - Package manager detection metadata (indicator files, install commands).
  - Run commands for launching dev servers / processes.
  - Subproject directory conventions for monorepo scanning.
  - All Rich-powered terminal output functions used across the CLI.

Keeping these in one place ensures every other module imports from a
single source of truth and keeps the rest of the codebase focused on
its own responsibility.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__

# ---------------------------------------------------------------------------
# Shared Rich console -- every module that prints to the terminal should
# import and use this instance so output remains consistent.
# ---------------------------------------------------------------------------
console = Console()


# =====================================================================
# Dependency file -> Language mapping
# =====================================================================
# Each key is a filename that, when found in a project root, indicates
# which programming language the project uses.
# =====================================================================

DEPENDENCY_FILES: Dict[str, str] = {
    # --- Node.js ---
    "package.json":       "Node.js",
    # --- Python ---
    "requirements.txt":   "Python",
    "pyproject.toml":     "Python",
    "Pipfile":            "Python",
    # --- Go ---
    "go.mod":             "Go",
    # --- Rust ---
    "Cargo.toml":         "Rust",
    # --- Java ---
    "pom.xml":            "Java",
    "build.gradle":       "Java",
    # --- PHP ---
    "composer.json":      "PHP",
    # --- Ruby ---
    "Gemfile":            "Ruby",
    # --- .NET ---
    # *.csproj files are handled via glob patterns in DEPENDENCY_GLOBS
    # --- Terraform ---
    "main.tf":            "Terraform",
    # --- Docker ---
    "Dockerfile":         "Docker",
    "docker-compose.yml": "Docker",
    "docker-compose.yaml": "Docker",
}


# =====================================================================
# Glob-based dependency patterns
# =====================================================================
# Some ecosystems use wildcard-matched filenames (e.g. *.csproj for .NET).
# The scanner checks these patterns in addition to the exact-match map.
# =====================================================================

DEPENDENCY_GLOBS: Dict[str, str] = {
    "*.csproj": ".NET",
}


# =====================================================================
# Subproject directories
# =====================================================================
# Common directory names that may contain independent sub-projects
# in monorepo-style layouts.  The scanner will look inside these.
# =====================================================================

SUBPROJECT_DIRS = frozenset({
    "frontend", "backend", "services", "apps",
    "packages", "libs", "modules", "src",
})


# =====================================================================
# Runtime version commands
# =====================================================================
# For each language we store the binary name and the arguments needed
# to print a version string.  ``runtime_check.py`` uses this to verify
# the runtime is available before attempting an install.
# =====================================================================

RUNTIME_CHECKS: Dict[str, Tuple[str, List[str]]] = {
    "Node.js":    ("node",    ["--version"]),
    "Python":     ("python3", ["--version"]),
    "Go":         ("go",      ["version"]),
    "Rust":       ("rustc",   ["--version"]),
    "Java":       ("java",    ["-version"]),
    "PHP":        ("php",     ["-v"]),
    "Ruby":       ("ruby",    ["-v"]),
    ".NET":       ("dotnet",  ["--version"]),
    "Terraform":  ("terraform", ["--version"]),
    "Docker":     ("docker",  ["--version"]),
}


# =====================================================================
# Package manager detection
# =====================================================================
# A PackageManagerInfo describes how to *detect* a specific package
# manager (via an indicator file) and how to *run* it (install_command).
#
# Each language has an ordered list -- the first entry whose indicator
# file is present in the project wins.  This ordering encodes sensible
# defaults (e.g. prefer pnpm > yarn > bun > npm for Node.js).
# =====================================================================

@dataclass
class PackageManagerInfo:
    """Metadata for a single package manager variant."""

    name: str
    """Human-readable name shown in the summary, e.g. ``npm``."""

    indicator_file: str
    """Filename whose presence signals this manager is in use."""

    install_command: List[str]
    """Full argv list to install dependencies, e.g. ``["npm", "install"]``."""


PACKAGE_MANAGERS: Dict[str, List[PackageManagerInfo]] = {
    "Node.js": [
        PackageManagerInfo("pnpm",  "pnpm-lock.yaml",   ["pnpm", "install"]),
        PackageManagerInfo("yarn",  "yarn.lock",         ["yarn", "install"]),
        PackageManagerInfo("bun",   "bun.lockb",         ["bun", "install"]),
        PackageManagerInfo("npm",   "package-lock.json", ["npm", "install"]),
        # Fallback -- if there is no lock file at all, default to npm.
        PackageManagerInfo("npm",   "package.json",      ["npm", "install"]),
    ],
    "Python": [
        PackageManagerInfo("poetry", "poetry.lock",      ["poetry", "install"]),
        PackageManagerInfo("poetry", "pyproject.toml",   ["poetry", "install"]),
        PackageManagerInfo("pipenv", "Pipfile.lock",     ["pipenv", "install"]),
        PackageManagerInfo("pipenv", "Pipfile",          ["pipenv", "install"]),
        PackageManagerInfo("pip",    "requirements.txt", ["pip", "install", "-r", "requirements.txt"]),
    ],
    "Go": [
        PackageManagerInfo("go modules", "go.mod", ["go", "mod", "download"]),
    ],
    "Rust": [
        PackageManagerInfo("cargo", "Cargo.toml", ["cargo", "build"]),
    ],
    "Java": [
        PackageManagerInfo("gradle", "build.gradle",     ["gradle", "build"]),
        PackageManagerInfo("gradle", "build.gradle.kts", ["gradle", "build"]),
        PackageManagerInfo("maven",  "pom.xml",          ["mvn", "install"]),
    ],
    "PHP": [
        PackageManagerInfo("composer", "composer.json", ["composer", "install"]),
    ],
    "Ruby": [
        PackageManagerInfo("bundler", "Gemfile", ["bundle", "install"]),
    ],
    ".NET": [
        PackageManagerInfo("dotnet", "*.csproj", ["dotnet", "restore"]),
    ],
    "Terraform": [
        PackageManagerInfo("terraform", "main.tf", ["terraform", "init"]),
    ],
    "Docker": [
        PackageManagerInfo("docker-compose", "docker-compose.yml",  ["docker-compose", "build"]),
        PackageManagerInfo("docker-compose", "docker-compose.yaml", ["docker-compose", "build"]),
        PackageManagerInfo("docker",         "Dockerfile",          ["docker", "build", "."]),
    ],
}


# =====================================================================
# Run commands -- how to start a dev server for each ecosystem
# =====================================================================

RUN_COMMANDS: Dict[str, List[List[str]]] = {
    "Node.js": [
        ["npm", "run", "dev"],
        ["npm", "start"],
    ],
    "Python": [
        ["python3", "manage.py", "runserver"],
        ["python3", "app.py"],
        ["python3", "main.py"],
    ],
    "Go": [
        ["go", "run", "."],
    ],
    "Rust": [
        ["cargo", "run"],
    ],
    "Java": [
        ["gradle", "bootRun"],
        ["mvn", "spring-boot:run"],
    ],
    "PHP": [
        ["php", "artisan", "serve"],
        ["php", "-S", "localhost:8000"],
    ],
    "Ruby": [
        ["bundle", "exec", "rails", "server"],
    ],
    ".NET": [
        ["dotnet", "run"],
    ],
    "Docker": [
        ["docker-compose", "up"],
    ],
}


# =====================================================================
# Environment file templates
# =====================================================================

ENV_TEMPLATES = [
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.defaults",
]


# =====================================================================
# Rich display helpers
# =====================================================================
# These functions are the *only* place that interacts with the terminal.
# Every visual element -- banners, tables, status lines, error
# messages -- lives here so that the rest of the codebase remains
# presentation-agnostic and easy to test.
# =====================================================================

def print_banner() -> None:
    """Print the DEVENV startup banner with version information."""
    banner = Text()
    banner.append("DEVENV", style="bold bright_cyan")
    banner.append(f"  v{__version__}", style="dim")
    banner.append("\nAutomatic Project Environment Setup", style="italic")
    console.print(Panel(banner, border_style="bright_cyan", padding=(1, 2)))
    console.print()


def print_scan_start() -> None:
    """Indicate that the directory scan has begun."""
    console.print("[bold cyan]Scanning project directory...[/bold cyan]\n")


def print_no_projects() -> None:
    """Warn the user that no recognised dependency files were found."""
    console.print(
        Panel(
            "[yellow]No recognised dependency files found in this directory.[/yellow]\n"
            "Make sure you are running devenv from a project root.",
            title="Nothing Found",
            border_style="yellow",
        )
    )


def print_detection_summary(
    language: str,
    package_manager: str,
    dependency_file: str,
    runtime_installed: bool,
    runtime_version: Optional[str],
) -> None:
    """
    Render a bordered table summarising the detection results.

    Shows the detected language, package manager, dependency file, and
    runtime availability at a glance so the user can confirm before
    proceeding with the install.
    """
    table = Table(
        show_header=False,
        border_style="bright_cyan",
        padding=(0, 2),
        title="Project Summary",
        title_style="bold bright_cyan",
    )
    table.add_column("Key", style="bold white", min_width=20)
    table.add_column("Value", style="white")

    table.add_row("Project detected", f"[bold]{language}[/bold]")
    table.add_row("Package manager",  f"[bold]{package_manager}[/bold]")
    table.add_row("Dependency file",  f"[dim]{dependency_file}[/dim]")

    if runtime_installed:
        version_str = runtime_version or "installed"
        table.add_row("Runtime", f"[green]{version_str}[/green]")
    else:
        table.add_row("Runtime", "[red]NOT FOUND[/red]")

    console.print(table)
    console.print()


def print_runtime_missing(language: str, command: str) -> None:
    """Tell the user the required runtime binary is not on PATH."""
    console.print(
        f"[bold red]{language} runtime not found on this system.[/bold red]\n"
        f"  Expected command: [dim]{command}[/dim]\n"
        "  Please install the runtime before proceeding.\n"
    )


def print_install_start() -> None:
    """Signal that the dependency installation is starting."""
    console.print("[bold cyan]Installing dependencies...[/bold cyan]\n")


def print_install_success() -> None:
    """Celebrate a successful install."""
    console.print(
        "\n[bold green]Dependencies installed successfully.[/bold green]"
    )


def print_install_error(message: str) -> None:
    """Show a clear, red-highlighted error message when an install fails."""
    console.print(f"\n[bold red]Installation failed:[/bold red] {message}")


def print_skipped() -> None:
    """Inform the user that installation was skipped by their choice."""
    console.print("[yellow]Installation skipped by user.[/yellow]")


def print_multiple_languages(languages: List[str]) -> None:
    """List all detected languages when a project is polyglot."""
    lang_list = ", ".join(f"[bold]{lang}[/bold]" for lang in languages)
    console.print(f"[cyan]Multiple languages detected:[/cyan] {lang_list}\n")
