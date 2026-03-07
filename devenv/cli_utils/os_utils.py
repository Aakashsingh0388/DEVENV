"""
os_utils.py -- Operating system detection and cross-platform runtime installation.

This module provides:
- Automatic OS detection (Windows, Linux, macOS)
- Package manager detection for each OS
- Runtime installation commands for missing runtimes
- Cross-OS compatibility features (WSL detection, etc.)
"""

import platform
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..utils import console


class OperatingSystem(Enum):
    """Supported operating systems."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


@dataclass
class OSInfo:
    """Information about the detected operating system."""
    os: OperatingSystem
    version: str
    package_manager: str
    is_wsl: bool = False


@dataclass
class RuntimeInstallCommand:
    """Command to install a runtime on a specific OS."""
    package_name: str
    install_command: List[str]
    description: str


# OS-specific package managers
OS_PACKAGE_MANAGERS = {
    OperatingSystem.WINDOWS: ["winget", "chocolatey"],
    OperatingSystem.LINUX: ["apt", "yum", "dnf", "pacman", "zypper"],
    OperatingSystem.MACOS: ["brew"],
}

# Package manager specific install commands for Linux distributions
PACKAGE_MANAGER_COMMANDS = {
    "apt": {
        "update": ["sudo", "apt", "update"],
        "install": ["sudo", "apt", "install", "-y"],
        "Node.js": "nodejs npm",
        "Python": "python3 python3-pip",
        "Go": "golang",
        "Java": "openjdk-11-jdk",
        "Docker": "docker.io",
        "Rust": "rustc",
        "Ruby": "ruby-full",
    },
    "yum": {
        "update": ["sudo", "yum", "update", "-y"],
        "install": ["sudo", "yum", "install", "-y"],
        "Node.js": "nodejs npm",
        "Python": "python3 python3-pip",
        "Go": "golang",
        "Java": "java-11-openjdk",
        "Docker": "docker",
        "Rust": "rust",
        "Ruby": "ruby",
    },
    "dnf": {
        "update": ["sudo", "dnf", "update", "-y"],
        "install": ["sudo", "dnf", "install", "-y"],
        "Node.js": "nodejs npm",
        "Python": "python3 python3-pip",
        "Go": "golang",
        "Java": "java-11-openjdk",
        "Docker": "docker",
        "Rust": "rust",
        "Ruby": "ruby",
    },
    "pacman": {
        "update": ["sudo", "pacman", "-Syu", "--noconfirm"],
        "install": ["sudo", "pacman", "-S", "--noconfirm"],
        "Node.js": "nodejs npm",
        "Python": "python python-pip",
        "Go": "go",
        "Java": "jdk11-openjdk",
        "Docker": "docker",
        "Rust": "rust",
        "Ruby": "ruby",
    },
    "zypper": {
        "update": ["sudo", "zypper", "refresh"],
        "install": ["sudo", "zypper", "install", "-y"],
        "Node.js": "nodejs npm",
        "Python": "python3 python3-pip",
        "Go": "go",
        "Java": "java-11-openjdk",
        "Docker": "docker",
        "Rust": "rust",
        "Ruby": "ruby",
    },
    "apk": {
        "update": ["sudo", "apk", "update"],
        "install": ["sudo", "apk", "add"],
        "Node.js": "nodejs npm",
        "Python": "python3 py3-pip",
        "Go": "go",
        "Java": "openjdk11",
        "Docker": "docker",
        "Rust": "rust",
        "Ruby": "ruby",
    },
}

# Runtime installation commands by OS and runtime (for Windows and macOS)
RUNTIME_INSTALL_COMMANDS: Dict[Tuple[OperatingSystem, str], RuntimeInstallCommand] = {
    # Windows
    (OperatingSystem.WINDOWS, "Node.js"): RuntimeInstallCommand(
        "nodejs", ["winget", "install", "OpenJS.NodeJS"], "Node.js runtime"
    ),
    (OperatingSystem.WINDOWS, "Python"): RuntimeInstallCommand(
        "python", ["winget", "install", "Python.Python"], "Python runtime"
    ),
    (OperatingSystem.WINDOWS, "Go"): RuntimeInstallCommand(
        "go", ["winget", "install", "GoLang.Go"], "Go runtime"
    ),
    (OperatingSystem.WINDOWS, "Java"): RuntimeInstallCommand(
        "openjdk", ["winget", "install", "Oracle.JDK"], "Java runtime"
    ),
    (OperatingSystem.WINDOWS, "Docker"): RuntimeInstallCommand(
        "docker", ["winget", "install", "Docker.DockerDesktop"], "Docker"
    ),
    (OperatingSystem.WINDOWS, "Rust"): RuntimeInstallCommand(
        "rustc", ["winget", "install", "Rustlang.Rust.MSVC"], "Rust runtime"
    ),
    (OperatingSystem.WINDOWS, "Ruby"): RuntimeInstallCommand(
        "ruby", ["winget", "install", "RubyInstallerTeam.RubyWithDevKit.3.2"], "Ruby runtime"
    ),

    # macOS
    (OperatingSystem.MACOS, "Node.js"): RuntimeInstallCommand(
        "node", ["brew", "install", "node"], "Node.js runtime"
    ),
    (OperatingSystem.MACOS, "Python"): RuntimeInstallCommand(
        "python", ["brew", "install", "python"], "Python runtime"
    ),
    (OperatingSystem.MACOS, "Go"): RuntimeInstallCommand(
        "go", ["brew", "install", "go"], "Go runtime"
    ),
    (OperatingSystem.MACOS, "Java"): RuntimeInstallCommand(
        "openjdk", ["brew", "install", "openjdk"], "Java runtime"
    ),
    (OperatingSystem.MACOS, "Docker"): RuntimeInstallCommand(
        "docker", ["brew", "install", "--cask", "docker"], "Docker"
    ),
    (OperatingSystem.MACOS, "Rust"): RuntimeInstallCommand(
        "rustc", ["brew", "install", "rustc"], "Rust runtime"
    ),
    (OperatingSystem.MACOS, "Ruby"): RuntimeInstallCommand(
        "ruby", ["brew", "install", "ruby"], "Ruby runtime"
    ),
}


def detect_os() -> OSInfo:
    """
    Detect the operating system and return OS information.

    Returns
    -------
    OSInfo
        Information about the detected OS, package manager, and WSL status.
    """
    system = platform.system().lower()

    if system == "windows":
        os_type = OperatingSystem.WINDOWS
        version = platform.version()
        package_manager = _detect_windows_package_manager()
        is_wsl = _is_wsl()
    elif system == "linux":
        os_type = OperatingSystem.LINUX
        version = platform.release()
        package_manager = _detect_linux_package_manager()
        is_wsl = _is_wsl()
    elif system == "darwin":
        os_type = OperatingSystem.MACOS
        version = platform.mac_ver()[0]
        package_manager = "brew"
        is_wsl = False
    else:
        os_type = OperatingSystem.UNKNOWN
        version = platform.version()
        package_manager = "unknown"
        is_wsl = False

    return OSInfo(
        os=os_type,
        version=version,
        package_manager=package_manager,
        is_wsl=is_wsl
    )


def _detect_windows_package_manager() -> str:
    """Detect the best available package manager on Windows."""
    # Check for winget first (modern Windows)
    if _command_exists("winget"):
        return "winget"
    # Fall back to chocolatey
    elif _command_exists("choco"):
        return "chocolatey"
    else:
        return "unknown"


def _detect_linux_package_manager() -> str:
    """Detect the package manager on Linux."""
    package_managers = [
        ("apt-get", "apt"),  # Debian/Ubuntu
        ("apt", "apt"),      # Debian/Ubuntu
        ("yum", "yum"),      # CentOS/RHEL
        ("dnf", "dnf"),      # Fedora
        ("pacman", "pacman"), # Arch Linux
        ("zypper", "zypper"), # openSUSE
        ("apk", "apk"),      # Alpine Linux
    ]

    for cmd, name in package_managers:
        if _command_exists(cmd):
            return name

    return "unknown"


def _is_wsl() -> bool:
    """Check if running under Windows Subsystem for Linux."""
    try:
        with open("/proc/version", "r") as f:
            version_info = f.read().lower()
            return "microsoft" in version_info or "wsl" in version_info
    except (FileNotFoundError, OSError):
        return False


def _command_exists(command: str) -> bool:
    """Check if a command exists on the system."""
    try:
        subprocess.run(
            [command, "--version"],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_runtime_install_command(os_info: OSInfo, runtime: str) -> Optional[RuntimeInstallCommand]:
    """
    Get the installation command for a runtime on the detected OS.

    Parameters
    ----------
    os_info : OSInfo
        The detected OS information.
    runtime : str
        The runtime to install (e.g., "Node.js", "Python").

    Returns
    -------
    Optional[RuntimeInstallCommand]
        The installation command, or None if not supported.
    """
    # First check for OS-specific commands (Windows, macOS)
    os_specific = RUNTIME_INSTALL_COMMANDS.get((os_info.os, runtime))
    if os_specific:
        return os_specific

    # For Linux, use dynamic package manager commands
    if os_info.os == OperatingSystem.LINUX:
        pm_commands = PACKAGE_MANAGER_COMMANDS.get(os_info.package_manager)
        if pm_commands and runtime in pm_commands:
            packages = pm_commands[runtime]
            update_cmd = pm_commands["update"]
            install_cmd = pm_commands["install"] + packages.split()

            # Combine update and install commands
            full_command = update_cmd + ["&&"] + install_cmd

            return RuntimeInstallCommand(
                package_name=packages.replace(" ", "-"),
                install_command=full_command,
                description=f"{runtime} runtime"
            )

    return None


def install_runtime(runtime_install_cmd: RuntimeInstallCommand, dry_run: bool = False) -> bool:
    """
    Install a runtime using the provided installation command.

    Parameters
    ----------
    runtime_install_cmd : RuntimeInstallCommand
        The installation command to run.
    dry_run : bool, optional
        If True, only show what would be done without executing.

    Returns
    -------
    bool
        True if installation was successful or would be successful.
    """
    if dry_run:
        console.print(f"[dim][dry-run] Would install {runtime_install_cmd.description}[/dim]")
        console.print(f"[dim][dry-run] Command: {' '.join(runtime_install_cmd.install_command)}[/dim]")
        return True

    try:
        console.print(f"Installing {runtime_install_cmd.description}...")
        result = subprocess.run(
            runtime_install_cmd.install_command,
            check=True,
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install {runtime_install_cmd.description}: {e}[/red]")
        return False
    except FileNotFoundError:
        console.print(f"[red]Package manager not found for installing {runtime_install_cmd.description}[/red]")
        return False


def should_use_wsl(os_info: OSInfo, project_type: str) -> bool:
    """
    Determine if WSL should be used for cross-OS compatibility.

    Parameters
    ----------
    os_info : OSInfo
        The detected OS information.
    project_type : str
        The type of project (e.g., "Linux", "macOS").

    Returns
    -------
    bool
        True if WSL should be used.
    """
    if not os_info.is_wsl and os_info.os == OperatingSystem.WINDOWS:
        # If we're on Windows and the project is Linux-specific, suggest WSL
        return project_type.lower() in ["linux", "ubuntu", "debian", "centos", "fedora"]
    return False


def get_wsl_command(original_command: List[str]) -> List[str]:
    """
    Wrap a command to run under WSL.

    Parameters
    ----------
    original_command : List[str]
        The original command to wrap.

    Returns
    -------
    List[str]
        The command wrapped for WSL execution.
    """
    return ["wsl"] + original_command


def fix_cross_os_compatibility(project_path: str, os_info: OSInfo) -> None:
    """
    Apply automatic fixes for cross-OS compatibility.

    - Linux/macOS: Ensure shell scripts are executable.
    - All: Warn about path separator issues if detected.
    """
    from pathlib import Path

    root = Path(project_path)
    
    # 1. Ensure shell scripts are executable on Unix-like systems
    if os_info.os in [OperatingSystem.LINUX, OperatingSystem.MACOS]:
        shell_scripts = list(root.glob("**/*.sh")) + list(root.glob("**/scripts/*"))
        for script in shell_scripts:
            if script.is_file():
                try:
                    subprocess.run(["chmod", "+x", str(script)], check=True, capture_output=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass

    # 2. Check for potential path issues (e.g., hardcoded backslashes in non-Windows)
    # This is more of a warning than a fix as we shouldn't rewrite user code.
    if os_info.os != OperatingSystem.WINDOWS:
        # Just a placeholder for future logic if we decide to be more aggressive
        pass