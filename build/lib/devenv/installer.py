"""
installer.py -- Execute dependency installation commands.

Responsibility:
    Given a resolved install command (e.g. ``["npm", "install"]``), run
    it as a subprocess inside the target project directory and stream
    its output to the terminal in real time.

Error handling:
    The module defines a custom :class:`InstallError` exception.  Any
    failure -- non-zero exit code, missing binary, OS-level error -- is
    raised as an ``InstallError`` with a human-readable message.  The
    CLI layer catches this and renders it with Rich formatting.

Safety:
    DEVENV never writes files to the user's project.  The only mutation
    is whatever the package manager itself does (downloading packages
    into ``node_modules/``, ``vendor/``, etc.).  A ``--dry-run`` mode
    is provided to preview the command without executing it.
"""

import subprocess
import sys
from typing import List

from .utils import console


class InstallError(Exception):
    """Raised when a dependency installation command fails."""


def run_install(
    install_command: List[str],
    cwd: str = ".",
    dry_run: bool = False,
) -> bool:
    """
    Execute *install_command* inside *cwd*.

    Parameters
    ----------
    install_command:
        Full ``argv`` list, e.g. ``["npm", "install"]``.
    cwd:
        Working directory where the command should run.  Typically the
        project root.
    dry_run:
        When ``True`` the command is printed but never executed.

    Returns
    -------
    bool:
        ``True`` on success.

    Raises
    ------
    InstallError:
        On any failure -- empty command, non-zero exit code, missing
        binary, or OS-level error.
    """
    # Guard: an empty command means the detector could not resolve a
    # package manager -- this should never reach here, but we protect
    # against it just in case.
    if not install_command:
        raise InstallError("No install command resolved for this project.")

    cmd_str = " ".join(install_command)

    # ── Dry-run mode ────────────────────────────────────────────────
    if dry_run:
        console.print(f"[dim][dry-run] would execute:[/dim] {cmd_str}")
        return True

    # ── Real execution ──────────────────────────────────────────────
    console.print(f"[bold cyan]Running:[/bold cyan] {cmd_str}\n")

    try:
        # We stream stdout line-by-line so the user sees real-time
        # progress from the package manager (download bars, warnings,
        # compilation output, etc.).
        process = subprocess.Popen(
            install_command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # line-buffered
        )

        assert process.stdout is not None  # for type-checkers
        for line in process.stdout:
            sys.stdout.write(line)

        return_code = process.wait()

        if return_code != 0:
            raise InstallError(
                f"Command '{cmd_str}' exited with code {return_code}."
            )

        return True

    except FileNotFoundError:
        raise InstallError(
            f"Command not found: '{install_command[0]}'. "
            "Is the package manager installed and on your PATH?"
        )
    except OSError as exc:
        raise InstallError(f"OS error running '{cmd_str}': {exc}")
