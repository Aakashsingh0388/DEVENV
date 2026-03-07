"""
docker_tools.py -- Docker and Docker Compose detection and management.

Responsibility:
    Detect Docker-related configuration files (``Dockerfile``,
    ``docker-compose.yml``, ``docker-compose.yaml``) in the project
    directory and offer to build/run containers.

Design:
    - Detection is file-based: presence of Docker files triggers the
      Docker workflow.
    - Runtime availability of ``docker`` and ``docker-compose`` (or
      ``docker compose``) is verified before offering build/run.
    - All execution goes through the installer module for consistency.
    - Security confirmation is handled by the security module.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from rich.panel import Panel
from rich.prompt import Confirm

from .utils import console


@dataclass
class DockerInfo:
    """
    Information about Docker configuration in a project.

    Attributes
    ----------
    has_dockerfile:
        ``True`` if a ``Dockerfile`` is present.
    has_compose:
        ``True`` if ``docker-compose.yml`` or ``docker-compose.yaml`` exists.
    dockerfile_paths:
        List of Dockerfile paths found.
    compose_paths:
        List of docker-compose file paths found.
    docker_installed:
        ``True`` if the ``docker`` binary is on PATH.
    compose_installed:
        ``True`` if ``docker-compose`` or ``docker compose`` is available.
    """
    has_dockerfile: bool = False
    has_compose: bool = False
    dockerfile_paths: List[Path] = None  # type: ignore[assignment]
    compose_paths: List[Path] = None  # type: ignore[assignment]
    docker_installed: bool = False
    compose_installed: bool = False

    def __post_init__(self) -> None:
        if self.dockerfile_paths is None:
            self.dockerfile_paths = []
        if self.compose_paths is None:
            self.compose_paths = []

    @property
    def has_any(self) -> bool:
        """True if any Docker configuration is present."""
        return self.has_dockerfile or self.has_compose


def detect_docker(project_root: Path) -> DockerInfo:
    """
    Scan *project_root* for Docker configuration files and check
    whether Docker/Compose runtimes are available.
    """
    info = DockerInfo()

    # Check for Dockerfiles
    dockerfile = project_root / "Dockerfile"
    if dockerfile.is_file():
        info.has_dockerfile = True
        info.dockerfile_paths.append(dockerfile)

    # Check for docker-compose files
    for name in ("docker-compose.yml", "docker-compose.yaml"):
        compose_file = project_root / name
        if compose_file.is_file():
            info.has_compose = True
            info.compose_paths.append(compose_file)

    # Check runtime availability
    info.docker_installed = shutil.which("docker") is not None
    info.compose_installed = (
        shutil.which("docker-compose") is not None
        or _docker_compose_v2_available()
    )

    return info


def _docker_compose_v2_available() -> bool:
    """Check if ``docker compose`` (v2 plugin) is available."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def show_docker_status(info: DockerInfo) -> None:
    """
    Display Docker detection results in a Rich panel.
    """
    lines = ["[bold]This project contains Docker configuration.[/bold]\n"]

    if info.has_dockerfile:
        lines.append("[green]Dockerfile[/green] detected")
    if info.has_compose:
        for p in info.compose_paths:
            lines.append(f"[green]{p.name}[/green] detected")

    lines.append("")

    if info.docker_installed:
        lines.append("[green]docker[/green] is installed")
    else:
        lines.append("[red]docker[/red] is NOT installed")

    if info.compose_installed:
        lines.append("[green]docker-compose[/green] is available")
    elif info.has_compose:
        lines.append("[red]docker-compose[/red] is NOT installed")

    console.print()
    console.print(
        Panel(
            "\n".join(lines),
            title="[bold cyan]Docker Configuration[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def offer_docker_build(
    info: DockerInfo,
    project_root: Path,
    auto_yes: bool = False,
) -> Optional[List[str]]:
    """
    If Docker is configured and available, ask the user if they want
    to build/run containers.

    Returns the command that should be executed, or ``None`` if the
    user declined or Docker is not available.
    """
    if not info.has_any:
        return None

    show_docker_status(info)

    # Determine what command to offer
    if info.has_compose and info.compose_installed:
        command = ["docker-compose", "up", "--build"]
        label = "docker-compose up --build"
    elif info.has_dockerfile and info.docker_installed:
        command = ["docker", "build", "."]
        label = "docker build ."
    else:
        if not info.docker_installed:
            console.print(
                "\n[yellow]Docker is not installed. Skipping container setup.[/yellow]"
            )
        return None

    console.print()
    if not auto_yes:
        proceed = Confirm.ask(
            "Would you like to build and run containers?",
            default=False,
        )
        if not proceed:
            console.print("[dim]Skipped Docker build.[/dim]")
            return None

    return command
