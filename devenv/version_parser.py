"""
version_parser.py -- Parse version requirements from project files.

Responsibility:
    Extract version constraints from ecosystem-specific configuration
    files so the CLI can warn the user when their installed runtime
    does not match the project's requirements.

Supported sources:
    - ``package.json``  -> ``engines.node``, ``engines.npm``
    - ``pyproject.toml`` -> ``requires-python``
    - ``runtime.txt``   -> e.g. ``python-3.11.4``
    - ``go.mod``        -> ``go X.Y``
    - ``.tool-versions`` -> asdf-style version pinning

Design:
    All parsing is best-effort.  If a file cannot be parsed or the
    version field is absent, ``None`` is returned.  No exceptions
    are raised for malformed content -- DEVENV does not enforce
    versions, it merely reports them.
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional


def parse_node_engines(project_root: Path) -> Optional[Dict[str, str]]:
    """
    Extract ``engines`` from ``package.json``.

    Returns a dict like ``{"node": ">=18.0.0", "npm": ">=9.0.0"}``
    or ``None`` if the file is absent or has no ``engines`` field.
    """
    pkg_json = project_root / "package.json"
    if not pkg_json.is_file():
        return None
    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
        engines = data.get("engines")
        if isinstance(engines, dict) and engines:
            return {k: str(v) for k, v in engines.items()}
    except (json.JSONDecodeError, OSError):
        pass
    return None


def parse_python_version(project_root: Path) -> Optional[str]:
    """
    Extract the required Python version from ``pyproject.toml`` or
    ``runtime.txt``.

    Checks ``pyproject.toml`` first (``requires-python``), then falls
    back to ``runtime.txt`` (Heroku-style ``python-3.11.4``).
    """
    # --- pyproject.toml ---
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8")
            match = re.search(
                r'requires-python\s*=\s*["\']([^"\']+)["\']',
                content,
            )
            if match:
                return match.group(1).strip()
        except OSError:
            pass

    # --- runtime.txt ---
    runtime_txt = project_root / "runtime.txt"
    if runtime_txt.is_file():
        try:
            content = runtime_txt.read_text(encoding="utf-8").strip()
            # Heroku format: python-3.11.4
            match = re.match(r"python-?([\d.]+)", content, re.IGNORECASE)
            if match:
                return f"=={match.group(1)}"
        except OSError:
            pass

    return None


def parse_go_version(project_root: Path) -> Optional[str]:
    """
    Extract the Go version directive from ``go.mod``.

    Looks for a line like ``go 1.21`` and returns ``"1.21"``.
    """
    go_mod = project_root / "go.mod"
    if not go_mod.is_file():
        return None
    try:
        content = go_mod.read_text(encoding="utf-8")
        match = re.search(r"^go\s+([\d.]+)", content, re.MULTILINE)
        if match:
            return match.group(1)
    except OSError:
        pass
    return None


def parse_tool_versions(project_root: Path) -> Optional[Dict[str, str]]:
    """
    Parse ``.tool-versions`` (asdf format).

    Each line is ``<tool> <version>``, e.g.::

        nodejs 20.11.0
        python 3.12.1

    Returns a dict like ``{"nodejs": "20.11.0", "python": "3.12.1"}``
    or ``None`` if the file is absent.
    """
    tv_file = project_root / ".tool-versions"
    if not tv_file.is_file():
        return None
    try:
        versions: Dict[str, str] = {}
        for line in tv_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                versions[parts[0]] = parts[1]
        return versions if versions else None
    except OSError:
        pass
    return None


def get_all_version_requirements(project_root: Path) -> Dict[str, str]:
    """
    Aggregate all version requirements found in the project.

    Returns a dict like::

        {
            "Node.js": ">=18.0.0",
            "Python": ">=3.8",
            "Go": "1.21",
        }

    Only includes entries where a version requirement was found.
    """
    reqs: Dict[str, str] = {}

    # Node.js
    engines = parse_node_engines(project_root)
    if engines and "node" in engines:
        reqs["Node.js"] = engines["node"]

    # Python
    py_ver = parse_python_version(project_root)
    if py_ver:
        reqs["Python"] = py_ver

    # Go
    go_ver = parse_go_version(project_root)
    if go_ver:
        reqs["Go"] = go_ver

    # .tool-versions (supplements other sources)
    tv = parse_tool_versions(project_root)
    if tv:
        tool_to_lang = {
            "nodejs": "Node.js",
            "python": "Python",
            "golang": "Go",
            "ruby": "Ruby",
            "java": "Java",
            "rust": "Rust",
            "php": "PHP",
            "dotnet": ".NET",
            "terraform": "Terraform",
        }
        for tool, version in tv.items():
            lang = tool_to_lang.get(tool)
            if lang and lang not in reqs:
                reqs[lang] = version

    return reqs
