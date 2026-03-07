import subprocess
import os

project_dir = "/vercel/share/v0-project/scripts/devenv-tool"
os.makedirs(project_dir, exist_ok=True)

subprocess.run(["uv", "init", "--bare", project_dir], check=True)
os.chdir(project_dir)
subprocess.run(["uv", "add", "typer", "rich"], check=True)
print("Setup complete")
