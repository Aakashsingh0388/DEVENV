"""
Allow invocation via ``python -m devenv``.

This module simply delegates to the Typer CLI app defined in ``cli.py``.
"""

from devenv.cli import app

app()
