"""
run.py -- Development server startup command.

This command starts the development server only. It does NOT install
dependencies or runtimes. For full setup, use the 'setup' command.
"""

import typer
from pathlib import Path

from ..scanner import full_scan
from ..detector import detect_all
from ..cli_utils.runtime_utils import check_runtime
from ..installer import run_install, InstallError
from ..dev_server import detect_dev_server, prompt_start_server
from ..cli_utils.docker_utils import detect_docker
from ..cli_utils.cli_utils import (
    print_banner, print_no_projects, print_runtime_missing, console
)
from ..cli_utils.project_utils import _validate_directory, _run_scan
from ..utils import RUN_COMMANDS


def run(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory.",
    ),
) -> None:
    """
    Start the development server or run the project.

    This command starts the development server only. It does NOT install
    dependencies or runtimes. For full environment setup, use 'devenv setup'.

    Examples of what this runs:
    - npm run dev (Node.js)
    - python manage.py runserver (Django)
    - go run main.go (Go)
    - rails server (Ruby on Rails)
    - docker-compose up (Docker)
    """
    project_path = _validate_directory(path)

    print_banner()

    # Try to use the enhanced dev server detection first
    try:
        dev_detection = detect_dev_server(project_path)
        if dev_detection.has_commands:
            console.print(
                f"[bold cyan]Starting development server for {project_path}...[/bold cyan]\n"
            )

            cmd = prompt_start_server(dev_detection, auto_yes=False)
            if cmd:
                console.print(f"[bold cyan]Running:[/bold cyan] {' '.join(cmd)}\n")
                try:
                    run_install(cmd, cwd=str(project_path))
                except InstallError as exc:
                    console.print(f"[bold red]Error:[/bold red] {exc}")
                    raise typer.Exit(code=1)
                return
            else:
                console.print("[yellow]No command selected. Exiting.[/yellow]")
                raise typer.Exit(code=0)

    except ImportError:
        pass

    # Fallback to legacy detection
    result = _run_scan(project_path)
    scan_results = result.language_files

    if not scan_results:
        print_no_projects()
        raise typer.Exit(code=1)

    detections = detect_all(scan_results)

    # Try to find a runnable stack
    for detection in detections:
        if detection.language == "Docker":
            # Offer Docker compose up
            docker_info = detect_docker(project_path)
            if docker_info.has_compose and docker_info.compose_installed:
                cmd = ["docker-compose", "up"]
                console.print(
                    f"[bold cyan]Starting:[/bold cyan] {' '.join(cmd)}\n"
                )
                try:
                    run_install(cmd, cwd=str(project_path))
                except InstallError as exc:
                    console.print(f"[bold red]Error:[/bold red] {exc}")
                    raise typer.Exit(code=1)
                return
            continue

        run_cmds = RUN_COMMANDS.get(detection.language)
        if not run_cmds:
            continue

        runtime = check_runtime(detection.language)
        if not runtime.installed:
            print_runtime_missing(detection.language, runtime.command)
            continue

        # Use the first available run command
        cmd = run_cmds[0]
        cmd_str = " ".join(cmd)
        console.print(f"[bold cyan]Starting:[/bold cyan] {cmd_str}\n")

        try:
            run_install(cmd, cwd=str(project_path))
        except InstallError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(code=1)
        return

    console.print("[yellow]Could not determine a run command for this project.[/yellow]")
    raise typer.Exit(code=1)