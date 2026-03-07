"""
End-to-end test for DEVENV.

Creates temporary project fixtures, runs the scanner/detector/environment
modules, and validates the results.
"""

import sys
import os
import tempfile
import importlib
from pathlib import Path

# ── Ensure the devenv package is importable ─────────────────────────────────
DEVENV_TOOL_DIR = "/vercel/share/v0-project/scripts/devenv-tool"
if DEVENV_TOOL_DIR not in sys.path:
    sys.path.insert(0, DEVENV_TOOL_DIR)

# Force-import after path manipulation
import devenv.scanner as scanner_mod
import devenv.detector as detector_mod
import devenv.environment as env_mod
import devenv.display as display_mod

scan_directory = scanner_mod.scan_directory
detect_all = detector_mod.detect_all
check_runtime = env_mod.check_runtime
print_banner = display_mod.print_banner
print_detection_summary = display_mod.print_detection_summary

from rich.console import Console

console = Console()

# ── Helpers ─────────────────────────────────────────────────────────────────

def section(name):
    console.print(f"[bold]--- Test: {name} ---[/bold]")

def ok(msg):
    console.print(f"[green]PASS[/green]: {msg}\n")

# ── Tests ───────────────────────────────────────────────────────────────────

def test_banner():
    section("Banner")
    print_banner()
    ok("Banner rendered.")


def test_scan_node_project():
    section("Scan Node.js project")
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir) / "package.json"
        pkg.write_text('{"name": "test", "dependencies": {}}')
        lock = Path(tmpdir) / "yarn.lock"
        lock.write_text("")

        results = scan_directory(tmpdir)
        assert "Node.js" in results, f"Expected 'Node.js' in scan results, got {list(results.keys())}"
        console.print(f"  Scanned files: {[str(p.name) for paths in results.values() for p in paths]}")

        detections = detect_all(results)
        assert len(detections) == 1
        d = detections[0]
        assert d.language == "Node.js"
        assert d.package_manager == "yarn"
        assert d.install_command == ["yarn", "install"]
        console.print(f"  Detected: {d.language} / {d.package_manager}")
        ok("Node.js project correctly detected.")


def test_scan_python_project():
    section("Scan Python project")
    with tempfile.TemporaryDirectory() as tmpdir:
        req = Path(tmpdir) / "requirements.txt"
        req.write_text("flask\nrequests\n")

        results = scan_directory(tmpdir)
        assert "Python" in results

        detections = detect_all(results)
        assert len(detections) == 1
        d = detections[0]
        assert d.language == "Python"
        assert d.package_manager == "pip"
        assert "requirements.txt" in " ".join(d.install_command)
        console.print(f"  Detected: {d.language} / {d.package_manager}")
        ok("Python project correctly detected.")


def test_scan_go_project():
    section("Scan Go project")
    with tempfile.TemporaryDirectory() as tmpdir:
        gomod = Path(tmpdir) / "go.mod"
        gomod.write_text("module example.com/hello\ngo 1.21\n")

        results = scan_directory(tmpdir)
        assert "Go" in results

        detections = detect_all(results)
        d = detections[0]
        assert d.language == "Go"
        assert d.package_manager == "go modules"
        console.print(f"  Detected: {d.language} / {d.package_manager}")
        ok("Go project correctly detected.")


def test_scan_rust_project():
    section("Scan Rust project")
    with tempfile.TemporaryDirectory() as tmpdir:
        cargo = Path(tmpdir) / "Cargo.toml"
        cargo.write_text('[package]\nname = "hello"\nversion = "0.1.0"\n')

        results = scan_directory(tmpdir)
        assert "Rust" in results

        detections = detect_all(results)
        d = detections[0]
        assert d.language == "Rust"
        assert d.package_manager == "cargo"
        console.print(f"  Detected: {d.language} / {d.package_manager}")
        ok("Rust project correctly detected.")


def test_scan_java_maven():
    section("Scan Java/Maven project")
    with tempfile.TemporaryDirectory() as tmpdir:
        pom = Path(tmpdir) / "pom.xml"
        pom.write_text("<project></project>")

        results = scan_directory(tmpdir)
        assert "Java" in results

        detections = detect_all(results)
        d = detections[0]
        assert d.language == "Java"
        assert d.package_manager == "maven"
        console.print(f"  Detected: {d.language} / {d.package_manager}")
        ok("Java/Maven project correctly detected.")


def test_scan_php_project():
    section("Scan PHP project")
    with tempfile.TemporaryDirectory() as tmpdir:
        composer = Path(tmpdir) / "composer.json"
        composer.write_text('{"require": {}}')

        results = scan_directory(tmpdir)
        assert "PHP" in results

        detections = detect_all(results)
        d = detections[0]
        assert d.language == "PHP"
        assert d.package_manager == "composer"
        console.print(f"  Detected: {d.language} / {d.package_manager}")
        ok("PHP project correctly detected.")


def test_scan_ruby_project():
    section("Scan Ruby project")
    with tempfile.TemporaryDirectory() as tmpdir:
        gemfile = Path(tmpdir) / "Gemfile"
        gemfile.write_text('source "https://rubygems.org"\ngem "rails"\n')

        results = scan_directory(tmpdir)
        assert "Ruby" in results

        detections = detect_all(results)
        d = detections[0]
        assert d.language == "Ruby"
        assert d.package_manager == "bundler"
        console.print(f"  Detected: {d.language} / {d.package_manager}")
        ok("Ruby project correctly detected.")


def test_multi_language():
    section("Multi-language project")
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "package.json").write_text("{}")
        (Path(tmpdir) / "requirements.txt").write_text("flask")
        (Path(tmpdir) / "go.mod").write_text("module x\ngo 1.21\n")

        results = scan_directory(tmpdir)
        detections = detect_all(results)

        langs = {d.language for d in detections}
        assert langs == {"Node.js", "Python", "Go"}, f"Got {langs}"
        console.print(f"  Detected languages: {langs}")
        ok("Multi-language detection works.")


def test_empty_directory():
    section("Empty directory")
    with tempfile.TemporaryDirectory() as tmpdir:
        results = scan_directory(tmpdir)
        assert len(results) == 0
        ok("Empty directory returns nothing.")


def test_runtime_check():
    section("Runtime check (Python)")
    status = check_runtime("Python")
    assert status.installed is True
    assert status.version is not None
    console.print(f"  Python runtime: {status.version}")
    ok("Runtime check works.")


def test_display_summary():
    section("Display summary")
    print_detection_summary(
        language="Node.js",
        package_manager="npm",
        dependency_file="package.json",
        runtime_installed=True,
        runtime_version="v20.11.0",
    )
    ok("Summary rendered.")


def test_node_pnpm_detection():
    section("pnpm detection priority")
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "package.json").write_text("{}")
        (Path(tmpdir) / "pnpm-lock.yaml").write_text("")

        results = scan_directory(tmpdir)
        detections = detect_all(results)
        d = detections[0]
        assert d.package_manager == "pnpm", f"Expected pnpm, got {d.package_manager}"
        console.print(f"  Detected: {d.package_manager}")
        ok("pnpm priority is correct.")


def test_pipenv_detection():
    section("Pipenv detection")
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "Pipfile").write_text("[packages]\nflask = '*'\n")

        results = scan_directory(tmpdir)
        detections = detect_all(results)
        d = detections[0]
        assert d.package_manager == "pipenv", f"Expected pipenv, got {d.package_manager}"
        console.print(f"  Detected: {d.package_manager}")
        ok("Pipenv correctly detected.")


# ── Runner ──────────────────────────────────────────────────────────────────

tests = [
    test_banner,
    test_scan_node_project,
    test_scan_python_project,
    test_scan_go_project,
    test_scan_rust_project,
    test_scan_java_maven,
    test_scan_php_project,
    test_scan_ruby_project,
    test_multi_language,
    test_empty_directory,
    test_runtime_check,
    test_display_summary,
    test_node_pnpm_detection,
    test_pipenv_detection,
]

passed = 0
failed = 0

for test_fn in tests:
    try:
        test_fn()
        passed += 1
    except Exception as exc:
        console.print(f"[bold red]FAIL[/bold red]: {test_fn.__name__} -- {exc}\n")
        failed += 1

console.print("=" * 60)
total = passed + failed
console.print(f"[bold]Results: {passed}/{total} passed[/bold]", end="")
if failed:
    console.print(f" [red]({failed} failed)[/red]")
else:
    console.print(" [green](all passed)[/green]")
