"""
multi_project.py -- Multi-project / monorepo detection and handling.

Responsibility:
    Detect when a repository contains multiple independent projects
    (e.g., frontend + backend, multiple microservices) and provide
    functionality to process them individually or collectively.

Detection strategies:
    1. **Directory structure** - Look for common monorepo patterns:
       - frontend/, backend/, services/
       - packages/, apps/, libs/
       - Multiple directories with their own dependency files
    
    2. **Monorepo tools** - Detect workspace configurations:
       - npm/yarn/pnpm workspaces in package.json
       - Lerna, Nx, Turborepo configurations
       - Python monorepo tools (pants, bazel)
    
    3. **Independent projects** - Multiple projects that happen to be
       in the same repository but aren't managed as a monorepo.

This module supports the use case where ``devenv install`` needs to
handle multiple sub-projects independently.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .scanner import full_scan, ScanResult


@dataclass
class SubProject:
    """
    Information about a detected sub-project.

    Attributes
    ----------
    name:
        Human-readable name (usually directory name).
    path:
        Absolute path to the sub-project directory.
    language:
        Detected primary language.
    languages:
        All languages detected in this sub-project.
    has_dependencies:
        Whether dependency files were found.
    """
    name: str
    path: Path
    language: str = "Unknown"
    languages: Set[str] = field(default_factory=set)
    has_dependencies: bool = False


@dataclass
class MonorepoConfig:
    """
    Configuration for a detected monorepo setup.

    Attributes
    ----------
    tool:
        The monorepo tool in use (npm workspaces, yarn, pnpm, lerna, nx, turborepo, etc.)
    workspace_patterns:
        Glob patterns for workspace packages.
    root_path:
        Path to the monorepo root.
    """
    tool: str
    workspace_patterns: List[str] = field(default_factory=list)
    root_path: Optional[Path] = None


@dataclass
class MultiProjectResult:
    """
    Complete result of multi-project detection.

    Attributes
    ----------
    is_monorepo:
        Whether this is a managed monorepo (vs. multiple independent projects).
    monorepo_config:
        Configuration if this is a monorepo.
    projects:
        List of detected sub-projects.
    root_languages:
        Languages detected at the repository root level.
    """
    is_monorepo: bool = False
    monorepo_config: Optional[MonorepoConfig] = None
    projects: List[SubProject] = field(default_factory=list)
    root_languages: Set[str] = field(default_factory=set)

    @property
    def has_multiple_projects(self) -> bool:
        """True if multiple independent projects were detected."""
        return len(self.projects) > 1

    @property
    def project_count(self) -> int:
        """Total number of projects detected."""
        return len(self.projects)


# Directories that commonly contain sub-projects
_SUBPROJECT_DIRS = frozenset({
    "frontend", "backend", "server", "client", "web", "api",
    "services", "apps", "packages", "libs", "modules",
    "mobile", "desktop", "cli", "core", "shared", "common",
})

# Directories to skip when scanning for sub-projects
_SKIP_DIRS = frozenset({
    "node_modules", ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    "vendor", "target", "build", "dist",
    ".tox", ".venv", "venv", "env",
    ".terraform", ".cargo", "bin", "obj",
    ".next", ".nuxt", "out", "coverage",
})


def _detect_monorepo_config(project_root: Path) -> Optional[MonorepoConfig]:
    """
    Detect if the project uses a monorepo management tool.
    """
    # Check for npm/yarn/pnpm workspaces
    package_json = project_root / "package.json"
    if package_json.is_file():
        try:
            content = package_json.read_text(encoding="utf-8", errors="ignore")
            
            # Check for workspaces field
            workspaces_match = re.search(
                r'"workspaces"\s*:\s*(\[[^\]]+\]|\{[^}]+\})',
                content,
                re.DOTALL
            )
            
            if workspaces_match:
                workspaces_str = workspaces_match.group(1)
                # Extract patterns from workspaces array
                patterns = re.findall(r'"([^"]+)"', workspaces_str)
                
                # Determine which tool based on lock file
                if (project_root / "pnpm-lock.yaml").exists():
                    tool = "pnpm workspaces"
                elif (project_root / "yarn.lock").exists():
                    tool = "yarn workspaces"
                else:
                    tool = "npm workspaces"
                
                return MonorepoConfig(
                    tool=tool,
                    workspace_patterns=patterns,
                    root_path=project_root,
                )
        except (OSError, IOError):
            pass

    # Check for Lerna
    lerna_json = project_root / "lerna.json"
    if lerna_json.is_file():
        try:
            content = lerna_json.read_text(encoding="utf-8", errors="ignore")
            patterns = re.findall(r'"packages"\s*:\s*\[(.*?)\]', content, re.DOTALL)
            workspace_patterns = []
            if patterns:
                workspace_patterns = re.findall(r'"([^"]+)"', patterns[0])
            
            return MonorepoConfig(
                tool="Lerna",
                workspace_patterns=workspace_patterns or ["packages/*"],
                root_path=project_root,
            )
        except (OSError, IOError):
            pass

    # Check for Nx
    nx_json = project_root / "nx.json"
    if nx_json.is_file():
        return MonorepoConfig(
            tool="Nx",
            workspace_patterns=["apps/*", "libs/*"],
            root_path=project_root,
        )

    # Check for Turborepo
    turbo_json = project_root / "turbo.json"
    if turbo_json.is_file():
        return MonorepoConfig(
            tool="Turborepo",
            workspace_patterns=["apps/*", "packages/*"],
            root_path=project_root,
        )

    # Check for Rush
    rush_json = project_root / "rush.json"
    if rush_json.is_file():
        return MonorepoConfig(
            tool="Rush",
            workspace_patterns=["apps/*", "libraries/*"],
            root_path=project_root,
        )

    return None


def _is_project_directory(directory: Path) -> bool:
    """
    Check if a directory appears to be an independent project.
    """
    # Check for dependency files
    dependency_files = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "go.mod",
        "Cargo.toml",
        "composer.json",
        "Gemfile",
        "pom.xml",
        "build.gradle",
    ]
    
    for dep_file in dependency_files:
        if (directory / dep_file).is_file():
            return True
    
    # Check for .csproj files
    if list(directory.glob("*.csproj")):
        return True
    
    return False


def _detect_language(directory: Path) -> str:
    """
    Detect the primary language for a directory.
    """
    language_files = {
        "package.json": "Node.js",
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "Pipfile": "Python",
        "go.mod": "Go",
        "Cargo.toml": "Rust",
        "composer.json": "PHP",
        "Gemfile": "Ruby",
        "pom.xml": "Java",
        "build.gradle": "Java",
    }
    
    for filename, language in language_files.items():
        if (directory / filename).is_file():
            return language
    
    # Check for .csproj files
    if list(directory.glob("*.csproj")):
        return ".NET"
    
    return "Unknown"


def _detect_all_languages(directory: Path) -> Set[str]:
    """
    Detect all languages present in a directory.
    """
    languages: Set[str] = set()
    
    language_files = {
        "package.json": "Node.js",
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "Pipfile": "Python",
        "go.mod": "Go",
        "Cargo.toml": "Rust",
        "composer.json": "PHP",
        "Gemfile": "Ruby",
        "pom.xml": "Java",
        "build.gradle": "Java",
        "Dockerfile": "Docker",
        "docker-compose.yml": "Docker",
    }
    
    for filename, language in language_files.items():
        if (directory / filename).is_file():
            languages.add(language)
    
    if list(directory.glob("*.csproj")):
        languages.add(".NET")
    
    return languages


def detect_multi_project(project_root: Path) -> MultiProjectResult:
    """
    Detect multiple projects in a repository.

    Parameters
    ----------
    project_root:
        Path to the repository root.

    Returns
    -------
    MultiProjectResult:
        Complete information about detected projects.
    """
    result = MultiProjectResult()
    
    # ── Check for monorepo configuration ────────────────────────────
    monorepo_config = _detect_monorepo_config(project_root)
    if monorepo_config:
        result.is_monorepo = True
        result.monorepo_config = monorepo_config
    
    # ── Scan root-level languages ───────────────────────────────────
    result.root_languages = _detect_all_languages(project_root)
    
    # ── Look for sub-project directories ────────────────────────────
    found_projects: List[SubProject] = []
    
    # First, check known subproject directory names
    for dir_name in _SUBPROJECT_DIRS:
        subdir = project_root / dir_name
        if subdir.is_dir() and _is_project_directory(subdir):
            found_projects.append(SubProject(
                name=dir_name,
                path=subdir,
                language=_detect_language(subdir),
                languages=_detect_all_languages(subdir),
                has_dependencies=True,
            ))
    
    # Then, check all immediate subdirectories
    try:
        for subdir in project_root.iterdir():
            if not subdir.is_dir():
                continue
            if subdir.name in _SKIP_DIRS:
                continue
            if subdir.name.startswith("."):
                continue
            # Skip if already found
            if any(p.path == subdir for p in found_projects):
                continue
            
            if _is_project_directory(subdir):
                found_projects.append(SubProject(
                    name=subdir.name,
                    path=subdir,
                    language=_detect_language(subdir),
                    languages=_detect_all_languages(subdir),
                    has_dependencies=True,
                ))
    except (OSError, IOError):
        pass
    
    # ── Sort projects by name ───────────────────────────────────────
    result.projects = sorted(found_projects, key=lambda p: p.name)
    
    # ── If monorepo config exists, expand workspace patterns ────────
    if result.is_monorepo and monorepo_config and monorepo_config.workspace_patterns:
        # Find projects matching workspace patterns
        for pattern in monorepo_config.workspace_patterns:
            # Convert glob pattern to actual directories
            pattern_dir = pattern.rstrip("/*")
            pattern_path = project_root / pattern_dir
            
            if pattern_path.is_dir():
                try:
                    for subdir in pattern_path.iterdir():
                        if not subdir.is_dir():
                            continue
                        if subdir.name in _SKIP_DIRS:
                            continue
                        if any(p.path == subdir for p in result.projects):
                            continue
                        
                        if _is_project_directory(subdir):
                            result.projects.append(SubProject(
                                name=f"{pattern_dir}/{subdir.name}",
                                path=subdir,
                                language=_detect_language(subdir),
                                languages=_detect_all_languages(subdir),
                                has_dependencies=True,
                            ))
                except (OSError, IOError):
                    pass
    
    # Sort again after adding workspace projects
    result.projects = sorted(result.projects, key=lambda p: p.name)
    
    return result


def print_multi_project_summary(result: MultiProjectResult) -> None:
    """
    Print a summary of detected projects.
    """
    from .utils import console
    from rich.table import Table
    from rich.panel import Panel
    
    if not result.has_multiple_projects:
        return
    
    # Header
    if result.is_monorepo and result.monorepo_config:
        console.print(
            Panel(
                f"[bold]Monorepo detected:[/bold] {result.monorepo_config.tool}",
                title="[bold bright_cyan]Multi-Project Repository[/bold bright_cyan]",
                border_style="bright_cyan",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold]{result.project_count}[/bold] independent projects detected",
                title="[bold bright_cyan]Multi-Project Repository[/bold bright_cyan]",
                border_style="bright_cyan",
            )
        )
    
    console.print()
    
    # Projects table
    table = Table(
        title="Detected Projects",
        title_style="bold bright_cyan",
        border_style="bright_cyan",
        padding=(0, 2),
    )
    table.add_column("Project", style="bold white", min_width=20)
    table.add_column("Language", style="white", min_width=12)
    table.add_column("Path", style="dim")
    
    for project in result.projects:
        lang_str = project.language
        if len(project.languages) > 1:
            other_langs = project.languages - {project.language}
            lang_str = f"{project.language} (+{', '.join(sorted(other_langs))})"
        
        table.add_row(
            project.name,
            lang_str,
            str(project.path.relative_to(result.projects[0].path.parent.parent) if result.projects else project.path),
        )
    
    console.print(table)
    console.print()
