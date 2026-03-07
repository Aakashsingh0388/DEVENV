"""
runtime_check.py -- Verify that required language runtimes are installed.

Responsibility:
    Before we attempt to install dependencies we need to know whether the
    language runtime (``node``, ``python3``, ``go``, ``rustc``, ``java``,
    ``php``, ``ruby``, ``dotnet``, ``terraform``, ``docker``) actually
    exists on the user's ``$PATH``.

    This module provides :func:`check_runtime` for individual checks and
    :func:`check_all_runtimes` for a full health report across every
    supported ecosystem.

Design notes:
    - We first use :func:`shutil.which` as a fast-path check.  This
      avoids spawning a subprocess when the binary is clearly missing.
    - When the binary *is* found we invoke it with its version flag and
      capture both stdout and stderr (Java prints to stderr).
    - A generous 10-second timeout guards against pathological cases
      where a binary hangs.
    - We intentionally do NOT offer to install missing runtimes.  That
      crosses into system administration territory and is outside
      DEVENV's scope.
"""

import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..utils import RUNTIME_CHECKS


@dataclass
class RuntimeStatus:
    """
    Result of a single runtime availability check.

    Attributes
    ----------
    language:
        The language that was checked (e.g. ``"Node.js"``).
    command:
        The binary name we looked for (e.g. ``"node"``).
    installed:
        ``True`` if the binary was found and responded to its version flag.
    version:
        The first line of version output, or ``None`` if the runtime is
        not installed.
    """

    language: str
    command: str
    installed: bool
    version: Optional[str] = None


def check_runtime(language: str) -> RuntimeStatus:
    """
    Verify that the runtime for *language* is reachable on ``$PATH``.

    Parameters
    ----------
    language:
        A language key matching :data:`utils.RUNTIME_CHECKS`
        (e.g. ``"Node.js"``, ``"Python"``).

    Returns
    -------
    RuntimeStatus:
        ``installed=True`` with the detected ``version`` string when
        the binary is found.  ``installed=False`` otherwise.

    Examples
    --------
    >>> status = check_runtime("Python")
    >>> status.installed
    True
    >>> status.version
    'Python 3.11.4'
    """
    entry = RUNTIME_CHECKS.get(language)
    if entry is None:
        # Language not in our registry -- report as missing.
        return RuntimeStatus(
            language=language,
            command="(unknown)",
            installed=False,
        )

    cmd, args = entry

    # Fast-path: is the binary on $PATH at all?
    if shutil.which(cmd) is None:
        return RuntimeStatus(
            language=language,
            command=cmd,
            installed=False,
        )

    # The binary exists -- invoke it and capture the version string.
    try:
        result = subprocess.run(
            [cmd, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Some runtimes (notably Java) print to stderr rather than stdout.
        raw = result.stdout.strip() or result.stderr.strip()
        lines = raw.splitlines()
        version_line = lines[0] if lines else ""

        return RuntimeStatus(
            language=language,
            command=cmd,
            installed=True,
            version=version_line,
        )
    except (subprocess.SubprocessError, OSError, IndexError):
        return RuntimeStatus(
            language=language,
            command=cmd,
            installed=False,
        )


def check_all_runtimes() -> List[RuntimeStatus]:
    """
    Check every runtime in the registry and return a list of statuses.

    This is used by the ``devenv doctor`` command to produce a full
    health report of the developer's system.
    """
    statuses: List[RuntimeStatus] = []
    for language in RUNTIME_CHECKS:
        statuses.append(check_runtime(language))
    return statuses


def check_project_runtimes(languages: List[str]) -> Dict[str, RuntimeStatus]:
    """
    Check runtimes only for the given list of languages.

    Returns a dict keyed by language name for easy lookup.
    """
    results: Dict[str, RuntimeStatus] = {}
    for lang in languages:
        results[lang] = check_runtime(lang)
    return results
