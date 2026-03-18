# 🚀 DevEnv

### Automatic Development Environment Setup

DevEnv is an intelligent **command-line interface (CLI)** tool that automatically prepares development environments for software projects.

It detects the project language, installs dependencies, configures the environment, and prepares the project to run — all with a **single command**.

DevEnv eliminates the classic developer problem:

> “It works on my machine.”

With DevEnv, developers can **clone a repository and start coding in seconds** — without manual setup.

---

# 📚 Table of Contents

* Overview
* Features
* Demo
* Installation
* Quick Start
* Supported Languages
* Commands
* How It Works
* Developer Workflow
* Cross Platform Support
* Why DevEnv
* Roadmap
* Contributing
* License
* Author

---

# 🧠 Overview

Modern projects often require multiple runtimes, dependencies, and environment configurations. Setting these up manually is time-consuming and error-prone.

DevEnv solves this by automatically detecting project requirements and configuring the environment for you.

It is designed for:

* Developers onboarding to new repositories
* Teams needing consistent environments
* Open-source projects improving contributor experience

---

# ✨ Features

## ⚡ One Command Setup

Prepare the entire development environment instantly:

```bash
devenv setup
```

---

## 🧠 Smart Runtime Detection

Automatically detects required runtimes:

* Python
* Node.js
* Go

If missing, DevEnv **guides or assists** in installing them.

---

## 📦 Automatic Dependency Installation

Detects dependency files and installs packages using the correct package manager.

| Language | Dependency File  | Package Manager |
| -------- | ---------------- | --------------- |
| Python   | requirements.txt | pip             |
| Python   | pyproject.toml   | pip / poetry    |
| Node.js  | package.json     | npm             |
| Go       | go.mod           | go              |

---

## 🚀 Intelligent Project Execution

Automatically detects how to run your project.

| Framework | Command          |
| --------- | ---------------- |
| Flask     | flask run        |
| FastAPI   | uvicorn main:app |
| Node.js   | npm start        |
| Next.js   | npm run dev      |

---

## 💻 Cross Platform Support

Works seamlessly on:

* Windows
* macOS
* Linux

Handles OS-specific issues like:

* Permissions
* Shell compatibility
* Runtime differences

---

# 🎬 Demo

```bash
devenv setup
```

Example output:

```
✔ Detected: Python project
✔ Checking runtime...
✔ Installing dependencies...
✔ Environment ready
✔ Suggested command: flask run
```

---

# 📦 Installation

Install from PyPI:

```bash
pip install smart-devenv
```

Verify installation:

```bash
devenv --version
```

---

# ⚡ Quick Start

```bash
git clone https://github.com/example/project.git
cd project

devenv setup
```

DevEnv will:

1. Detect project language
2. Check runtimes
3. Install dependencies
4. Fix compatibility issues
5. Suggest run command

---

# 🌐 Supported Languages

Currently supported:

* Python
* Node.js
* Go

Supported files:

```
requirements.txt
pyproject.toml
package.json
go.mod
```

---

# 🛠 Commands

## devenv setup

```bash
devenv setup [OPTIONS]
```

| Option        | Description     |
| ------------- | --------------- |
| -p, --path    | Project path    |
| -n, --dry-run | Preview actions |
| -y, --yes     | Skip prompts    |

---

## devenv scan

```bash
devenv scan
```

Detects project structure.

---

## devenv install

```bash
devenv install
```

Installs dependencies automatically.

---

## devenv run

```bash
devenv run
```

Runs project using detected command.

---

## devenv doctor

```bash
devenv doctor
```

Checks system environment.

---

## devenv info

```bash
devenv info
```

Shows project details.

---

## devenv summary

```bash
devenv summary
```

Quick overview of project.

---

# ⚙️ How It Works

DevEnv follows these steps:

1. Scan project files
2. Detect programming language
3. Identify dependency files
4. Select package manager
5. Install dependencies
6. Suggest or run project

---

# 🔄 Developer Workflow

```bash
pip install smart-devenv

git clone <repo>
cd <repo>

devenv setup
devenv run
```

---

# 🤔 Why DevEnv

### Without DevEnv

* Manual runtime setup
* Manual dependency installation
* OS compatibility issues
* Finding correct run command

### With DevEnv

```bash
devenv setup
```

Everything is ready automatically.

---

# 🗺 Roadmap

* Java support
* Docker integration
* Virtual environment auto-setup
* AI-based project analysis

---

# 🤝 Contributing

Contributions are welcome!

1. Fork the repo
2. Create a branch
3. Commit changes
4. Open a pull request

---

# 📄 License

MIT License

---

# 👨‍💻 Author

**Aakash Birendra Singh**

GitHub:
(https://github.com/Aakashsingh0388)

LinkedIn:
(https://www.linkedin.com/in/aakash-singh-7b8416318)

