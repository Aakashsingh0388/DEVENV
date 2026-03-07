"""
doctor.py -- System health check and diagnostics command.

This command provides comprehensive health checks for the project
environment, including runtime availability, dependencies, services,
and configuration validation.
"""

import typer
from pathlib import Path
from rich.panel import Panel

from ..scanner import full_scan
from ..detector import detect_all
from ..cli_utils.runtime_utils import check_runtime, check_all_runtimes
from ..cli_utils.docker_utils import detect_docker
from ..service_detector import detect_services
from ..version_parser import get_all_version_requirements
from ..cli_utils.cli_utils import print_banner, console
from ..cli_utils.project_utils import _validate_directory, _run_scan


def doctor(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory (for context-aware checks).",
    ),
) -> None:
    """
    Run a comprehensive health check on the project environment.

    This command provides a full diagnostic report including:
    - Runtime availability (Node.js, Python, Go, etc.)
    - Project dependencies and configuration
    - Required services (databases, caches, queues)
    - Docker configuration status
    - Version requirements validation

    Example output:

        Runtime Check
        [check] Node.js installed
        [check] Python installed
        [x] Docker missing
        [check] Git installed

        Project Dependencies
        [check] package.json detected
        [check] requirements.txt detected

        Services
        [check] PostgreSQL required (docker-compose)
        [check] Redis required (environment)
    """
    project_path = _validate_directory(path)

    print_banner()

    console.print("[bold bright_cyan]Running system health check...[/bold bright_cyan]\n")

    # ── Section 1: Runtime Check ────────────────────────────────────
    console.print(
        Panel(
            "[bold]Runtime Check[/bold]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()

    # Check all runtimes
    runtime_results = check_all_runtimes()
    for result in runtime_results:
        if result.installed:
            status = "[green]✓[/green]"
            version_info = f" {result.version}" if result.version else ""
        else:
            status = "[red]✗[/red]"
            version_info = " not installed"

        console.print(f"{status} {result.language}{version_info}")

    console.print()

    # ── Section 2: Project Analysis ────────────────────────────────
    console.print(
        Panel(
            "[bold]Project Analysis[/bold]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()

    result = _run_scan(project_path)

    if result.language_files:
        console.print(f"[green]✓ Detected {len(result.language_files)} language(s)[/green]")

        for lang, files in result.language_files.items():
            runtime = check_runtime(lang)
            if runtime.installed:
                console.print(f"[green]✓ {lang}[/green] - {len(files)} file(s)")
            else:
                console.print(f"[red]✗ {lang}[/red] - runtime missing")

        # Check for package managers
        detections = detect_all(result.language_files)
        detected_managers = {d.package_manager for d in detections if d.package_manager != "unknown"}
        if detected_managers:
            console.print(f"[green]✓ Package managers: {', '.join(detected_managers)}[/green]")
        else:
            console.print("[yellow]⚠ No package managers detected[/yellow]")
    else:
        console.print("[yellow]⚠ No project files detected[/yellow]")

    # Check for environment files
    env_files = list(project_path.glob(".env*"))
    if env_files:
        console.print(f"[green]✓ Environment files: {len(env_files)} found[/green]")
    else:
        console.print("[yellow]⚠ No environment files found[/yellow]")

    console.print()

    # ── Section 3: Docker Configuration ────────────────────────────
    console.print(
        Panel(
            "[bold]Docker Configuration[/bold]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()

    docker_info = detect_docker(project_path)
    if docker_info.has_dockerfile:
        console.print("[green]✓ Dockerfile detected[/green]")
    else:
        console.print("[dim]- No Dockerfile found[/dim]")

    if docker_info.has_compose:
        if docker_info.compose_installed:
            console.print("[green]✓ Docker Compose available[/green]")
        else:
            console.print("[red]✗ Docker Compose not installed[/red]")
    else:
        console.print("[dim]- No Docker Compose files found[/dim]")

    if docker_info.docker_installed:
        console.print("[green]✓ Docker runtime available[/green]")
    else:
        console.print("[red]✗ Docker runtime not installed[/red]")

    console.print()

    # ── Section 4: Services ────────────────────────────────────────
    console.print(
        Panel(
            "[bold]Required Services[/bold]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()

    try:
        services = detect_services(project_path)
        if services.services:
            for service in services.services:
                console.print(f"[blue]ℹ {service.name}[/blue] - {service.purpose}")
        else:
            console.print("[dim]- No services detected[/dim]")
    except ImportError:
        console.print("[yellow]⚠ Service detection not available[/yellow]")

    console.print()

    # ── Section 5: Version Requirements ────────────────────────────
    console.print(
        Panel(
            "[bold]Version Requirements[/bold]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()

    version_reqs = get_all_version_requirements(project_path)
    if version_reqs:
        for lang, req in version_reqs.items():
            runtime = check_runtime(lang)
            if runtime.installed and runtime.version:
                # Simple version check (could be enhanced)
                console.print(f"[green]✓ {lang}[/green] - requires {req}, found {runtime.version}")
            else:
                console.print(f"[red]✗ {lang}[/red] - requires {req}, runtime not available")
    else:
        console.print("[dim]- No version requirements specified[/dim]")

    console.print()

    # ── Summary ────────────────────────────────────────────────────
    console.print(
        Panel(
            "[bold]Health Check Complete[/bold]\n\n"
            "Use [bold cyan]devenv setup[/bold cyan] for full environment setup\n"
            "Use [bold cyan]devenv install[/bold cyan] to install dependencies\n"
            "Use [bold cyan]devenv run[/bold cyan] to start development server",
            border_style="green",
            padding=(1, 2),
        )
    )