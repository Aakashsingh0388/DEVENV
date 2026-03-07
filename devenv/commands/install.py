"""
install.py -- Project dependency installation command.

This command installs project dependencies only. It does NOT install
system runtimes like Node.js, Python, or Docker. For full environment
setup including runtime installation, use the 'setup' command.
"""

import typer
from pathlib import Path

from ..scanner import full_scan
from ..detector import detect_all
from ..cli_utils.runtime_utils import check_runtime
from ..installer import run_install, InstallError
from ..cli_utils.security import confirm_install, confirm_docker_build
from ..env_manager import generate_env_file
from ..cli_utils.docker_utils import detect_docker, offer_docker_build
from ..multi_project import detect_multi_project, print_multi_project_summary
from ..cli_utils.cli_utils import (
    print_banner, print_no_projects, print_multiple_languages,
    print_detection_summary, print_runtime_missing, print_install_start,
    print_install_success, print_install_error, print_skipped, console
)
from ..cli_utils.project_utils import _validate_directory, _run_scan


def _install_logic(
    path: str,
    dry_run: bool,
    yes: bool,
) -> None:
    """
    Core install pipeline for dependency installation.

    This installs project dependencies only - NOT system runtimes.
    For full environment setup, use the setup command.

    1. Scan the project directory for known dependency files.
    2. Detect the programming language from those files.
    3. Determine which package manager is in use.
    4. Check that the required runtime is installed.
    5. Display a summary table for the user.
    6. Ask for confirmation via security module.
    7. Execute the dependency install command.
    8. Handle environment files and Docker.
    """
    project_path = _validate_directory(path)

    # ── Banner ──────────────────────────────────────────────────────
    print_banner()

    # ── Check for multi-project setup ───────────────────────────────
    try:
        multi_result = detect_multi_project(project_path)
        if multi_result.has_multiple_projects:
            print_multi_project_summary(multi_result)
    except ImportError:
        pass

    # ── Step 1: Scan the project directory ──────────────────────────
    result = _run_scan(project_path)
    scan_results = result.language_files

    if not scan_results:
        print_no_projects()
        raise typer.Exit(code=0)

    # ── Step 2 & 3: Detect language + package manager ───────────────
    detections = detect_all(scan_results)

    if not detections:
        print_no_projects()
        raise typer.Exit(code=0)

    # When more than one language is detected (polyglot projects)
    # we process each stack independently and inform the user.
    if len(detections) > 1:
        print_multiple_languages([d.language for d in detections])

    # ── Process each detected stack ─────────────────────────────────
    any_failed = False
    any_installed = False

    for detection in detections:
        # Skip Docker in the main install loop -- handled separately
        if detection.language == "Docker":
            continue

        # ── Step 4: Check runtime availability ──────────────────────
        runtime = check_runtime(detection.language)

        # ── Step 5: Show summary ────────────────────────────────────
        print_detection_summary(
            language=detection.language,
            package_manager=detection.package_manager,
            dependency_file=detection.dependency_file,
            runtime_installed=runtime.installed,
            runtime_version=runtime.version,
        )

        # Runtime missing -- warn and skip this stack.
        if not runtime.installed:
            print_runtime_missing(detection.language, runtime.command)
            any_failed = True
            continue

        # Package manager could not be resolved.
        if detection.package_manager == "unknown" or not detection.install_command:
            console.print(
                f"[yellow]Could not determine install command for "
                f"{detection.language}. Skipping.[/yellow]\n"
            )
            any_failed = True
            continue

        # ── Step 6: Security confirmation ───────────────────────────
        if not confirm_install(
            detection.install_command,
            detection.language,
            cwd=str(project_path),
            auto_yes=yes,
        ):
            print_skipped()
            continue

        # ── Step 7: Install dependencies ────────────────────────────
        print_install_start()

        try:
            run_install(
                detection.install_command,
                cwd=str(project_path),
                dry_run=dry_run,
            )
            print_install_success()
            any_installed = True
        except InstallError as exc:
            print_install_error(str(exc))
            any_failed = True

        console.print()  # visual spacing between stacks

    # ── Step 8: Environment file handling ───────────────────────────
    generate_env_file(project_path, auto_yes=yes)

    # ── Step 9: Docker handling ─────────────────────────────────────
    docker_info = detect_docker(project_path)
    if docker_info.has_any:
        docker_cmd = offer_docker_build(
            docker_info,
            project_path,
            auto_yes=yes,
        )
        if docker_cmd:
            if confirm_docker_build(docker_cmd, str(project_path), auto_yes=yes):
                try:
                    run_install(
                        docker_cmd,
                        cwd=str(project_path),
                        dry_run=dry_run,
                    )
                    console.print(
                        "[bold green]Docker build completed.[/bold green]"
                    )
                except InstallError as exc:
                    print_install_error(str(exc))
                    any_failed = True

    console.print("[green]✓ Dependencies installed[/green]\n")


def install(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory to analyse.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be installed without running anything.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt and install immediately.",
    ),
) -> None:
    """
    Scan, detect, and install project dependencies.

    This command installs project dependencies only. It does NOT install
    system runtimes like Node.js, Python, or Docker. For full environment
    setup including runtime installation, use 'devenv setup'.

    Examples of what this installs:
    - npm install (Node.js)
    - pip install -r requirements.txt (Python)
    - go mod download (Go)
    - bundle install (Ruby)
    """
    _install_logic(path, dry_run, yes)


def init(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory to analyse.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be installed without running anything.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt and install immediately.",
    ),
) -> None:
    """
    [Legacy] Alias for 'install'. Scan, detect, and install dependencies.
    """
    _install_logic(path, dry_run, yes)