"""
detector.py -- Language and package manager detection engine.

Responsibility:
    Given the scan results (a mapping of language -> dependency file paths),
    determine which *package manager* is in use for each language by
    inspecting lock files and indicator files in the project directory.

Resolution strategy:
    For each language the ``PACKAGE_MANAGERS`` list in ``utils.py`` is
    ordered by priority.  The first entry whose ``indicator_file`` is
    present among the project's files wins.  This means, for example,
    that ``pnpm-lock.yaml`` takes precedence over ``yarn.lock``, and
    ``yarn.lock`` over a bare ``package.json`` (npm fallback).

Extended support:
    - .NET projects detected via ``*.csproj`` glob patterns.
    - Terraform detected via ``main.tf``.
    - Docker detected via ``Dockerfile`` / ``docker-compose.yml``.
"""

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .utils import PACKAGE_MANAGERS, PackageManagerInfo


@dataclass
class DetectionResult:
    """
    Aggregated result for a single detected language stack.

    Attributes
    ----------
    language:
        The programming language name (e.g. ``"Node.js"``).
    dependency_file:
        The filename that triggered the detection (e.g. ``"package.json"``).
    package_manager:
        Resolved manager name (e.g. ``"yarn"``), or ``"unknown"`` if
        no matching manager could be determined.
    install_command:
        The full ``argv`` list to execute the install, e.g.
        ``["yarn", "install"]``.  Empty when the manager is unknown.
    """

    language: str
    dependency_file: str
    package_manager: str
    install_command: List[str]


def detect_package_manager(
    language: str,
    dep_files: List[Path],
) -> Optional[PackageManagerInfo]:
    """
    Determine the best-matching package manager for *language*.

    Parameters
    ----------
    language:
        Language string as returned by the scanner.
    dep_files:
        The dependency file paths found for this language.

    Returns
    -------
    PackageManagerInfo or None:
        The first matching manager from the priority list, or ``None``
        if no indicator file could be matched.

    How it works:
        1. Collect the basenames of every dependency file found.
        2. Also list *all* sibling files in each dependency file's parent
           directory -- this catches lock files (``yarn.lock``,
           ``pnpm-lock.yaml``, etc.) that are not themselves dependency
           files but live alongside ``package.json``.
        3. Walk the priority-ordered ``PACKAGE_MANAGERS[language]`` list
           and return the first entry whose ``indicator_file`` appears
           in the combined set.
        4. For glob-style indicators (e.g. ``*.csproj``), use fnmatch
           to check against all known filenames.
    """
    managers = PACKAGE_MANAGERS.get(language)
    if not managers:
        return None

    # Build a set of basenames from the dependency files themselves.
    basenames = {p.name for p in dep_files}

    # Also inspect sibling files to pick up lock files.
    parent_files: set = set()
    for p in dep_files:
        if p.parent.exists():
            parent_files.update(
                f.name for f in p.parent.iterdir() if f.is_file()
            )

    all_known = basenames | parent_files

    # First match in priority order wins.
    for mgr in managers:
        # Check if the indicator is a glob pattern
        if "*" in mgr.indicator_file or "?" in mgr.indicator_file:
            for fname in all_known:
                if fnmatch.fnmatch(fname, mgr.indicator_file):
                    return mgr
        elif mgr.indicator_file in all_known:
            return mgr

    return None


def detect_all(
    scan_results: Dict[str, List[Path]],
) -> List[DetectionResult]:
    """
    Analyse the full scan results and produce one :class:`DetectionResult`
    per detected language.

    If a language is found but no package manager can be resolved, the
    result still appears in the list with ``package_manager="unknown"``
    and an empty ``install_command`` so the CLI can report it gracefully.
    """
    detections: List[DetectionResult] = []

    for language, dep_paths in scan_results.items():
        mgr = detect_package_manager(language, dep_paths)
        if mgr is None:
            detections.append(DetectionResult(
                language=language,
                dependency_file=str(dep_paths[0].name),
                package_manager="unknown",
                install_command=[],
            ))
        else:
            detections.append(DetectionResult(
                language=language,
                dependency_file=mgr.indicator_file,
                package_manager=mgr.name,
                install_command=list(mgr.install_command),
            ))

    return detections
