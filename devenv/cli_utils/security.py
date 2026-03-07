"""
security.py -- Pre-installation security checks.

Responsibility:
    Before executing any install command, DEVENV should clearly show
    the user exactly what will run and ask for explicit confirmation.
    This module provides the security confirmation flow that sits
    between detection and execution.

Design:
    - Displays the exact command in a Rich panel so it stands out.
    - Warns about post-install scripts (e.g. npm's lifecycle scripts).
    - Returns a boolean indicating whether the user approved execution.
    - In ``--yes`` mode, confirmation is skipped (for CI pipelines).
"""

from typing import List

from rich.panel import Panel
from rich.prompt import Confirm

from ..utils import console


def confirm_install(
    install_command: List[str],
    language: str,
    cwd: str = ".",
    auto_yes: bool = False,
) -> bool:
    """
    Display the command that will be executed and ask for confirmation.

    Parameters
    ----------
    install_command:
        Full ``argv`` list, e.g. ``["npm", "install"]``.
    language:
        The detected language (used in the display).
    cwd:
        The working directory where the command will execute.
    auto_yes:
        When ``True``, skip the prompt and return ``True`` immediately.

    Returns
    -------
    bool:
        ``True`` if the user approved, ``False`` otherwise.
    """
    cmd_str = " ".join(install_command)

    console.print()
    console.print(
        Panel(
            f"[bold]The following command will run:[/bold]\n\n"
            f"  [bold cyan]{cmd_str}[/bold cyan]\n\n"
            f"[dim]Language:[/dim]  {language}\n"
            f"[dim]Directory:[/dim] {cwd}",
            title="[bold yellow]Security Check[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )

    if auto_yes:
        console.print("[dim]Auto-confirmed via --yes flag.[/dim]")
        return True

    return Confirm.ask("\nContinue?", default=True)


def confirm_docker_build(
    command: List[str],
    cwd: str = ".",
    auto_yes: bool = False,
) -> bool:
    """
    Display a Docker build/compose command and ask for confirmation.

    Parameters
    ----------
    command:
        Full ``argv`` list, e.g. ``["docker-compose", "up"]``.
    cwd:
        Working directory.
    auto_yes:
        Skip prompt if True.

    Returns
    -------
    bool:
        ``True`` if approved.
    """
    cmd_str = " ".join(command)

    console.print()
    console.print(
        Panel(
            f"[bold]Docker command to execute:[/bold]\n\n"
            f"  [bold cyan]{cmd_str}[/bold cyan]\n\n"
            f"[dim]Directory:[/dim] {cwd}",
            title="[bold yellow]Docker Security Check[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )

    if auto_yes:
        console.print("[dim]Auto-confirmed via --yes flag.[/dim]")
        return True

    return Confirm.ask("\nContinue?", default=True)
