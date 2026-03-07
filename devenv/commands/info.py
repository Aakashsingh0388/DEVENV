"""
info.py -- Detailed project metadata display command.

This command shows comprehensive project information including
languages, package managers, environment files, Docker config,
and subproject directories.
"""

import typer
from pathlib import Path
from rich.table import Table
from rich.panel import Panel

from ..scanner import full_scan
from ..detector import detect_all
from ..cli_utils.docker_utils import detect_docker, show_docker_status
from ..version_parser import get_all_version_requirements
from ..cli_utils.cli_utils import print_banner, console
from ..cli_utils.project_utils import _validate_directory, _run_scan


def info(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory.",
    ),
) -> None:
    """
    Display detailed project metadata.

    Shows the project path, detected languages, package managers,
    dependency files, version requirements, environment files, Docker
    configuration, and subproject directories -- all in one overview.
    """
    project_path = _validate_directory(path)

    print_banner()
    result = _run_scan(project_path)

    # ── Project overview ────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold]Project Path:[/bold] {project_path}\n"
            f"[bold]Languages:[/bold]   {', '.join(sorted(result.language_files.keys())) or 'None detected'}",
            title="[bold bright_cyan]Project Information[/bold bright_cyan]",
            border_style="bright_cyan",
            padding=(1, 2),
        )
    )
    console.print()

    # ── Languages and package managers ─────────────────────────────
    if result.language_files:
        table = Table(
            title="Language Detection",
            title_style="bold bright_cyan",
            border_style="dim",
            padding=(0, 2),
        )
        table.add_column("Language", style="bold white", min_width=15)
        table.add_column("Files", style="white")
        table.add_column("Package Manager", style="cyan")

        detections = detect_all(result.language_files)
        lang_to_detection = {d.language: d for d in detections}

        for lang, files in sorted(result.language_files.items()):
            file_list = ", ".join(p.name for p in files)
            detection = lang_to_detection.get(lang)
            package_manager = detection.package_manager if detection else "unknown"
            table.add_row(lang, file_list, package_manager)

        console.print(table)
        console.print()

    # ── Subprojects ─────────────────────────────────────────────────
    if result.subprojects:
        sub_table = Table(
            title="Subproject Directories",
            title_style="bold bright_cyan",
            border_style="dim",
            padding=(0, 2),
        )
        sub_table.add_column("Directory", style="bold white")
        sub_table.add_column("Path", style="dim")
        for sp in result.subprojects:
            sub_table.add_row(sp.name, str(sp.relative_to(project_path)))
        console.print(sub_table)
        console.print()

    # ── Environment templates ───────────────────────────────────────
    if result.env_templates:
        console.print(
            Panel(
                "\n".join(f"  [bold]{p.name}[/bold]" for p in result.env_templates),
                title="[bold cyan]Environment Templates Found[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        console.print()

    # ── Docker files ────────────────────────────────────────────────
    if result.docker_files:
        docker_info = detect_docker(project_path)
        show_docker_status(docker_info)
        console.print()

    # ── Version requirements ────────────────────────────────────────
    version_reqs = get_all_version_requirements(project_path)
    if version_reqs:
        ver_table = Table(
            title="Version Requirements",
            title_style="bold bright_cyan",
            border_style="dim",
            padding=(0, 2),
        )
        ver_table.add_column("Language", style="bold white", min_width=15)
        ver_table.add_column("Required Version", style="yellow")
        for lang, req in sorted(version_reqs.items()):
            ver_table.add_row(lang, req)
        console.print(ver_table)
        console.print()