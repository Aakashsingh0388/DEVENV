#!/bin/bash
set -e
cd /vercel/share/v0-project/scripts/devenv-tool
uv init --bare .
uv add typer rich
echo "DEVENV project initialized successfully."
