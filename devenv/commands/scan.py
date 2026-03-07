"""
scan.py -- Read-only project analysis command.

This command performs a comprehensive scan of the project directory
to detect languages, dependency files, environment templates, Docker
configuration, and subproject directories without making any changes.
"""

import typer
from pathlib import Path
from rich.table import Table
from rich.panel import Panel

from ..scanner import full_scan
from ..detector import detect_all
from ..cli_utils.runtime_utils import check_runtime
from ..cli_utils.docker_utils import detect_docker, show_docker_status
from ..version_parser import get_all_version_requirements
from ..cli_utils.cli_utils import print_banner, print_no_projects, console
from ..cli_utils.project_utils import _validate_directory, _run_scan


def scan(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory to analyse.",
    ),
) -> None:
    """
    Scan the project and display a report of what was found.

    This is a read-only operation -- nothing is installed or modified.
    It shows detected languages, dependency files, environment templates,
    Docker configuration, and subproject directories.
    """
    project_path = _validate_directory(path)

    print_banner()
    result = _run_scan(project_path)

    # ── Languages table ─────────────────────────────────────────────
    if result.language_files:
        table = Table(
            title="Detected Projects",
            title_style="bold bright_cyan",
            border_style="bright_cyan",
            padding=(0, 2),
        )
        table.add_column("Language", style="bold white", min_width=15)
        table.add_column("Files", style="white")
        table.add_column("Status", style="white")

        for lang, files in sorted(result.language_files.items()):
            file_list = ", ".join(p.name for p in files)
            status = check_runtime(lang)
            if status.installed:
                status_str = f"[green]{status.version or 'installed'}[/green]"
            else:
                status_str = f"[red]{lang} is required but not installed[/red]"
            table.add_row(lang, file_list, status_str)

        console.print(table)
        console.print()
    else:
        print_no_projects()

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
        ver_table.add_column("Required", style="yellow")
        for lang, req in sorted(version_reqs.items()):
            ver_table.add_row(lang, req)
        console.print(ver_table)
        console.print()