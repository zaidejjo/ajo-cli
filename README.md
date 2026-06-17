<p align="center">
  <img src="https://img.shields.io/pypi/v/ajo-cli?color=%2300f2fe&style=flat-square" alt="PyPI">
  <img src="https://img.shields.io/pypi/pyversions/ajo-cli?color=%234facfe&style=flat-square" alt="Python">
  <img src="https://img.shields.io/aur/version/ajo-cli?color=%23f355da&style=flat-square" alt="AUR">
  <img src="https://img.shields.io/github/license/zaidejjo/ajo-cli?color=%2300ffcc&style=flat-square" alt="License">
</p>

<h1 align="center">AJO</h1>
<p align="center"><em>Professional Django Scaffolder with Cyberpunk TUI</em></p>

<p align="center">
  <a href="https://zaidejjo.github.io/ajo-cli/"><strong>🌐 Explore the Interactive Showcase & Web Simulator</strong></a>
</p>

<p align="center">
  <b>ajo</b> is an interactive CLI tool that generates production-ready Django projects
  with a beautiful cyberpunk-themed terminal UI. Pick your architecture, database,
  and add-on modules — ajo handles the rest.
</p>

<p align="center">
  <code>ajo</code> &nbsp;·&nbsp;
  <code>ajo --headless --name myproject -p rest-api -d postgresql</code> &nbsp;·&nbsp;
  <code>ajo --theme dracula</code>
</p>

---

## Features

| | Feature | |
|---|---|---|
| 🗄️ | **Multi-Database Support** — PostgreSQL, MySQL, SQLite | 🐙 |
| **GitHub Integration** — Auto repo creation & push | 🔄 |
| **CI/CD with Ruff** — GitHub Actions pipeline | 🔒 |
| **.env Security** — Auto-generated secrets | 📦 |
| **Multiple Apps** — Scaffold any number of apps | 🧪 |
| **Testing** — pytest with coverage & factory-boy | 🐳 |
| **Docker Support** — Dockerfile + Compose + Redis + Mailhog | 🎨 |
| **Bootstrap 5 Themes** — Pre-built UI themes | 🛠️ |
| **Django Shell Plus** — Enhanced shell | 🔍 |
| **Debug Toolbar** — Dev debugging tools | 🐙 |

---

## 🌐 Interactive Showcase & Web Simulator

Experience AJO directly in your browser! We have built a dedicated single-page showcase website featuring:
- **Interactive Terminal Simulator**: Watch a live, animated simulation of the `ajo` scaffolding workflow.
- **Live Diagnostics Simulator**: Run a simulated scan of a Django project and watch the self-healing Diagnostic Engine fix issues with one click.
- **Theme Switcher**: Cycle the site's accent colors between `Cyberpunk Cyan`, `Dracula Purple`, and `Monochromatic` to preview AJO's visual themes.
- **Tabbed Installation Guide**: Easily copy installation commands for `pipx`, `uv`, `AUR`, or source.

👉 **[Visit the Interactive Showcase Website](https://zaidejjo.github.io/ajo-cli/)**

---

## Architecture Presets

Choose the foundation that fits your stack:

| Preset | Key | Stack |
|---|---|---|
| **Standard Monolith** | `monolith` | Django + Bootstrap 5 + HTMX |
| **REST API Ready** | `rest-api` | DRF + JWT + CORS + Swagger/OpenAPI |
| **Ninja API** | `ninja-api` | django-ninja + Pydantic + Swagger UI |
| **GraphQL API** | `graphql-api` | Graphene + Relay + GraphiQL IDE |
| **Docker** | `docker` | Multi-stage Dockerfile + Compose (PostgreSQL, Redis, Mailhog) |

Each preset generates a complete Django project with:
- `manage.py`, settings, URLs, WSGI/ASGI
- `.env` with auto-generated `SECRET_KEY`
- `.gitignore` for Django best practices
- `pyproject.toml` with `uv` dependency management

The REST API, Ninja API, and GraphQL API presets are **model-aware** — they auto-generate serializers, viewsets, routers, and API endpoints by scanning your Django models via AST analysis.

---

## Add-on Modules

Layer optional features on top of any preset:

| Add-on | Key | What it adds |
|---|---|---|
| **Auth & Users** | `auth` | JWT auth (SimpleJWT), custom `User` model with bio/avatar, registration, login/signup templates, preset-aware REST or Ninja endpoints |
| **Caching & Performance** | `cache` | Redis caching (`django-redis`), DB connection pooling (`django-db-connection-pool`), `django-debug-toolbar`, demo cached view |
| **Security Hardening** | `security` | Brute-force protection (`django-axes`), TOTP 2FA (`django-otp`), CSP headers (`django-csp`), HSTS/XSS/CSRF hardening |
| **Testing Infrastructure** | `testing` | pytest + pytest-django, coverage (fail-under 80%), factory-boy, per-app test directories, auto-generated model factories and API tests |

Select add-ons interactively with `<space>` during the scaffold flow, or pass them via `--addons`:

```bash
ajo --addons auth cache testing
```

---

## Themes

AJO ships with three visual themes. Pass `--theme` to switch:

```
ajo --theme cyberpunk          # Neon cyan (default)
ajo --theme dracula            # Dracula purple/pink
ajo --theme monochromatic      # Clean greyscale/blue
ajo --theme mono               # Alias for monochromatic
```

Themes are applied to both the Rich terminal output and all InquirerPy interactive prompts. Terminal colour depth (TrueColor, 256, 16) is auto-detected.

---

## Installation

### pip / pipx (any OS)

```bash
# Recommended — isolated environment
pipx install ajo-cli

# With uv (also isolated)
uv tool install ajo-cli

# With pip (global)
pip install ajo-cli
```

### AUR (Arch Linux)

```bash
yay -S ajo-cli
paru -S ajo-cli
```

### From source

```bash
git clone https://github.com/zaidejjo/ajo-cli.git
cd ajo-cli
uv sync
ajo --version
```

---

## Quickstart

### Create a new Django project (interactive)

```bash
ajo
```

Follow the prompts:
1. Choose a **project name**
2. Pick an **architecture preset** (Monolith, REST API, Ninja API, GraphQL API, Docker)
3. Select a **database** (SQLite, PostgreSQL, MySQL)
4. Optionally enable **add-on modules** (auth, cache, security, testing)
5. Review the scaffold preview
6. Confirm — ajo creates the project, installs dependencies via `uv`, initialises git, and optionally creates a GitHub repo

### One-shot (headless)

```bash
ajo --headless --name myproject \
    --preset rest-api \
    --database postgresql \
    --addons auth cache testing \
    --no-github
```

Flags:

| Flag | Default | Description |
|---|---|---|
| `-n, --name` | — | Project name |
| `-p, --preset` | `monolith` | Architecture preset |
| `-d, --database` | `sqlite` | Database type |
| `-y, --yes` | — | Accept all defaults (implies `--headless`) |
| `--addons` | — | Add-on modules (space-separated) |
| `--no-github` | — | Skip GitHub repo creation |
| `--no-cicd` | — | Skip CI/CD pipeline setup |
| `--output-dir` | `.` | Parent directory for the project |
| `--theme` | `cyberpunk` | Visual theme |
| `--headless` | — | Non-interactive mode |

### Smart CLI — manage existing Django projects

Run `ajo` inside an existing Django project directory:

```bash
cd myproject
ajo
```

AJO detects your Django project and presents a **context-aware menu** of commands:

| Command | When it appears |
|---|---|
| Run Server | Always |
| Create Superuser | When no superuser exists (highlighted as urgent) |
| Run Tests | Always |
| Create App | Always |
| Django Shell | Always |
| Make Migrations | When model changes detected (highlighted as urgent) |
| Apply Migrations | When unapplied migrations exist (highlighted as urgent) |
| Fix Ruff Issues | When Ruff reports problems (highlighted as urgent) |
| Clear Cache | Always |
| Run Diagnostics | Always — scans for misconfigurations with auto-fix |

The smart menu also shows a **live dashboard** with project metadata, branch, virtualenv status, server status, migration state, and Ruff lint status — all updating in real time.

---

## Persistent Configuration

On the first interactive run, AJO asks:

```
? Do you use a Nerd Font in your terminal? (y/N)
```

Your answer is saved to `~/.config/ajo/config.json`:

```json
{
  "version": 1,
  "nerd_fonts": true,
  "theme": null,
  "updated_at": "2026-06-17T12:00:00+00:00"
}
```

- `nerd_fonts`: Controls whether Nerd Font icons or text fallbacks are used across the entire TUI
- `theme`: Reserved for future persistent theme preference

**Override precedence:**
1. `$NERD_FONTS` environment variable
2. Saved `config.json` value
3. Auto-detection (terminal emulator heuristics)
4. Default: text fallbacks

---

## Docker

The **Docker preset** generates a production-ready container setup:

```bash
ajo --preset docker
```

Creates:
- **Dockerfile** — Multi-stage build with uv caching, `python manage.py collectstatic`
- **docker-compose.yml** — `web` service + PostgreSQL/MySQL + Redis + Mailhog
- **.dockerignore** — venv, cache, git

Optionally integrates with Celery worker.

---

## Diagnostics

AJO includes a self-healing diagnostic engine that scans your Django project for common issues and offers **one-click auto-fixes**:

| Check | Auto-fix |
|---|---|
| Missing contrib apps in `INSTALLED_APPS` | Adds them |
| Missing `ALLOWED_HOSTS` | Appends `["*"]` |
| Hardcoded `DEBUG=True` in production | Prompts to fix |
| Missing or placeholder `SECRET_KEY` | Generates a secure 50-char key |
| Missing admin URL in root URLconf | Wires `admin/` path |
| Duplicate migration prefixes | Renames with next available number |

Run diagnostics from the smart CLI menu or directly.

---

## Development

### Setup

```bash
git clone https://github.com/zaidejjo/ajo-cli.git
cd ajo-cli
uv sync
```

### Run tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=ajo

# Specific file
uv run pytest tests/test_config.py -v
```

### Project structure

```
ajo/
├── cli.py                 # CLI parser, TUI, features, scaffold flow
├── core/
│   ├── config.py          # Persistent config manager (~/.config/ajo/)
│   ├── constants.py       # NF icons (Nerd Font + fallbacks), Theme, ThemeVariant
│   ├── app.py             # async_entry decorator
│   └── exceptions.py      # AjoError hierarchy (5 subclasses)
├── ui/
│   ├── theme.py           # ThemeEngine (3 themes, colour-depth adapt), FileTreePreview
│   ├── capabilities.py    # Terminal detection (Nerd Fonts, TrueColor, Sixel, etc.)
│   ├── fuzzy.py           # Interactive fuzzy finder
│   ├── keyboard.py        # Keyboard event handling
│   └── progress.py        # Async progress manager
├── presets/
│   ├── monolith.py        # Standard Monolith preset
│   ├── rest_api.py        # REST API Ready preset
│   ├── ninja_api.py       # Ninja API preset
│   ├── graphql_api.py     # GraphQL API preset
│   ├── docker.py          # Docker preset
│   └── addons/            # Auth, Cache, Security, Testing add-ons
├── scaffolding/
│   └── engine.py          # Transactional scaffold engine with rollback
├── templates/
│   └── django_app.py      # Django project file generator
├── detector/
│   ├── project.py         # DjangoProjectDetector (fast + slow async scans)
│   ├── smart_cli.py       # SmartDjangoCLI (context-aware commands)
│   ├── cache.py           # Filesystem cache with TTL
│   └── ast_analyzer.py    # AST-based model/relationship scanner
├── gateway/               # Async subprocess wrappers (uv, git, gh)
└── validators.py          # Project/app name validators + DiagnosticEngine
```

---

## Requirements

- **Python 3.10+**
- **uv** — the Astral Python package manager (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **git** — optional, for version control
- **GitHub CLI (`gh`)** — optional, for GitHub repo creation

---

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  <sub>Built with</sub>
  <br>
  <code>🐍 Python 3.10+</code> &nbsp;
  <code>🦄 Django 5.0+</code> &nbsp;
  <code>⚡ uv</code> &nbsp;
  <code>🦀 Ruff</code>
</p>
