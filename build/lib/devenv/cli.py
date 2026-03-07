"""
cli.py -- Main Typer CLI entry point that wires everything together.

This is the orchestration layer.  It does not contain business logic
itself; instead it calls into the specialised modules:

    1. ``scanner``        -- discover dependency files
    2. ``detector``       -- resolve language + package manager
    3. ``runtime_check``  -- verify the runtime binary exists
    4. ``installer``      -- execute the install command
    5. ``security``       -- confirm commands before execution
    6. ``env_manager``    -- detect and generate .env files
    7. ``docker_tools``   -- Docker/Compose detection and management
    8. ``version_parser`` -- parse version requirements from config files
    9. ``service_detector`` -- detect required services (databases, caches)
   10. ``dev_server``     -- detect and start development servers
   11. ``project_summary`` -- generate comprehensive project reports
   12. ``multi_project``  -- handle monorepos and multi-project setups

Supported commands
------------------
``devenv scan``
    Read-only scan of the project directory.
``devenv install``
    Full pipeline: scan, detect, confirm, install.
``devenv doctor``
    Comprehensive health check for project and system.
``devenv run``
    Start the project's dev server or main process.
``devenv info``
    Display detailed project metadata.
``devenv summary``
    Quick project summary with all key information.
``devenv init``
    Legacy alias for ``install`` (preserved for backwards compatibility).

Flags
-----
``--path / -p``
    Point at a project directory other than the current working directory.
``--dry-run / -n``
    Preview the install command without executing it.
``--yes / -y``
    Skip the interactive confirmation prompt (useful for CI pipelines).
``--version / -v``
    Print the version string and exit.

Usage examples::

    devenv scan
    devenv install --path ./my-project
    devenv install --dry-run
    devenv doctor
    devenv run
    devenv info
    devenv summary
"""

from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from . import __version__
from .detector import detect_all
from .docker_tools import detect_docker, offer_docker_build, show_docker_status
from .env_manager import generate_env_file
from .installer import InstallError, run_install
from .runtime_check import RuntimeStatus, check_all_runtimes, check_runtime
from .scanner import ScanResult, full_scan, scan_directory
from .security import confirm_docker_build, confirm_install
from .utils import (
    RUN_COMMANDS,
    console,
    print_banner,
    print_detection_summary,
    print_install_error,
    print_install_start,
    print_install_success,
    print_multiple_languages,
    print_no_projects,
    print_runtime_missing,
    print_scan_start,
    print_skipped,
)
from .version_parser import get_all_version_requirements

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


# =====================================================================
# Helper: run a scan with progress spinner
# =====================================================================

def _run_scan(project_path: Path) -> ScanResult:
    """Run a full scan with a Rich progress spinner."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Scanning project directory...", total=None)
        return full_scan(str(project_path))


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


# =====================================================================
# scan command
# =====================================================================

@app.command()
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


# =====================================================================
# install command (also aliased as "init" for backwards compatibility)
# =====================================================================

def _install_logic(
    path: str,
    dry_run: bool,
    yes: bool,
) -> None:
    """
    Core install pipeline shared by ``install`` and ``init`` commands.

    1. Scan the project directory for known dependency files.
    2. Detect the programming language from those files.
    3. Determine which package manager is in use.
    4. Check that the required runtime is installed.
    5. Display a summary table for the user.
    6. Ask for confirmation via security module.
    7. Execute the dependency install command.
    8. Handle environment files and Docker.
    9. Optionally start the development server.
    """
    project_path = _validate_directory(path)

    # ── Banner ──────────────────────────────────────────────────────
    print_banner()

    # ── Check for multi-project setup ───────────────────────────────
    try:
        from .multi_project import detect_multi_project, print_multi_project_summary
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

    # ── Step 10: Offer to start dev server ──────────────────────────
    if any_installed and not dry_run:
        try:
            from .dev_server import detect_dev_server, prompt_start_server
            
            dev_detection = detect_dev_server(project_path)
            if dev_detection.has_commands:
                console.print()
                cmd = prompt_start_server(dev_detection, auto_yes=False)
                if cmd:
                    console.print()
                    try:
                        run_install(cmd, cwd=str(project_path))
                    except InstallError as exc:
                        print_install_error(str(exc))
        except ImportError:
            pass

    # ── Final exit code ─────────────────────────────────────────────
    if any_failed:
        raise typer.Exit(code=1)


@app.command()
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
    Scan the project, detect dependencies, and install them.

    This is the primary command.  It walks through the full pipeline:
    scan, detect, verify runtime, confirm, and install.
    """
    _install_logic(path, dry_run, yes)


@app.command()
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


# =====================================================================
# doctor command -- Comprehensive health check
# =====================================================================

@app.command()
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

    statuses = check_all_runtimes()

    # Also check for Git
    import shutil
    git_installed = shutil.which("git") is not None

    installed_count = 0
    for status in statuses:
        if status.installed:
            installed_count += 1
            mark = "[green]\u2713[/green]"
            version = f" [dim]({status.version})[/dim]" if status.version else ""
            console.print(f"  {mark} {status.language} installed{version}")
        else:
            mark = "[red]\u2717[/red]"
            console.print(f"  {mark} {status.language} missing")

    # Git status
    if git_installed:
        console.print(f"  [green]\u2713[/green] Git installed")
        installed_count += 1
    else:
        console.print(f"  [red]\u2717[/red] Git missing")

    console.print()
    total = len(statuses) + 1  # +1 for Git
    console.print(f"  [bold]{installed_count}/{total}[/bold] runtimes available\n")

    # ── Section 2: Project Dependencies ─────────────────────────────
    result = _run_scan(project_path)

    console.print(
        Panel(
            "[bold]Project Dependencies[/bold]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()

    if result.language_files:
        for lang, files in sorted(result.language_files.items()):
            for f in files:
                console.print(f"  [green]\u2713[/green] {f.name} detected [dim]({lang})[/dim]")
    else:
        console.print("  [yellow]No dependency files found[/yellow]")

    console.print()

    # ── Section 3: Services Detection ───────────────────────────────
    try:
        from .service_detector import detect_services, get_service_summary

        service_result = detect_services(project_path)

        console.print(
            Panel(
                "[bold]Services[/bold]",
                border_style="bright_cyan",
                padding=(0, 2),
            )
        )
        console.print()

        if service_result.has_services:
            for service in service_result.services:
                console.print(
                    f"  [green]\u2713[/green] {service.name} required "
                    f"[dim]({service.detected_via})[/dim]"
                )
            console.print()
            console.print(f"  [bold cyan]{get_service_summary(service_result)}[/bold cyan]")
        else:
            console.print("  [dim]No external services detected[/dim]")

        console.print()
    except ImportError:
        pass

    # ── Section 4: Docker Status ────────────────────────────────────
    docker_info = detect_docker(project_path)

    console.print(
        Panel(
            "[bold]Docker[/bold]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()

    if docker_info.has_dockerfile:
        console.print(f"  [green]\u2713[/green] Dockerfile found")
    else:
        console.print(f"  [dim]-[/dim] No Dockerfile")

    if docker_info.has_compose:
        console.print(f"  [green]\u2713[/green] docker-compose.yml found")
    else:
        console.print(f"  [dim]-[/dim] No docker-compose.yml")

    console.print()

    if docker_info.docker_installed:
        console.print(f"  [green]\u2713[/green] Docker is installed")
    else:
        console.print(f"  [red]\u2717[/red] Docker is NOT installed")

    if docker_info.compose_installed:
        console.print(f"  [green]\u2713[/green] Docker Compose is available")
    elif docker_info.has_compose:
        console.print(f"  [red]\u2717[/red] Docker Compose is NOT installed")

    console.print()

    # ── Section 5: Version Requirements ─────────────────────────────
    version_reqs = get_all_version_requirements(project_path)
    if version_reqs:
        console.print(
            Panel(
                "[bold]Version Requirements[/bold]",
                border_style="bright_cyan",
                padding=(0, 2),
            )
        )
        console.print()

        for lang, req in sorted(version_reqs.items()):
            status = next(
                (s for s in statuses if s.language == lang), None
            )
            if status and status.installed:
                console.print(
                    f"  [green]\u2713[/green] {lang}: requires {req} "
                    f"[dim](have {status.version or 'installed'})[/dim]"
                )
            else:
                console.print(
                    f"  [red]\u2717[/red] {lang}: requires {req} [red](MISSING)[/red]"
                )

        console.print()

    # ── Final Summary ───────────────────────────────────────────────
    console.print(
        Panel(
            "[bold green]Health check complete.[/bold green]",
            border_style="green",
            padding=(0, 2),
        )
    )


# =====================================================================
# run command
# =====================================================================

@app.command()
def run(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory.",
    ),
) -> None:
    """
    Start the project's dev server or main process.

    Detects the project type and runs the appropriate start command.
    For Node.js projects this is typically ``npm run dev`` or ``npm start``.
    For Python projects it tries ``python manage.py runserver`` etc.
    """
    project_path = _validate_directory(path)

    print_banner()

    # ── Use enhanced dev server detection ───────────────────────────
    try:
        from .dev_server import detect_dev_server

        detection = detect_dev_server(project_path)

        if detection.has_commands:
            recommended = detection.recommended
            assert recommended is not None

            console.print(f"[bold cyan]Detected:[/bold cyan] {recommended.framework}")
            console.print(f"[bold cyan]Command:[/bold cyan]  {recommended.command_str}")
            console.print(f"[dim]{recommended.description}[/dim]")
            console.print()

            proceed = Confirm.ask(
                "Start the development server?",
                default=True,
            )

            if proceed:
                console.print()
                try:
                    run_install(recommended.command, cwd=str(project_path))
                except InstallError as exc:
                    print_install_error(str(exc))
                return

            console.print("[dim]Cancelled.[/dim]")
            return

    except ImportError:
        pass

    # ── Fallback to legacy detection ────────────────────────────────
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
                    print_install_error(str(exc))
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
            print_install_error(str(exc))
        return

    console.print("[yellow]Could not determine a run command for this project.[/yellow]")
    raise typer.Exit(code=1)


# =====================================================================
# info command
# =====================================================================

@app.command()
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

    # ── Detailed detection table ────────────────────────────────────
    if result.language_files:
        detections = detect_all(result.language_files)

        table = Table(
            title="Detected Stacks",
            title_style="bold bright_cyan",
            border_style="bright_cyan",
            padding=(0, 2),
        )
        table.add_column("Language", style="bold white", min_width=12)
        table.add_column("Manager", style="white", min_width=12)
        table.add_column("Dependency File", style="dim")
        table.add_column("Install Command", style="cyan")
        table.add_column("Runtime", style="white")

        for d in detections:
            runtime = check_runtime(d.language)
            if runtime.installed:
                rt_str = f"[green]{runtime.version or 'installed'}[/green]"
            else:
                rt_str = "[red]not found[/red]"

            cmd_str = " ".join(d.install_command) if d.install_command else "[dim]n/a[/dim]"
            table.add_row(
                d.language,
                d.package_manager,
                d.dependency_file,
                cmd_str,
                rt_str,
            )

        console.print(table)
        console.print()

    # ── All dependency files ────────────────────────────────────────
    if result.language_files:
        files_table = Table(
            title="All Dependency Files",
            title_style="bold bright_cyan",
            border_style="dim",
            padding=(0, 2),
        )
        files_table.add_column("File", style="bold white")
        files_table.add_column("Language", style="white")
        files_table.add_column("Path", style="dim")

        for lang, files in sorted(result.language_files.items()):
            for f in files:
                files_table.add_row(
                    f.name,
                    lang,
                    str(f.relative_to(project_path)),
                )

        console.print(files_table)
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

    # ── Environment files ───────────────────────────────────────────
    if result.env_templates:
        env_list = "\n".join(
            f"  [bold]{p.name}[/bold]  [dim]{p.relative_to(project_path)}[/dim]"
            for p in result.env_templates
        )
        console.print(
            Panel(
                env_list,
                title="[bold cyan]Environment Templates[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        console.print()

    # ── Docker ──────────────────────────────────────────────────────
    docker_info = detect_docker(project_path)
    if docker_info.has_any:
        show_docker_status(docker_info)
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


# =====================================================================
# summary command -- Quick project summary
# =====================================================================

@app.command()
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
        from .project_summary import generate_project_summary, print_project_summary

        summary_data = generate_project_summary(project_path)
        print_project_summary(summary_data)

    except ImportError:
        # Fallback to basic info if module not available
        console.print("[yellow]Summary module not available. Use 'devenv info' instead.[/yellow]")
        raise typer.Exit(code=1)


# Allow ``python devenv/cli.py`` invocation during development.
if __name__ == "__main__":
    app()
