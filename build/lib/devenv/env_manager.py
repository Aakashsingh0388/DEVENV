"""
env_manager.py -- Environment file detection and generation.

Responsibility:
    Detect ``.env.example``, ``.env.sample``, and similar template files
    in the project directory.  When found, offer to copy the template to
    ``.env`` so the developer has a ready-to-use environment file.

Design:
    - Only copies if ``.env`` does not already exist (never overwrites).
    - Asks the user for confirmation before creating the file.
    - Optionally shows the contents of the template for review.
"""

import shutil
from pathlib import Path
from typing import List, Optional

from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from .utils import ENV_TEMPLATES, console


def find_env_templates(project_root: Path) -> List[Path]:
    """
    Search for environment template files in *project_root*.

    Returns a list of Paths to found template files, ordered by
    preference (first match is the most commonly used name).
    """
    found: List[Path] = []
    for template_name in ENV_TEMPLATES:
        candidate = project_root / template_name
        if candidate.is_file():
            found.append(candidate)
    return found


def show_env_template(template_path: Path) -> None:
    """
    Display the contents of an environment template using Rich syntax
    highlighting.
    """
    try:
        content = template_path.read_text(encoding="utf-8")
        console.print()
        console.print(
            Panel(
                Syntax(content, "bash", theme="monokai", line_numbers=True),
                title=f"[bold]{template_path.name}[/bold]",
                border_style="dim",
            )
        )
    except OSError:
        console.print(f"[yellow]Could not read {template_path.name}[/yellow]")


def generate_env_file(
    project_root: Path,
    auto_yes: bool = False,
) -> Optional[Path]:
    """
    Detect env templates and offer to generate a ``.env`` file.

    Parameters
    ----------
    project_root:
        The project directory to scan.
    auto_yes:
        Skip confirmation prompts if True.

    Returns
    -------
    Path or None:
        The path to the generated ``.env`` file, or ``None`` if no
        template was found or the user declined.
    """
    env_file = project_root / ".env"

    # Don't overwrite an existing .env
    if env_file.is_file():
        console.print(
            "[dim].env file already exists -- skipping generation.[/dim]"
        )
        return None

    templates = find_env_templates(project_root)
    if not templates:
        return None

    # Use the first (highest-priority) template found.
    template = templates[0]

    console.print()
    console.print(
        Panel(
            f"Found environment template: [bold]{template.name}[/bold]\n\n"
            "This file contains configuration variables your project needs.",
            title="[bold cyan]Environment File Detected[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not auto_yes:
        # Show template contents for review
        show_env_template(template)

        proceed = Confirm.ask(
            "\nDo you want to generate a .env file from this template?",
            default=True,
        )
        if not proceed:
            console.print("[yellow]Skipped .env generation.[/yellow]")
            return None

    # Copy the template to .env
    try:
        shutil.copy2(str(template), str(env_file))
        console.print(
            f"[bold green]Created .env from {template.name}[/bold green]"
        )
        console.print(
            "[dim]Remember to fill in the actual values before running "
            "the project.[/dim]"
        )
        return env_file
    except OSError as exc:
        console.print(
            f"[bold red]Failed to create .env:[/bold red] {exc}"
        )
        return None
