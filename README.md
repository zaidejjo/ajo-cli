# 🚀 AJO - Professional Django Scaffolder

[![PyPI version](https://img.shields.io/pypi/v/ajo.svg)](https://pypi.org/project/ajo/)
[![Python Version](https://img.shields.io/pypi/pyversions/ajo.svg)](https://python.org)
[![AUR Version](https://img.shields.io/aur/version/ajo)](https://aur.archlinux.org/packages/ajo)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **AJO** (Advanced Java Orchestrator) - The ultimate Django project generator with Cyberpunk TUI

## ✨ Features

- 🚀 **Lightning Fast** - Powered by `uv` package manager
- 🎨 **Stunning TUI** - Cyberpunk theme with Nerd Font icons
- 🗄️ **Multi-Database** - SQLite, PostgreSQL, MySQL support
- 🐙 **GitHub Integration** - Auto-create repos and push
- 🔄 **CI/CD Ready** - GitHub Actions with Ruff linter
- 📦 **Multiple Apps** - Create unlimited Django apps
- 🔒 **Security First** - Auto .env with SECRET_KEY

## 📦 Installation

### Option 1: pip (Any OS)

```bash
# with pipx (recommended)
pipx install ajo-cli

# whith pip
pip install ajo-cli
# Or with uv (recommended)
uv tool install ajo-cli
```

### Option 2: AUR (Arch linux)

```bash
# Install globally
yay -S ajo-cli

# Using paru
paru -S ajo-cli

```




# Create new Django project
ajo

# Inside Django project, run smart commands
ajo
# Then choose from: runserver, makemigrations, migrate, etc.



# completions/ajo.bash
_ajo_completion() {
    local cur=${COMP_WORDS[COMP_CWORD]}
    COMPREPLY=($(compgen -W "help version" -- $cur))
}
complete -F _ajo_completion ajo
