"""
project_summary.py -- Smart project summary generation.

Responsibility:
    After scanning a project, generate a comprehensive summary that
    includes all relevant information about the project's technology
    stack, dependencies, services, and configuration.

This module combines data from multiple sources:
    - Scanner results (languages, files, subprojects)
    - Detector results (package managers, install commands)
    - Runtime checks (installed versions)
    - Service detection (databases, caches, queues)
    - Docker configuration
    - Version requirements

The summary is formatted for clear terminal output using Rich.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .detector import DetectionResult, detect_all
from .docker_tools import DockerInfo, detect_docker
from .runtime_check import RuntimeStatus, check_runtime
from .scanner import ScanResult, full_scan
from .service_detector import ServiceDetectionResult, detect_services
from .utils import console
from .version_parser import get_all_version_requirements


@dataclass
class FrameworkInfo:
    """
    Information about a detected framework.

    Attributes
    ----------
    name:
        Framework name (e.g., "Next.js", "Django").
    version:
        Detected version if available.
    language:
        The programming language it's built on.
    """
    name: str
    version: Optional[str] = None
    language: str = "Unknown"


@dataclass
class ProjectSummary:
    """
    Complete summary of a project's technology stack.

    This is the main data structure produced by the analysis.
    """
    root_path: Path
    
    # Language and framework
    primary_language: str = "Unknown"
    languages: Set[str] = field(default_factory=set)
    framework: Optional[FrameworkInfo] = None
    
    # Runtime
    runtime_version: Optional[str] = None
    runtime_installed: bool = False
    
    # Package management
    package_manager: str = "Unknown"
    dependency_count: int = 0
    
    # Services
    services: List[str] = field(default_factory=list)
    
    # Docker
    has_dockerfile: bool = False
    has_docker_compose: bool = False
    docker_installed: bool = False
    
    # Project structure
    is_monorepo: bool = False
    subprojects: List[str] = field(default_factory=list)
    
    # Files
    env_files: List[str] = field(default_factory=list)
    
    # Version requirements
    version_requirements: Dict[str, str] = field(default_factory=dict)


def _detect_framework(project_root: Path, language: str) -> Optional[FrameworkInfo]:
    """
    Detect the framework being used for a given language.
    """
    if language == "Node.js":
        package_json = project_root / "package.json"
        if package_json.is_file():
            try:
                content = package_json.read_text(encoding="utf-8", errors="ignore")
                
                # Framework detection patterns
                frameworks = [
                    ("next", "Next.js"),
                    ("nuxt", "Nuxt"),
                    ("gatsby", "Gatsby"),
                    ("@angular/core", "Angular"),
                    ("vue", "Vue.js"),
                    ("react", "React"),
                    ("svelte", "Svelte"),
                    ("@nestjs/core", "NestJS"),
                    ("express", "Express"),
                    ("fastify", "Fastify"),
                    ("koa", "Koa"),
                    ("hapi", "Hapi"),
                    ("@remix-run/node", "Remix"),
                    ("astro", "Astro"),
                    ("solid-js", "SolidJS"),
                ]
                
                for pkg, framework_name in frameworks:
                    if f'"{pkg}"' in content:
                        # Try to extract version
                        version_match = re.search(
                            rf'"{pkg}":\s*"([^"]+)"',
                            content
                        )
                        version = version_match.group(1) if version_match else None
                        return FrameworkInfo(
                            name=framework_name,
                            version=version,
                            language="Node.js",
                        )
            except (OSError, IOError):
                pass

    elif language == "Python":
        # Check for Django
        if (project_root / "manage.py").exists():
            return FrameworkInfo(name="Django", language="Python")
        
        # Check requirements or pyproject.toml for frameworks
        req_files = [
            project_root / "requirements.txt",
            project_root / "pyproject.toml",
        ]
        
        frameworks = [
            ("fastapi", "FastAPI"),
            ("flask", "Flask"),
            ("django", "Django"),
            ("starlette", "Starlette"),
            ("tornado", "Tornado"),
            ("pyramid", "Pyramid"),
            ("falcon", "Falcon"),
            ("streamlit", "Streamlit"),
        ]
        
        for req_file in req_files:
            if req_file.is_file():
                try:
                    content = req_file.read_text(encoding="utf-8", errors="ignore").lower()
                    for pkg, framework_name in frameworks:
                        if pkg in content:
                            return FrameworkInfo(name=framework_name, language="Python")
                except (OSError, IOError):
                    pass

    elif language == "Ruby":
        gemfile = project_root / "Gemfile"
        if gemfile.is_file():
            try:
                content = gemfile.read_text(encoding="utf-8", errors="ignore").lower()
                if "rails" in content:
                    return FrameworkInfo(name="Ruby on Rails", language="Ruby")
                elif "sinatra" in content:
                    return FrameworkInfo(name="Sinatra", language="Ruby")
            except (OSError, IOError):
                pass

    elif language == "PHP":
        if (project_root / "artisan").exists():
            return FrameworkInfo(name="Laravel", language="PHP")
        if (project_root / "bin" / "console").exists():
            return FrameworkInfo(name="Symfony", language="PHP")

    elif language == "Go":
        go_mod = project_root / "go.mod"
        if go_mod.is_file():
            try:
                content = go_mod.read_text(encoding="utf-8", errors="ignore").lower()
                if "gin-gonic" in content:
                    return FrameworkInfo(name="Gin", language="Go")
                elif "echo" in content:
                    return FrameworkInfo(name="Echo", language="Go")
                elif "fiber" in content:
                    return FrameworkInfo(name="Fiber", language="Go")
            except (OSError, IOError):
                pass

    return None


def _count_dependencies(project_root: Path, language: str) -> int:
    """
    Count the number of dependencies in a project.
    """
    count = 0

    if language == "Node.js":
        package_json = project_root / "package.json"
        if package_json.is_file():
            try:
                content = package_json.read_text(encoding="utf-8", errors="ignore")
                # Count dependency entries
                dep_pattern = re.compile(r'"[^"]+"\s*:\s*"[^"]+"')
                
                # Find dependencies sections
                for section in ["dependencies", "devDependencies", "peerDependencies"]:
                    section_match = re.search(
                        rf'"{section}"\s*:\s*\{{([^}}]*)\}}',
                        content,
                        re.DOTALL
                    )
                    if section_match:
                        count += len(dep_pattern.findall(section_match.group(1)))
            except (OSError, IOError):
                pass

    elif language == "Python":
        req_file = project_root / "requirements.txt"
        if req_file.is_file():
            try:
                content = req_file.read_text(encoding="utf-8", errors="ignore")
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        count += 1
            except (OSError, IOError):
                pass

    elif language == "Go":
        go_mod = project_root / "go.mod"
        if go_mod.is_file():
            try:
                content = go_mod.read_text(encoding="utf-8", errors="ignore")
                # Count require statements
                count = len(re.findall(r"^\s+\S+\s+v", content, re.MULTILINE))
            except (OSError, IOError):
                pass

    return count


def generate_project_summary(project_root: Path) -> ProjectSummary:
    """
    Generate a comprehensive project summary.

    Parameters
    ----------
    project_root:
        Path to the project directory.

    Returns
    -------
    ProjectSummary:
        Complete summary of the project's technology stack.
    """
    summary = ProjectSummary(root_path=project_root)

    # ── Run full scan ───────────────────────────────────────────────
    scan_result = full_scan(str(project_root))
    
    # ── Languages ───────────────────────────────────────────────────
    summary.languages = set(scan_result.language_files.keys())
    
    # Remove Docker from primary languages
    primary_languages = summary.languages - {"Docker"}
    if primary_languages:
        summary.primary_language = sorted(primary_languages)[0]
    
    # ── Detection results ───────────────────────────────────────────
    detections = detect_all(scan_result.language_files)
    
    for detection in detections:
        if detection.language == "Docker":
            continue
        
        if detection.language == summary.primary_language:
            summary.package_manager = detection.package_manager
            break
    
    # ── Framework detection ─────────────────────────────────────────
    if summary.primary_language != "Unknown":
        summary.framework = _detect_framework(project_root, summary.primary_language)
    
    # ── Runtime check ───────────────────────────────────────────────
    if summary.primary_language != "Unknown":
        runtime = check_runtime(summary.primary_language)
        summary.runtime_installed = runtime.installed
        summary.runtime_version = runtime.version
    
    # ── Dependency count ────────────────────────────────────────────
    summary.dependency_count = _count_dependencies(project_root, summary.primary_language)
    
    # ── Services detection ──────────────────────────────────────────
    service_result = detect_services(project_root)
    summary.services = sorted(service_result.all_service_names)
    
    # ── Docker ──────────────────────────────────────────────────────
    docker_info = detect_docker(project_root)
    summary.has_dockerfile = docker_info.has_dockerfile
    summary.has_docker_compose = docker_info.has_compose
    summary.docker_installed = docker_info.docker_installed
    
    # ── Monorepo / Subprojects ──────────────────────────────────────
    if scan_result.subprojects:
        summary.is_monorepo = True
        summary.subprojects = [sp.name for sp in scan_result.subprojects]
    
    # ── Environment files ───────────────────────────────────────────
    summary.env_files = [p.name for p in scan_result.env_templates]
    
    # ── Version requirements ────────────────────────────────────────
    summary.version_requirements = get_all_version_requirements(project_root)
    
    return summary


def print_project_summary(summary: ProjectSummary) -> None:
    """
    Print a formatted project summary to the console.
    """
    # ── Header ──────────────────────────────────────────────────────
    title = Text()
    title.append("Project Summary", style="bold bright_cyan")
    
    console.print()
    console.print(Panel(title, border_style="bright_cyan"))
    console.print()
    
    # ── Main info table ─────────────────────────────────────────────
    table = Table(
        show_header=False,
        border_style="bright_cyan",
        padding=(0, 2),
        expand=True,
    )
    table.add_column("Key", style="bold white", min_width=20)
    table.add_column("Value", style="white")
    
    # Language
    lang_str = summary.primary_language
    if summary.framework:
        lang_str = f"{summary.primary_language} ({summary.framework.name})"
    table.add_row("Language", f"[bold]{lang_str}[/bold]")
    
    # Framework (if detected separately)
    if summary.framework and summary.framework.version:
        table.add_row("Framework", f"[bold]{summary.framework.name}[/bold] {summary.framework.version}")
    
    # Runtime
    if summary.runtime_installed:
        table.add_row("Runtime", f"[green]{summary.runtime_version or 'installed'}[/green]")
    else:
        table.add_row("Runtime", "[red]NOT FOUND[/red]")
    
    # Package Manager
    table.add_row("Package Manager", f"[bold]{summary.package_manager}[/bold]")
    
    # Dependencies
    if summary.dependency_count > 0:
        table.add_row("Dependencies", f"[bold]{summary.dependency_count}[/bold] packages")
    
    console.print(table)
    console.print()
    
    # ── Services ────────────────────────────────────────────────────
    if summary.services:
        services_table = Table(
            title="Required Services",
            title_style="bold bright_cyan",
            border_style="dim",
            padding=(0, 2),
        )
        services_table.add_column("Service", style="bold white")
        services_table.add_column("Status", style="white")
        
        for service in summary.services:
            services_table.add_row(
                service,
                "[yellow]detected[/yellow]",
            )
        
        console.print(services_table)
        console.print()
    
    # ── Docker ──────────────────────────────────────────────────────
    if summary.has_dockerfile or summary.has_docker_compose:
        docker_lines = []
        if summary.has_dockerfile:
            docker_lines.append("[green]Dockerfile[/green] detected")
        if summary.has_docker_compose:
            docker_lines.append("[green]docker-compose.yml[/green] detected")
        
        if summary.docker_installed:
            docker_lines.append("\n[green]Docker[/green] is installed")
        else:
            docker_lines.append("\n[red]Docker[/red] is NOT installed")
        
        console.print(
            Panel(
                "\n".join(docker_lines),
                title="[bold cyan]Docker[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        console.print()
    
    # ── Subprojects (Monorepo) ──────────────────────────────────────
    if summary.is_monorepo and summary.subprojects:
        sub_table = Table(
            title="Subprojects",
            title_style="bold bright_cyan",
            border_style="dim",
            padding=(0, 2),
        )
        sub_table.add_column("Directory", style="bold white")
        
        for subproject in summary.subprojects:
            sub_table.add_row(subproject)
        
        console.print(sub_table)
        console.print()
