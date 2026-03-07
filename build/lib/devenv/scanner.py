"""
scanner.py -- Project directory walker and dependency file discoverer.

Responsibility:
    Walk the target project directory and return every known dependency
    file grouped by the programming language it belongs to.

Design choices:
    - The walk is bounded to a maximum depth of 3 directories below the
      root so that vendored or nested ``node_modules``-style trees do
      not pollute the results.
    - Common noise directories (``.git``, ``node_modules``, ``vendor``,
      virtual-env folders, build artefacts, etc.) are pruned immediately
      so the scan stays fast even in large monorepos.
    - Subproject directories (``frontend/``, ``backend/``, ``services/``,
      ``apps/``) are detected and scanned independently.
    - Glob patterns (e.g. ``*.csproj``) are matched in addition to
      exact filename lookups.
    - Environment template files (``.env.example``, ``.env.sample``)
      are collected separately for the env_manager module.
    - Docker configuration files are flagged for the docker_tools module.
    - Results are returned as ``{language: [Path, ...]}`` so that
      downstream modules can iterate per-language without re-scanning.
"""

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .utils import (
    DEPENDENCY_FILES,
    DEPENDENCY_GLOBS,
    ENV_TEMPLATES,
    SUBPROJECT_DIRS,
)


# Directories that should never be descended into.  These are either
# package caches, build outputs, VCS metadata, or virtual environments.
_SKIP_DIRS = frozenset({
    "node_modules", ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    "vendor", "target", "build", "dist",
    ".tox", ".venv", "venv", "env",
    ".terraform", ".cargo", "bin", "obj",
})

# Maximum depth below the root to scan.
_MAX_DEPTH = 3


@dataclass
class ScanResult:
    """
    Complete result of scanning a project directory.

    Attributes
    ----------
    root:
        The resolved root path that was scanned.
    language_files:
        ``{language: [Path, ...]}`` for every dependency file found.
    env_templates:
        Paths to environment template files (e.g. ``.env.example``).
    docker_files:
        Paths to Docker-related files (``Dockerfile``, ``docker-compose.yml``).
    subprojects:
        Directory names that appear to be independent subprojects.
    all_files:
        Flat set of all filenames encountered (used by the detector
        to check for lock files and sibling indicators).
    """
    root: Path
    language_files: Dict[str, List[Path]] = field(default_factory=dict)
    env_templates: List[Path] = field(default_factory=list)
    docker_files: List[Path] = field(default_factory=list)
    subprojects: List[Path] = field(default_factory=list)
    all_files: Set[str] = field(default_factory=set)


def scan_directory(root: str = ".") -> Dict[str, List[Path]]:
    """
    Scan *root* for known dependency files.

    Returns a mapping ``{language: [path, ...]}`` for every dependency
    file found.  This is the backwards-compatible API used by the
    existing ``init`` command.

    Parameters
    ----------
    root:
        Filesystem path to the project directory.  Defaults to the
        current working directory.

    Returns
    -------
    dict:
        Keys are language names (``"Node.js"``, ``"Python"``, etc.),
        values are lists of :class:`pathlib.Path` objects pointing at
        the matched dependency files.
    """
    result = full_scan(root)
    return result.language_files


def full_scan(root: str = ".") -> ScanResult:
    """
    Perform a comprehensive scan of *root* returning a :class:`ScanResult`.

    This extended scan also collects environment templates, Docker files,
    and identifies subproject directories -- used by the new CLI commands
    (``scan``, ``doctor``, ``info``).
    """
    root_path = Path(root).resolve()
    result = ScanResult(root=root_path)

    for dirpath, dirnames, filenames in os.walk(root_path):
        # ── Prune noisy / irrelevant directories ───────────────────
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]

        # ── Depth guard -- only scan _MAX_DEPTH levels below root ──
        rel_depth = Path(dirpath).relative_to(root_path).parts
        if len(rel_depth) > _MAX_DEPTH:
            dirnames.clear()
            continue

        # ── Detect subproject directories ──────────────────────────
        current_dir = Path(dirpath)
        if len(rel_depth) == 1 and current_dir.name in SUBPROJECT_DIRS:
            result.subprojects.append(current_dir)

        # ── Match filenames against known dependency files ─────────
        for fname in filenames:
            result.all_files.add(fname)
            full_path = Path(dirpath) / fname

            # Exact filename match
            if fname in DEPENDENCY_FILES:
                lang = DEPENDENCY_FILES[fname]
                result.language_files.setdefault(lang, []).append(full_path)

                # Collect Docker files separately as well
                if lang == "Docker":
                    result.docker_files.append(full_path)

            # Glob pattern match (e.g. *.csproj)
            for pattern, lang in DEPENDENCY_GLOBS.items():
                if fnmatch.fnmatch(fname, pattern):
                    result.language_files.setdefault(lang, []).append(full_path)

            # Environment template detection
            if fname in ENV_TEMPLATES:
                result.env_templates.append(full_path)

    return result


def list_dependency_files(root: str = ".") -> List[str]:
    """
    Convenience helper -- return a flat list of discovered dependency
    file paths as plain strings.

    Useful for quick inspections and debugging.
    """
    results = scan_directory(root)
    paths: List[str] = []
    for file_list in results.values():
        for p in file_list:
            paths.append(str(p))
    return paths
