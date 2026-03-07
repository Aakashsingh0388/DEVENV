import subprocess
import sys
import os

# Install typer and rich via pip
subprocess.run([sys.executable, "-m", "pip", "install", "typer[all]", "rich"], check=True)
print("Dependencies installed successfully.")
