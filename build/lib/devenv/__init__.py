"""
DEVENV -- Automatic Project Environment Setup & Dependency Installer

A production-grade CLI tool that scans a developer's project directory,
detects the programming language and package manager in use, verifies
that the required runtime is available, manages environment files,
detects Docker configurations, performs security checks, and installs
dependencies automatically.

Supported ecosystems:
    Node.js, Python, Go, Rust, Java (Maven/Gradle), PHP, Ruby,
    .NET, Terraform, Docker

Commands:
    devenv scan      -- Scan and report project structure
    devenv install   -- Install dependencies for detected projects
    devenv doctor    -- Comprehensive health check (runtimes, services, docker)
    devenv run       -- Start the project's dev server or main process
    devenv info      -- Display detailed project metadata
    devenv summary   -- Quick project summary with all key information

Features:
    - Multi-project / monorepo support
    - Service detection (PostgreSQL, Redis, MongoDB, Kafka, etc.)
    - Smart dev server detection and startup
    - Comprehensive project health checks
    - Docker and Docker Compose integration

The package exposes a Typer-based CLI app via :pydata:`cli.app`.
"""

__version__ = "2.1.0"
__app_name__ = "devenv"
