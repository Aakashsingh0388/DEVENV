"""
dev_server.py -- Development server detection and startup.

Responsibility:
    After dependencies are installed, detect how to start the project's
    development server and offer to launch it for the user.

Detection strategies:
    1. **package.json scripts** - Check for ``dev``, ``start``, ``serve`` scripts.
    2. **Framework-specific files** - Detect Next.js, Django, Flask, FastAPI, etc.
    3. **Entry point files** - Look for ``main.py``, ``app.py``, ``index.js``, etc.
    4. **Makefiles** - Check for ``make dev`` or ``make run`` targets.

The module provides both detection and execution functionality, with
interactive prompting for user confirmation.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.prompt import Confirm

from .utils import console


@dataclass
class DevServerCommand:
    """
    A potential command to start the development server.

    Attributes
    ----------
    command:
        The command as a list of arguments.
    description:
        Human-readable description of what this command does.
    priority:
        Lower numbers = higher priority (more specific/preferred).
    framework:
        The framework or tool this command is for.
    """
    command: List[str]
    description: str
    priority: int = 10
    framework: str = "Unknown"

    @property
    def command_str(self) -> str:
        """Return the command as a single string."""
        return " ".join(self.command)


@dataclass
class DevServerDetectionResult:
    """
    Complete result of development server detection.

    Attributes
    ----------
    commands:
        List of detected server commands, sorted by priority.
    recommended:
        The recommended command to use (first in sorted list).
    language:
        Primary language/runtime for the project.
    """
    commands: List[DevServerCommand] = field(default_factory=list)
    language: str = "Unknown"

    @property
    def recommended(self) -> Optional[DevServerCommand]:
        """Return the recommended (highest priority) command."""
        if self.commands:
            return sorted(self.commands, key=lambda c: c.priority)[0]
        return None

    @property
    def has_commands(self) -> bool:
        """True if any start commands were detected."""
        return len(self.commands) > 0


def _parse_package_json_scripts(project_root: Path) -> Dict[str, str]:
    """
    Extract scripts from package.json.
    """
    scripts: Dict[str, str] = {}
    package_json = project_root / "package.json"

    if not package_json.is_file():
        return scripts

    try:
        content = package_json.read_text(encoding="utf-8", errors="ignore")

        # Find scripts section
        scripts_match = re.search(
            r'"scripts"\s*:\s*\{([^}]*)\}',
            content,
            re.DOTALL
        )

        if scripts_match:
            scripts_block = scripts_match.group(1)
            # Parse individual scripts
            script_pattern = re.compile(r'"(\w+)"\s*:\s*"([^"]*)"')
            for match in script_pattern.finditer(scripts_block):
                scripts[match.group(1)] = match.group(2)

    except (OSError, IOError):
        pass

    return scripts


def _detect_nodejs_commands(project_root: Path) -> List[DevServerCommand]:
    """
    Detect Node.js development server commands.
    """
    commands: List[DevServerCommand] = []
    scripts = _parse_package_json_scripts(project_root)

    # Priority order for npm scripts
    script_priorities = {
        "dev": 1,
        "start:dev": 2,
        "serve": 3,
        "start": 4,
        "watch": 5,
    }

    # Detect package manager
    if (project_root / "pnpm-lock.yaml").exists():
        pm = "pnpm"
    elif (project_root / "yarn.lock").exists():
        pm = "yarn"
    elif (project_root / "bun.lockb").exists():
        pm = "bun"
    else:
        pm = "npm"

    # Check for common dev scripts
    for script_name, priority in script_priorities.items():
        if script_name in scripts:
            script_content = scripts[script_name]
            
            # Determine framework from script content
            framework = "Node.js"
            if "next" in script_content:
                framework = "Next.js"
            elif "vite" in script_content:
                framework = "Vite"
            elif "nuxt" in script_content:
                framework = "Nuxt"
            elif "gatsby" in script_content:
                framework = "Gatsby"
            elif "react-scripts" in script_content:
                framework = "Create React App"
            elif "vue-cli" in script_content or "vue" in script_content:
                framework = "Vue CLI"
            elif "angular" in script_content or "ng " in script_content:
                framework = "Angular"
            elif "nest" in script_content:
                framework = "NestJS"
            elif "express" in script_content:
                framework = "Express"

            if pm == "npm":
                cmd = ["npm", "run", script_name] if script_name != "start" else ["npm", "start"]
            else:
                cmd = [pm, script_name] if pm in ("yarn", "bun") else [pm, "run", script_name]

            commands.append(DevServerCommand(
                command=cmd,
                description=f"Run '{script_name}' script ({script_content[:50]}...)" if len(script_content) > 50 else f"Run '{script_name}' script ({script_content})",
                priority=priority,
                framework=framework,
            ))

    # Check for framework-specific entry points
    if (project_root / "next.config.js").exists() or (project_root / "next.config.mjs").exists():
        if "dev" not in scripts:
            commands.append(DevServerCommand(
                command=["npx", "next", "dev"],
                description="Start Next.js development server",
                priority=1,
                framework="Next.js",
            ))

    return commands


def _detect_python_commands(project_root: Path) -> List[DevServerCommand]:
    """
    Detect Python development server commands.
    """
    commands: List[DevServerCommand] = []

    # Django
    if (project_root / "manage.py").exists():
        commands.append(DevServerCommand(
            command=["python", "manage.py", "runserver"],
            description="Start Django development server",
            priority=1,
            framework="Django",
        ))

    # FastAPI with uvicorn
    for app_file in ["main.py", "app.py", "api.py"]:
        app_path = project_root / app_file
        if app_path.exists():
            try:
                content = app_path.read_text(encoding="utf-8", errors="ignore")
                if "FastAPI" in content or "fastapi" in content:
                    module_name = app_file.replace(".py", "")
                    commands.append(DevServerCommand(
                        command=["uvicorn", f"{module_name}:app", "--reload"],
                        description=f"Start FastAPI with uvicorn ({app_file})",
                        priority=1,
                        framework="FastAPI",
                    ))
                    break
            except (OSError, IOError):
                pass

    # Flask
    for app_file in ["app.py", "application.py", "wsgi.py"]:
        app_path = project_root / app_file
        if app_path.exists():
            try:
                content = app_path.read_text(encoding="utf-8", errors="ignore")
                if "Flask" in content or "flask" in content:
                    commands.append(DevServerCommand(
                        command=["flask", "run", "--reload"],
                        description=f"Start Flask development server",
                        priority=2,
                        framework="Flask",
                    ))
                    break
            except (OSError, IOError):
                pass

    # Generic Python entry points
    for entry_file in ["main.py", "app.py", "run.py", "server.py"]:
        entry_path = project_root / entry_file
        if entry_path.exists():
            # Check if it's a runnable script (has __main__ or direct execution)
            try:
                content = entry_path.read_text(encoding="utf-8", errors="ignore")
                if "__name__" in content or "if __name__" in content:
                    commands.append(DevServerCommand(
                        command=["python", entry_file],
                        description=f"Run {entry_file}",
                        priority=5,
                        framework="Python",
                    ))
            except (OSError, IOError):
                pass

    # Streamlit
    for app_file in ["app.py", "main.py", "streamlit_app.py"]:
        app_path = project_root / app_file
        if app_path.exists():
            try:
                content = app_path.read_text(encoding="utf-8", errors="ignore")
                if "streamlit" in content.lower() or "st." in content:
                    commands.append(DevServerCommand(
                        command=["streamlit", "run", app_file],
                        description=f"Start Streamlit app",
                        priority=1,
                        framework="Streamlit",
                    ))
                    break
            except (OSError, IOError):
                pass

    return commands


def _detect_go_commands(project_root: Path) -> List[DevServerCommand]:
    """
    Detect Go development server commands.
    """
    commands: List[DevServerCommand] = []

    if (project_root / "go.mod").exists():
        # Check for main.go
        if (project_root / "main.go").exists():
            commands.append(DevServerCommand(
                command=["go", "run", "main.go"],
                description="Run main.go",
                priority=1,
                framework="Go",
            ))
        elif (project_root / "cmd").is_dir():
            # Common Go project structure with cmd/
            commands.append(DevServerCommand(
                command=["go", "run", "."],
                description="Run Go project",
                priority=2,
                framework="Go",
            ))
        else:
            commands.append(DevServerCommand(
                command=["go", "run", "."],
                description="Run Go project",
                priority=3,
                framework="Go",
            ))

    return commands


def _detect_rust_commands(project_root: Path) -> List[DevServerCommand]:
    """
    Detect Rust development commands.
    """
    commands: List[DevServerCommand] = []

    if (project_root / "Cargo.toml").exists():
        commands.append(DevServerCommand(
            command=["cargo", "run"],
            description="Build and run Rust project",
            priority=1,
            framework="Rust/Cargo",
        ))
        commands.append(DevServerCommand(
            command=["cargo", "watch", "-x", "run"],
            description="Run with hot-reload (requires cargo-watch)",
            priority=2,
            framework="Rust/Cargo",
        ))

    return commands


def _detect_ruby_commands(project_root: Path) -> List[DevServerCommand]:
    """
    Detect Ruby development server commands.
    """
    commands: List[DevServerCommand] = []

    # Rails
    if (project_root / "Gemfile").exists():
        try:
            gemfile_content = (project_root / "Gemfile").read_text(encoding="utf-8", errors="ignore")
            if "rails" in gemfile_content.lower():
                commands.append(DevServerCommand(
                    command=["bundle", "exec", "rails", "server"],
                    description="Start Rails development server",
                    priority=1,
                    framework="Ruby on Rails",
                ))
        except (OSError, IOError):
            pass

    # Sinatra
    for app_file in ["app.rb", "server.rb", "main.rb"]:
        if (project_root / app_file).exists():
            commands.append(DevServerCommand(
                command=["ruby", app_file],
                description=f"Run {app_file}",
                priority=3,
                framework="Ruby",
            ))

    return commands


def _detect_php_commands(project_root: Path) -> List[DevServerCommand]:
    """
    Detect PHP development server commands.
    """
    commands: List[DevServerCommand] = []

    # Laravel
    if (project_root / "artisan").exists():
        commands.append(DevServerCommand(
            command=["php", "artisan", "serve"],
            description="Start Laravel development server",
            priority=1,
            framework="Laravel",
        ))

    # Symfony
    if (project_root / "bin" / "console").exists():
        commands.append(DevServerCommand(
            command=["symfony", "server:start"],
            description="Start Symfony development server",
            priority=1,
            framework="Symfony",
        ))

    # Generic PHP
    if (project_root / "public" / "index.php").exists():
        commands.append(DevServerCommand(
            command=["php", "-S", "localhost:8000", "-t", "public"],
            description="Start PHP built-in server",
            priority=5,
            framework="PHP",
        ))
    elif (project_root / "index.php").exists():
        commands.append(DevServerCommand(
            command=["php", "-S", "localhost:8000"],
            description="Start PHP built-in server",
            priority=5,
            framework="PHP",
        ))

    return commands


def _detect_dotnet_commands(project_root: Path) -> List[DevServerCommand]:
    """
    Detect .NET development server commands.
    """
    commands: List[DevServerCommand] = []

    # Find *.csproj files
    csproj_files = list(project_root.glob("*.csproj"))
    if csproj_files:
        commands.append(DevServerCommand(
            command=["dotnet", "run"],
            description="Run .NET project",
            priority=1,
            framework=".NET",
        ))
        commands.append(DevServerCommand(
            command=["dotnet", "watch", "run"],
            description="Run .NET project with hot-reload",
            priority=2,
            framework=".NET",
        ))

    return commands


def _detect_makefile_commands(project_root: Path) -> List[DevServerCommand]:
    """
    Detect development commands from Makefile.
    """
    commands: List[DevServerCommand] = []
    makefile = project_root / "Makefile"

    if not makefile.is_file():
        return commands

    try:
        content = makefile.read_text(encoding="utf-8", errors="ignore")
        
        # Common make targets for development
        target_priorities = {
            "dev": 1,
            "run": 2,
            "start": 3,
            "serve": 4,
            "server": 5,
        }

        for target, priority in target_priorities.items():
            # Check if target exists in Makefile
            pattern = re.compile(rf"^{target}\s*:", re.MULTILINE)
            if pattern.search(content):
                commands.append(DevServerCommand(
                    command=["make", target],
                    description=f"Run 'make {target}'",
                    priority=priority + 10,  # Lower priority than direct commands
                    framework="Make",
                ))

    except (OSError, IOError):
        pass

    return commands


def detect_dev_server(project_root: Path, language: Optional[str] = None) -> DevServerDetectionResult:
    """
    Detect available development server commands for a project.

    Parameters
    ----------
    project_root:
        Path to the project directory.
    language:
        Optional language hint from the scanner.

    Returns
    -------
    DevServerDetectionResult:
        Complete information about detected start commands.
    """
    result = DevServerDetectionResult()
    all_commands: List[DevServerCommand] = []

    # Run all detectors
    all_commands.extend(_detect_nodejs_commands(project_root))
    all_commands.extend(_detect_python_commands(project_root))
    all_commands.extend(_detect_go_commands(project_root))
    all_commands.extend(_detect_rust_commands(project_root))
    all_commands.extend(_detect_ruby_commands(project_root))
    all_commands.extend(_detect_php_commands(project_root))
    all_commands.extend(_detect_dotnet_commands(project_root))
    all_commands.extend(_detect_makefile_commands(project_root))

    # Sort by priority
    result.commands = sorted(all_commands, key=lambda c: c.priority)

    # Set primary language based on highest-priority command
    if result.recommended:
        result.language = result.recommended.framework

    return result


def prompt_start_server(
    detection: DevServerDetectionResult,
    auto_yes: bool = False,
) -> Optional[List[str]]:
    """
    Prompt the user to start the development server.

    Parameters
    ----------
    detection:
        Result from detect_dev_server.
    auto_yes:
        If True, skip confirmation and return the recommended command.

    Returns
    -------
    Optional[List[str]]:
        The selected command to run, or None if user declined.
    """
    if not detection.has_commands:
        console.print("[yellow]No development server command detected.[/yellow]")
        return None

    recommended = detection.recommended
    assert recommended is not None

    console.print()
    console.print(f"[bold cyan]Detected:[/bold cyan] {recommended.framework}")
    console.print(f"[bold cyan]Command:[/bold cyan]  {recommended.command_str}")
    console.print(f"[dim]{recommended.description}[/dim]")
    console.print()

    if auto_yes:
        return recommended.command

    proceed = Confirm.ask(
        "Start the development server?",
        default=True,
    )

    if proceed:
        return recommended.command

    return None
