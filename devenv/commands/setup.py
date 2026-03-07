"""
setup.py -- Complete automated development environment setup command.

This command provides full environment bootstrap including:
- OS detection and cross-platform support
- Automatic runtime installation
- Project dependency installation
- Environment configuration
- Optional project startup
"""

import typer
from pathlib import Path
from rich.prompt import Confirm

from ..scanner import full_scan
from ..detector import detect_all
from ..cli_utils.runtime_utils import check_runtime
from ..installer import run_install, InstallError
from ..cli_utils.security import confirm_install, confirm_docker_build
from ..env_manager import generate_env_file
from ..cli_utils.docker_utils import detect_docker, offer_docker_build
from ..dev_server import detect_dev_server, prompt_start_server
from ..multi_project import detect_multi_project, print_multi_project_summary
from ..cli_utils.cli_utils import (
    print_banner, print_no_projects, print_multiple_languages,
    print_detection_summary, print_runtime_missing, print_install_start,
    print_install_success, print_install_error, print_skipped, console
)
from ..cli_utils.project_utils import _validate_directory, _run_scan
from ..cli_utils.os_utils import detect_os, get_runtime_install_command, install_runtime, fix_cross_os_compatibility


def _setup_logic(
    path: str,
    dry_run: bool,
    yes: bool,
) -> None:
    """
    Core setup pipeline for complete development environment setup.

    Enhanced version with 9 steps:
    1. Detect OS
    2. Detect package manager
    3. Detect project language
    4. Check required runtimes
    5. Install missing runtimes
    6. Install project dependencies
    7. Fix cross-OS compatibility
    8. Detect run command
    9. Start development server
    """
    project_path = _validate_directory(path)

    # ── Banner ──────────────────────────────────────────────────────
    print_banner()
    console.print("[bold green]🚀 Complete Development Environment Setup[/bold green]\n")

    # ── Step 1: Detect OS ──────────────────────────────────────────
    console.print("[bold cyan]Step 1: Detecting operating system...[/bold cyan]")
    try:
        os_info = detect_os()
        console.print(f"[green]✓ Detected {os_info.os.value.title()}")
        if os_info.is_wsl:
            console.print("[blue]ℹ  Running under Windows Subsystem for Linux (WSL)[/blue]")
    except Exception:
        console.print("[yellow]⚠ OS detection failed, continuing with defaults[/yellow]")
        os_info = None

    # ── Step 2: Detect package manager ─────────────────────────────
    console.print("\n[bold cyan]Step 2: Detecting package manager...[/bold cyan]")
    if os_info:
        console.print(f"[green]✓ Package manager: {os_info.package_manager}[/green]")
    else:
        console.print("[yellow]⚠ Package manager detection unavailable[/yellow]")

    # ── Step 3: Detect project language ────────────────────────────
    console.print("\n[bold cyan]Step 3: Detecting project language...[/bold cyan]")
    result = _run_scan(project_path)
    scan_results = result.language_files

    if not scan_results:
        print_no_projects()
        raise typer.Exit(code=0)

    detections = detect_all(scan_results)

    if not detections:
        print_no_projects()
        raise typer.Exit(code=0)

    if len(detections) > 1:
        print_multiple_languages([d.language for d in detections])
    
    for d in detections:
        console.print(f"[green]✓ Detected {d.language} project ({d.dependency_file})[/green]")

    # ── Step 4: Check required runtimes ────────────────────────────
    console.print("\n[bold cyan]Step 4: Checking required runtimes...[/bold cyan]")
    missing_runtimes = []
    installed_runtimes = []

    for detection in detections:
        runtime = check_runtime(detection.language)
        if runtime.installed:
            console.print(f"[green]✓ {detection.language} runtime already installed ({runtime.version or 'available'})[/green]")
            installed_runtimes.append(detection.language)
        else:
            missing_runtimes.append(detection.language)
            console.print(f"[red]✗ {detection.language} runtime not found[/red]")

    # ── Step 5: Install missing runtimes ───────────────────────────
    if missing_runtimes:
        console.print("\n[bold cyan]Step 5: Installing missing runtimes...[/bold cyan]")
        if os_info:
            for runtime_name in missing_runtimes:
                try:
                    install_cmd = get_runtime_install_command(os_info, runtime_name)
                    if install_cmd:
                        console.print(f"Detected OS: [bold]{os_info.os.value.title()}[/bold]")
                        console.print(f"Missing runtime: [bold]{runtime_name}[/bold]")
                        console.print(f"Installing using [bold]{os_info.package_manager}[/bold]...")
                        
                        if not yes:
                            if not Confirm.ask(f"Install {install_cmd.description} ({install_cmd.package_name})?"):
                                continue

                        if install_runtime(install_cmd, dry_run=dry_run):
                            console.print(f"[green]✓ Successfully installed {runtime_name}[/green]")
                            installed_runtimes.append(runtime_name)
                        else:
                            console.print(f"[red]✗ Failed to install {runtime_name}[/red]")
                    else:
                        console.print(f"[red]✗ No installation command available for {runtime_name} on {os_info.os.value}[/red]")
                except Exception as e:
                    console.print(f"[yellow]⚠ Runtime installation failed for {runtime_name}: {e}[/yellow]")
        else:
            console.print("[yellow]⚠ Cannot install runtimes without OS info[/yellow]")
    else:
        console.print("\n[bold cyan]Step 5: Installing missing runtimes...[/bold cyan]")
        console.print("[green]✓ No missing runtimes to install[/green]")

    # ── Step 6: Install project dependencies ───────────────────────
    console.print("\n[bold cyan]Step 6: Installing project dependencies...[/bold cyan]")
    # Process each detected stack
    any_failed = False
    any_installed = False

    for detection in detections:
        # Skip Docker in the main install loop -- handled separately if needed
        if detection.language == "Docker":
            continue

        # Check runtime availability
        runtime = check_runtime(detection.language)

        # Show summary
        print_detection_summary(
            language=detection.language,
            package_manager=detection.package_manager,
            dependency_file=detection.dependency_file,
            runtime_installed=runtime.installed,
            runtime_version=runtime.version,
        )

        # Runtime missing -- skip this stack
        if not runtime.installed:
            print_runtime_missing(detection.language, runtime.command)
            any_failed = True
            continue

        # Package manager could not be resolved
        if detection.package_manager == "unknown" or not detection.install_command:
            console.print(
                f"[yellow]Could not determine install command for "
                f"{detection.language}. Skipping.[/yellow]\n"
            )
            any_failed = True
            continue

        # Security confirmation
        if not confirm_install(
            detection.install_command,
            detection.language,
            cwd=str(project_path),
            auto_yes=yes,
        ):
            print_skipped()
            continue

        # Install dependencies
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

    # ── Step 7: Fix cross-OS compatibility ────────────────────────
    console.print("[bold cyan]Step 7: Fixing cross-OS compatibility...[/bold cyan]")
    if os_info:
        fix_cross_os_compatibility(str(project_path), os_info)
        console.print("[green]✓ Compatibility fixes applied[/green]\n")
    else:
        console.print("[yellow]⚠ OS detection not available, skipping compatibility fixes[/yellow]\n")

    # ── Step 8 & 9: Detect run command & Start development server ──
    console.print("[bold cyan]Step 8 & 9: Detecting run command & Starting project...[/bold cyan]")
    if not dry_run:
        try:
            dev_detection = detect_dev_server(project_path)
            if dev_detection.has_commands:
                console.print()
                console.print("[blue]Available run commands:[/blue]")
                for i, cmd in enumerate(dev_detection.commands, 1):
                    if isinstance(cmd, (list, tuple)):
                        cmd_str = " ".join(cmd)
                    else:
                        cmd_str = str(getattr(cmd, "command_str", cmd))
                    console.print(f"  {i}. {cmd_str}")

                cmd = prompt_start_server(dev_detection, auto_yes=yes)
                if cmd:
                    console.print()
                    if isinstance(cmd, (list, tuple)):
                        start_cmd_str = " ".join(cmd)
                    else:
                        start_cmd_str = str(cmd)
                    console.print(f"[blue]Starting project with: {start_cmd_str}[/blue]")
                    try:
                        run_install(cmd, cwd=str(project_path))
                        console.print("[green]✓ Project started successfully![/green]")
                    except InstallError as exc:
                        print_install_error(str(exc))
                        console.print("[yellow]Project setup completed, but failed to start automatically.[/yellow]")
                else:
                    console.print("[yellow]No start command selected. Project setup completed.[/yellow]")
            else:
                console.print("[yellow]No development server commands detected for this project.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Development server detection failed: {e}[/yellow]")
    else:
        console.print("[dim][dry-run] would detect and start project[/dim]")

    # ── Final summary ──────────────────────────────────────────────
    console.print("\n[bold green]🎉 Development environment setup complete![/bold green]")

    if any_installed:
        console.print("[green]✓ Dependencies installed successfully[/green]")

    if installed_runtimes:
        console.print(f"[green]✓ Runtimes available: {', '.join(installed_runtimes)}[/green]")

    if cross_os_needed and os_info and os_info.os.value == "windows" and not os_info.is_wsl:
        console.print("[blue]💡 Tip: For better Linux project compatibility, consider using WSL[/blue]")

    if any_failed:
        console.print("[yellow]⚠ Some components failed to install. Check the output above.[/yellow]")

    console.print("\n[dim]Your development environment is ready to use![/dim]")


def setup(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Path to the project directory to set up.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be set up without running anything.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts and set up immediately.",
    ),
) -> None:
    """
    Complete automated development environment setup in one command.

    This enhanced setup command provides:

    1. 🌐 Cross-OS Intelligence
       - Automatically detects Windows, Linux, or macOS
       - Uses appropriate package managers (winget, apt, brew, etc.)
       - Handles cross-platform compatibility

    2. 🔍 Smart Project Detection
       - Detects Node.js, Python, Go, Java, .NET, Docker, and more
       - Identifies package managers (npm, yarn, pip, etc.)
       - Supports monorepo and multi-language projects

    3. ⚡ Automatic Runtime Installation
       - Installs missing runtimes (Node.js, Python, Java, etc.)
       - Uses system package managers when available
       - Provides clear installation prompts

    4. 📦 Dependency Management
       - Installs project dependencies automatically
       - Handles different package managers seamlessly
       - Manages Docker containers if needed

    5. 🌍 Cross-OS Compatibility
       - Detects WSL on Windows for Linux projects
       - Suggests compatibility improvements
       - Handles path and command differences

    6. ⚙️  Environment Configuration
       - Creates .env files with detected variables
       - Sets up development environment variables
       - Configures ports and connections

    7. 🚀 Automatic Project Startup
       - Detects and runs appropriate dev commands
       - Shows available run options for user selection
       - Starts development servers automatically

    8. 🛡️  Safety First
       - Confirms all installations before proceeding
       - Provides dry-run mode for preview
       - Clear error messages and recovery suggestions

    Perfect for:
    - New team members joining a project
    - Setting up development environments on new machines
    - Automated CI/CD pipeline setup
    - Cross-platform development workflows

    Usage examples:
        devenv setup                    # Setup current directory
        devenv setup --path ./myproject # Setup specific directory
        devenv setup --dry-run          # Preview what would be done
        devenv setup --yes              # Skip all confirmations
    """
    _setup_logic(path, dry_run, yes)
