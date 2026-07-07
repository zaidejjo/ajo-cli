# AJO CLI — Super Agent Architecture & Engineering Blueprint

> **Version:** 2.0.2 → 3.0.0 (Projected)  
> **Author:** zaidejjo  
> **Document Type:** Architecture & Implementation Blueprint  
> **Status:** Draft / Strategic Planning

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
   - 2.1 Codebase Audit
   - 2.2 Performance Bottleneck Catalog
   - 2.3 Architectural Debt Register
3. [Target Architecture](#3-target-architecture)
   - 3.1 Module Dependency Map
   - 3.2 Package Layout v3.0
   - 3.3 Data Flow Diagram
4. [Performance & Concurrency Overhaul](#4-performance--concurrency-overhaul)
   - 4.1 Async Core with `anyio` / `asyncio`
   - 4.2 Heavy I/O Thread Workers
   - 4.3 Native Alternative Replacements
   - 4.4 Startup Time Optimization
5. [Smart Intelligence System](#5-smart-intelligence-system)
   - 5.1 Reactive Dashboard Engine
   - 5.2 Dynamic Command Reordering
   - 5.3 Live Alerts & Nudges
6. [Advanced Scaffolding Presets](#6-advanced-scaffolding-presets)
   - 6.1 Preset Plugin Architecture
   - 6.2 REST API Preset (DRF + CORS + drf-spectacular)
   - 6.3 GraphQL API Preset (Graphene-Django + Relay)
   - 6.4 Modern Full-Stack Preset (TailwindCSS + Alpine.js / htmx)
   - 6.5 Dockerization Preset
7. [DevEx & Fallback Resilience](#7-devex--fallback-resilience)
   - 7.1 Headless / Non-Interactive Mode
   - 7.2 Terminal Capability Detection & Fallback
   - 7.3 Transactional State Management
   - 7.4 Robust Rollback & Error Recovery
8. [Phased Implementation Roadmap](#8-phased-implementation-roadmap)
   - 8.1 Milestone Table
   - 8.2 Phase 1: Performance Core
   - 8.3 Phase 2: Smart Dashboard
   - 8.4 Phase 3: Feature Presets
   - 8.5 Phase 4: DevEx & Polish
   - 8.6 Phase 5: Testing Infrastructure
9. [Risk Register & Mitigations](#9-risk-register--mitigations)
10. [Appendix: Key Technical Decisions](#10-appendix-key-technical-decisions)

---

## 1. Executive Summary

**AJO CLI** is a Django scaffolding TUI tool that compresses project setup from ~15–20 minutes of manual work into ~60 seconds of guided interaction. The current codebase (v2.0.2) has strong visual polish and a solid foundation but suffers from:

- **Sluggish startup & heavy I/O** — synchronous subprocess calls block the UI
- **Unintegrated intelligence** — the `SmartDjangoCLI` class in `detector.py` is fully written but never wired into the main `cli.py`
- **Incomplete feature surface** — Docker, GraphQL, Full-Stack presets are advertised but absent
- **No non-interactive mode** — the tool cannot be scripted or used in CI
- **Zero test coverage** — no safety net for refactoring

This blueprint defines a **five-phase re-engineering plan** to transform AJO from a visually polished prototype into a production-grade, high-performance, enterprise-ready developer tool.

---

## 2. Current State Analysis

### 2.1 Codebase Audit

| Module | Lines | Role | Health |
|---|---|---|---|
| `ajo/cli.py` | 1,133 | Main entry, UI, orchestration | ⚠️ Overloaded — God module pattern |
| `ajo/templates/django_app.py` | 595 | Project scaffold engine | ⚠️ Mixed concerns — UI + I/O + templates |
| `ajo/detector.py` | 487 | Django project analysis + SmartDjangoCLI | ⚠️ Duplicate UI spinner; SmartDjangoCLI unused |
| `ajo/backup_cli.py` | 1,134 | Full duplicate of cli.py | 🚫 Dead code — delete entirely |
| `ajo/utils.py` | 95 | Utility functions | ✅ Clean |
| `ajo/validators.py` | 135 | Name validation | ✅ Clean |
| `ajo/exceptions.py` | 25 | Exception hierarchy | ⚠️ Missing exception for State management |
| `ajo/database_manager.py` | 67 | Database config templates | ⚠️ Duplicates config in cli.py |
| `ajo/github_integration.py` | 57 | GitHub operations | ⚠️ Thin wrapper around subprocess |

### 2.2 Performance Bottleneck Catalog

| # | Location | Issue | Severity |
|---|---|---|---|
| P1 | `detector.py:_check_migrations_needed()` | Runs `uv run manage.py makemigrations --dry-run` — spins up entire Django app. Takes **2–5 seconds** per call. | 🔴 Critical |
| P2 | `detector.py:_check_unapplied_migrations()` | Runs `uv run manage.py showmigrations --plan` — same Django bootstrap cost. | 🔴 Critical |
| P3 | `cli.py:check_prerequisites()` | Three sequential `subprocess.run` calls for `uv`, `git`, `gh` each with ~50ms overhead. | 🟡 Medium |
| P4 | `cli.py:print_banner()` | `time.sleep(0.005)` per banner line — adds ~200ms unnecessary delay. | 🟢 Low |
| P5 | `cli.py:setup_github()` | Three sequential git subprocesses (`init`, `add`, `commit`) plus one `gh repo create`. | 🟡 Medium |
| P6 | `django_app.py:_run_command()` | Every `uv add`, `uv init`, `django-admin` call uses Rich Progress that doesn't update smoothly for fast commands. | 🟢 Low |
| P7 | `detector.py` | Custom spinner via `sys.stdout.write` reimplements Rich's `SpinnerColumn`. Duplicate logic. | 🟡 Medium |

### 2.3 Architectural Debt Register

| # | Debt | Location | Impact |
|---|---|---|---|
| D1 | `backup_cli.py` is a full copy of `cli.py` with `--yes` added to one `gh` command | `backup_cli.py` | Confusion; maintenance hazard |
| D2 | `SmartDjangoCLI` in `detector.py` never imported from `cli.py` | `detector.py:368` | Features exist but are invisible — wasted code |
| D3 | Banner & prereqs commented out in `cli.py:main()` | `cli.py:1037-1039` | Dead code comments |
| D4 | Duplicate database config dictionaries in `cli.py` and `database_manager.py` | Both modules | Inconsistency risk |
| D5 | Feature grid advertises Docker, GraphQL, Debug Toolbar, Shell Plus — none implemented | `cli.py:show_features()` | Misleading to users |
| D6 | `show_dashboard()` swallows all exceptions with bare `except:` | `cli.py:821` | Silent failures during debugging |
| D7 | No `argparse` / `click` — shell completion stub has non-existent `help` and `version` | `pyproject.toml`, `README.md` | Cannot pass CLI args |

---

## 3. Target Architecture

### 3.1 Module Dependency Map (After Re-engineering)

```
ajo/
├── __init__.py              # Version, metadata
├── __main__.py              # python -m ajo entry
├── cli.py                   # Lightweight entry point → router
│
├── core/                    # NEW — Core engine layer
│   ├── __init__.py
│   ├── app.py               # Application lifecycle & state
│   ├── config.py            # Centralized configuration
│   ├── exceptions.py        # Moved from ajo/exceptions.py, enhanced
│   └── constants.py         # NF icons, Theme colors (extracted from cli.py)
│
├── commands/                # NEW — Command framework
│   ├── __init__.py
│   ├── base.py              # Abstract BaseCommand
│   ├── scaffold.py          # project:scaffold command
│   ├── dashboard.py         # project:dashboard / status
│   ├── app_create.py        # app:create command
│   ├── migrate.py           # db:migrate command
│   ├── github_push.py       # github:push command
│   └── dockerize.py         # docker:init command (NEW)
│
├── detector/                # NEW — Detection subsystem (refactored)
│   ├── __init__.py
│   ├── project.py           # DjangoProjectDetector (extracted, slimmed)
│   ├── smart_cli.py         # SmartDjangoCLI (extracted, enhanced)
│   └── cache.py             # Detector state cache (NEW)
│
├── presets/                 # NEW — Preset plugin system
│   ├── __init__.py
│   ├── base.py              # AbstractPreset (NEW)
│   ├── monolith.py          # Standard Monolith preset
│   ├── rest_api.py          # REST API preset
│   ├── graphql.py           # GraphQL preset (NEW)
│   ├── fullstack.py         # Modern Full-Stack preset (NEW)
│   └── docker.py            # Docker preset (NEW)
│
├── scaffolding/             # NEW — Scaffolding engine (refactored)
│   ├── __init__.py
│   ├── engine.py            # ScaffoldEngine — orchestrates steps
│   ├── steps/               # Atomic scaffold steps
│   │   ├── __init__.py
│   │   ├── directory.py     # mkdir step
│   │   ├── uv_init.py       # uv init step
│   │   ├── deps.py          # uv add step
│   │   ├── django_start.py  # django-admin startproject / manual
│   │   ├── env.py           # .env generation
│   │   ├── gitignore.py     # .gitignore generation
│   │   ├── templates.py     # Bootstrap templates
│   │   └── cicd.py          # GitHub Actions workflow
│   └── templates/           # Jinja2 template files
│       ├── base.html.j2
│       ├── settings.py.j2
│       ├── Dockerfile.j2    # NEW
│       ├── docker-compose.yml.j2  # NEW
│       └── nginx.conf.j2    # NEW
│
├── ui/                      # NEW — UI components (extracted)
│   ├── __init__.py
│   ├── console.py           # Console singleton
│   ├── theme.py             # Theme + NF (extracted from cli.py)
│   ├── panels.py            # show_error, show_success, etc.
│   ├── progress.py          # Rich Progress wrappers
│   ├── terminal.py          # Terminal capability detection (NEW)
│   └── prompts.py           # InquirerPy wrappers (NEW)
│
├── gateway/                 # NEW — I/O gateway layer
│   ├── __init__.py
│   ├── uv.py                # uv operations via async subprocess
│   ├── git.py               # Git operations
│   └── gh.py                # GitHub CLI operations
│
├── validators.py            # Keep as-is
└── utils.py                 # Keep as-is
```

### 3.2 Package Layout v3.0

```
ajo/
├── __init__.py
├── __main__.py
├── py.typed                 # PEP 561
├── core/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── exceptions.py
│   └── constants.py
├── commands/
│   ├── __init__.py
│   ├── base.py
│   ├── scaffold.py
│   ├── dashboard.py
│   ├── app_create.py
│   ├── migrate.py
│   ├── github_push.py
│   └── dockerize.py
├── detector/
│   ├── __init__.py
│   ├── project.py
│   ├── smart_cli.py
│   └── cache.py
├── presets/
│   ├── __init__.py
│   ├── base.py
│   ├── monolith.py
│   ├── rest_api.py
│   ├── graphql.py
│   ├── fullstack.py
│   └── docker.py
├── scaffolding/
│   ├── __init__.py
│   ├── engine.py
│   ├── steps/
│   │   ├── __init__.py
│   │   ├── directory.py
│   │   ├── uv_init.py
│   │   ├── deps.py
│   │   ├── django_start.py
│   │   ├── env.py
│   │   ├── gitignore.py
│   │   ├── templates.py
│   │   └── cicd.py
│   └── templates/
│       ├── base.html.j2
│       ├── settings.py.j2
│       ├── Dockerfile.j2
│       ├── docker-compose.yml.j2
│       └── nginx.conf.j2
├── ui/
│   ├── __init__.py
│   ├── console.py
│   ├── theme.py
│   ├── panels.py
│   ├── progress.py
│   ├── terminal.py
│   └── prompts.py
├── gateway/
│   ├── __init__.py
│   ├── uv.py
│   ├── git.py
│   └── gh.py
├── validators.py
└── utils.py
```

### 3.3 Data Flow Diagram

```
User Input (TTY / args)
        │
        ▼
┌─────────────────────────────────┐
│         cli.py (main)            │
│  ┌─ argparser → mode dispatch    │
│  │  • interactive: tui_loop()    │
│  │  • headless: execute()        │
│  └─ StateManager lifecycle       │
└──────────┬──────────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐ ┌──────────┐
│ Commands  │ │ Presets   │
│ (dispatch)│ │ (config)  │
└─────┬─────┘ └─────┬────┘
      │              │
      ▼              ▼
┌──────────────────────────┐
│    ScaffoldEngine         │
│  ┌─ Step 1: mkdir         │
│  ├─ Step 2: uv init       │
│  ├─ Step 3: deps          │
│  ├─ Step 4: django_start  │
│  ├─ Step 5: env           │
│  ├─ Step 6: gitignore     │
│  ├─ Step 7: templates     │
│  └─ Step 8: cicd / docker │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│   Gateway Layer (I/O)     │
│  (async subprocesses)     │
│  uv.py | git.py | gh.py   │
└──────────────────────────┘
```

---

## 4. Performance & Concurrency Overhaul

### 4.1 Async Core with `anyio` / `asyncio`

**Problem:** Every I/O operation blocks the Rich/InquirerPy event loop, causing UI freezes.

**Solution:** Introduce an async runtime using **`anyio`** (backport-friendly, Trio/asyncio compatible) for all I/O. The main CLI function remains synchronous at the entry point but delegates to async tasks internally.

**Pattern — Async Wrapper:**

```python
# ajo/core/app.py

import anyio
from functools import wraps
from typing import TypeVar, Callable, Awaitable

T = TypeVar("T")

def async_entry(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """Decorator: run an async CLI entry point synchronously."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        return anyio.run(func, *args, **kwargs)
    return wrapper
```

**Key async operations to convert:**

| Operation | Current | Async Strategy |
|---|---|---|
| `uv add django` | `subprocess.run(...)` | `await anyio.run_process(["uv", "add", "django"])` |
| `git init` | `subprocess.run(...)` | `await anyio.run_process(["git", "init"], cwd=path)` |
| `gh repo create` | `subprocess.run(...)` | `await anyio.run_process(...)` |
| `manage.py check --deploy` | `subprocess.run(...)` | `await anyio.run_process(...)` |
| Prerequisite checks | 3 sync calls | `await asyncio.gather(check_uv(), check_git(), check_gh())` |

### 4.2 Heavy I/O Thread Workers

**Problem:** Django management commands (`makemigrations --dry-run`, `showmigrations --plan`) are inherently synchronous because they import the full Django app. We cannot make them truly async.

**Solution:** Use `anyio.to_thread.run_sync()` to offload these to a thread pool, keeping the async event loop responsive for UI updates.

**Pattern:**

```python
# ajo/detector/project.py

import anyio
from pathlib import Path

class DjangoProjectDetector:
    async def _check_migrations_needed_async(self) -> bool:
        """Thread-worker for expensive migration check."""
        result = await anyio.to_thread.run_sync(
            self._run_makemigrations_dry_run,
            limiter=anyio.CapacityLimiter(1),  # Only 1 concurrent Django process
        )
        return result

    def _run_makemigrations_dry_run(self) -> bool:
        """Synchronous subprocess — runs in thread pool."""
        import subprocess
        result = subprocess.run(
            ["uv", "run", "python", "manage.py", "makemigrations", "--dry-run"],
            capture_output=True, text=True, timeout=10,
        )
        return "No changes detected" not in result.stdout
```

**Startup flow (async):**
```
main()
  │
  ├── async: gather(
  │     check_python_version(),
  │     check_uv_installed(),
  │     check_git_installed(),
  │     check_gh_installed(),
  │   )
  │
  ├── if detector.is_django_project:
  │     async: gather(
  │       detector.project_info (fast, local),
  │       to_thread.run_sync(check_migrations),  # heavy
  │       to_thread.run_sync(check_unapplied),    # heavy
  │     )
  │     → UI updates progressively as each completes
  │
  └── → Either dashboard or new-project wizard
```

### 4.3 Native Alternative Replacements

Replace shell subprocess calls with native Python alternatives wherever possible.

| Current (subprocess) | Native Alternative | Module | Performance Gain |
|---|---|---|---|
| `uv --version` | `shutil.which("uv")` + metadata | `shutil` | ~50ms → ~0.1ms |
| `git --version` | `shutil.which("git")` | `shutil` | ~50ms → ~0.1ms |
| `gh --version` | `shutil.which("gh")` | `shutil` | ~50ms → ~0.1ms |
| `python --version` | `sys.version_info` | `sys` | ~0ms (already available) |
| `git branch --show-current` | Read `.git/HEAD` and parse ref | `pathlib` | ~30ms → ~0.5ms |
| `git status` check | Read `.git/index` mtime | `pathlib` | ~30ms → ~0.1ms |
| Check server running | `socket.connect_ex(('127.0.0.1', 8000))` | `socket` | Already native |

**Key implementation — Git branch from filesystem:**

```python
# ajo/gateway/git.py

from pathlib import Path

def get_git_branch(project_path: Path) -> str:
    """Read current git branch from filesystem (no subprocess)."""
    head_file = project_path / ".git" / "HEAD"
    if not head_file.exists():
        return "N/A"
    try:
        content = head_file.read_text().strip()
        # "ref: refs/heads/main" → "main"
        if content.startswith("ref: "):
            return content.split("/")[-1]
        # Detached HEAD: return commit hash
        return content[:7]
    except Exception:
        return "N/A"
```

### 4.4 Startup Time Optimization

**Current startup cost (estimated):** ~800ms–2.5s

**Target startup cost:** <200ms to interactive prompt

| Optimization | Estimated Savings |
|---|---|
| Remove `print_banner()` animation `time.sleep` | ~200ms |
| Parallelize prerequisite checks (async gather) | ~100ms |
| Replace subprocess for git branch with pathlib | ~30ms |
| Cache detector results for repeated `ajo` calls | ~500ms–2s |
| Lazy-load `SmartDjangoCLI` (only when inside project) | ~100ms |
| Replace `uv run manage.py` subprocess with local parsing | ~2–5s (biggest win) |

**Detection cache** (`ajo/detector/cache.py`):

```python
import json
import time
from pathlib import Path

CACHE_TTL = 30  # seconds

class DetectorCache:
    """Caches detector results to avoid repeated heavy operations."""

    @staticmethod
    def get_cache_path(project_path: Path) -> Path:
        return project_path / ".ajo_cache" / "detector_state.json"

    @staticmethod
    def load(project_path: Path) -> dict | None:
        cache_file = DetectorCache.get_cache_path(project_path)
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text())
            if time.time() - data.get("timestamp", 0) < CACHE_TTL:
                return data.get("state")
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    @staticmethod
    def save(project_path: Path, state: dict) -> None:
        cache_file = DetectorCache.get_cache_path(project_path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({
            "timestamp": time.time(),
            "state": state,
        }))
```

---

## 5. Smart Intelligence System

### 5.1 Reactive Dashboard Engine

**Current state:** `show_dashboard()` in `cli.py` builds a static table from `detector.project_info`. `SmartDjangoCLI.get_commands()` in `detector.py` has dynamic reordering logic but is never called.

**Target:** A **reactive** dashboard that:
1. Renders immediately with cached/fast data (project name, branch, venv, apps)
2. Shows a **live** spinner for slow operations (migration checks)
3. Updates the panel in-place as each slow operation completes
4. Reorders commands based on state

**Implementation — Reactive Dashboard:**

```python
# ajo/commands/dashboard.py

from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from ajo.core.constants import NF, Theme
from ajo.detector.project import DjangoProjectDetector
from ajo.detector.smart_cli import SmartDjangoCLI
from ajo.detector.cache import DetectorCache

async def show_reactive_dashboard(detector: DjangoProjectDetector) -> SmartDjangoCLI:
    """Render a live-updating dashboard panel."""
    smart_cli = SmartDjangoCLI(detector)

    with Live(auto_refresh=False, console=console) as live:
        # Phase 1: Fast data (immediate)
        phase1_data = await detector.collect_fast_info()
        dashboard = _build_dashboard_table(phase1_data)
        live.update(dashboard)
        live.refresh()

        # Phase 2: Slow data (thread worker)
        async def update_slow():
            slow_data = await detector.collect_slow_info()
            dashboard = _build_dashboard_table({**phase1_data, **slow_data})
            live.update(dashboard)
            live.refresh()

        # Phase 3: Final with smart command warnings
        final_data = await detector.collect_all()
        commands = smart_cli.get_commands()
        alerts = _extract_alerts(final_data, commands)
        dashboard = _build_dashboard_table(final_data, alerts=alerts)
        live.update(dashboard)
        live.refresh()

    return smart_cli
```

### 5.2 Dynamic Command Reordering

**Architecture for SmartDjangoCLI integration:**

```python
# ajo/detector/smart_cli.py

from dataclasses import dataclass, field
from typing import List
from ajo.core.constants import NF, Theme

@dataclass
class SmartCommand:
    name: str
    action: str
    description: str
    icon: str = ""
    priority: int = 0       # Higher = sorted first
    badge: str | None = None  # e.g., "3 pending", "needed!"
    alert_level: int = 0     # 0=normal, 1=warning, 2=critical

class SmartDjangoCLI:
    """Context-aware command provider with dynamic priority."""

    def __init__(self, detector):
        self.detector = detector

    def get_commands(self) -> List[SmartCommand]:
        info = self.detector.project_info
        commands: List[SmartCommand] = []

        # Always available
        commands.append(SmartCommand("Run Server", "runserver",
            "Start dev server", NF.SERVER, priority=50))
        commands.append(SmartCommand("Create Superuser", "createsuperuser",
            "Create admin account", NF.USER, priority=30))
        commands.append(SmartCommand("Run Tests", "test",
            "Run all tests", NF.TEST, priority=20))
        commands.append(SmartCommand("Create New App", "create_app",
            "Scaffold new app", NF.APP, priority=10))
        commands.append(SmartCommand("Django Shell", "shell",
            "Open Python shell", NF.SHELL, priority=5))
        commands.append(SmartCommand("Clear Cache", "clear_cache",
            "Remove __pycache__", NF.CACHE, priority=1))

        # Dynamic migration commands with priority boost
        if info.get("needs_migrations"):
            commands.append(SmartCommand(
                "⚠ Make Migrations",
                "makemigrations",
                "Model changes detected — run first!",
                NF.MIGRATION,
                priority=100,        # Top of list
                badge="NEEDED!",
                alert_level=2,
            ))
        else:
            commands.append(SmartCommand("Make Migrations", "makemigrations",
                "Create new migrations", NF.MIGRATION, priority=40))

        unapplied = len(info.get("unapplied_migrations", []))
        if unapplied > 0:
            commands.append(SmartCommand(
                f"⚠ Migrate ({unapplied} pending)",
                "migrate",
                f"Apply {unapplied} pending migration(s)",
                NF.DATABASE,
                priority=90,         # Second highest
                badge=f"{unapplied} pending",
                alert_level=1 if unapplied < 5 else 2,
            ))
            # Remove or demote the normal migrate entry
            commands = [c for c in commands if c.action == "migrate" and c.priority < 50]
        else:
            commands.append(SmartCommand("Migrate", "migrate",
                "Apply migrations", NF.DATABASE, priority=40))

        # Sort by priority descending
        commands.sort(key=lambda c: -c.priority)
        return commands
```

### 5.3 Live Alerts & Nudges

The dashboard should display contextual nudges:

| Condition | Nudge | Action Suggested |
|---|---|---|
| `needs_migrations` is `True` | 🔴 "Model changes detected! Run makemigrations." | Highlight "Make Migrations" command in red |
| Unapplied migrations > 0 | 🟡 "3 migrations pending. Run migrate." | Show count in badge on "Migrate" command |
| Server running on :8000 | 🟢 "Dev server is running at :8000" | Add "Open Browser" action |
| No superuser exists | ℹ️ "No admin user found. Create one?" | Offer `createsuperuser` with priority boost |
| Venv inactive | 🟡 "Virtual environment not active" | Suggest `.venv/bin/activate` |
| Ruff violations detected | 🟡 "Ruff found issues in X files" | Offer to run `ruff check --fix` |

---

## 6. Advanced Scaffolding Presets

### 6.1 Preset Plugin Architecture

**Problem:** Currently, presets are hardcoded in `DjangoProjectScaffolder.__init__()` with if-else branches. Adding a new preset requires modifying the scaffolder.

**Target:** A **plugin architecture** where each preset is a self-contained Python class that defines:
- Required dependencies (`django, djangorestframework, ...`)
- Settings additions (`INSTALLED_APPS`, `MIDDLEWARE`, `REST_FRAMEWORK`, etc.)
- Post-scaffold hooks (generate files, configure URLs)
- Docker configuration overrides

**Base class:**

```python
# ajo/presets/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Callable, Awaitable

@dataclass
class PresetManifest:
    name: str
    description: str
    category: str  # "backend", "frontend", "infra"
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)
    settings_additions: Dict[str, str] = field(default_factory=dict)
    middleware_additions: List[str] = field(default_factory=list)
    installed_apps_additions: List[str] = field(default_factory=list)

class AbstractPreset(ABC):
    """Base class for all architecture presets."""

    @property
    @abstractmethod
    def manifest(self) -> PresetManifest:
        ...

    @abstractmethod
    async def apply_settings(self, project_path: Path, settings_path: Path) -> None:
        """Inject preset-specific settings into settings.py."""
        ...

    @abstractmethod
    async def post_scaffold(self, project_path: Path, project_name: str) -> None:
        """Run any post-scaffold steps (file generation, config)."""
        ...

    async def apply_docker_overrides(self) -> Dict[str, str] | None:
        """Return Docker service overrides for this preset, or None."""
        return None
```

### 6.2 REST API Preset (DRF + CORS + drf-spectacular)

```python
# ajo/presets/rest_api.py

class RestAPIPreset(AbstractPreset):
    @property
    def manifest(self) -> PresetManifest:
        return PresetManifest(
            name="REST API Ready",
            description="DRF + CORS + Swagger/OpenAPI pre-configured",
            category="backend",
            dependencies=[
                "djangorestframework",
                "django-cors-headers",
                "drf-spectacular",
                "django-filter",
            ],
            installed_apps_additions=[
                "rest_framework",
                "corsheaders",
                "drf_spectacular",
                "django_filters",
            ],
            middleware_additions=[
                "corsheaders.middleware.CorsMiddleware",
            ],
            settings_additions={
                "CORS_ALLOW_ALL_ORIGINS": "True  # Override in production",
                "REST_FRAMEWORK": """{
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
}""",
                "SPECTACULAR_SETTINGS": """{
    'TITLE': '{project_name} API',
    'DESCRIPTION': 'Auto-generated API documentation',
    'VERSION': '1.0.0',
}""",
            },
        )

    async def apply_settings(self, project_path: Path, settings_path: Path) -> None:
        # Inject settings (handled by engine via manifest.settings_additions)
        pass

    async def post_scaffold(self, project_path: Path, project_name: str) -> None:
        urls_path = project_path / project_name / "urls.py"
        # Append drf-spectacular URLs
        spectacular_urls = """
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns += [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
"""
        with urls_path.open("a") as f:
            f.write(spectacular_urls)
```

### 6.3 GraphQL API Preset (Graphene-Django + Relay)

```python
# ajo/presets/graphql.py

class GraphQLPreset(AbstractPreset):
    @property
    def manifest(self) -> PresetManifest:
        return PresetManifest(
            name="GraphQL API",
            description="Graphene-Django + GraphiQL + Relay-ready schema",
            category="backend",
            dependencies=[
                "graphene-django",
                "django-filter",
            ],
            installed_apps_additions=[
                "graphene_django",
            ],
            settings_additions={
                "GRAPHENE": """{
    'SCHEMA': '{project_name}.schema.schema',
}""",
            },
        )

    async def post_scaffold(self, project_path: Path, project_name: str) -> None:
        # Generate schema.py
        schema_content = '''import graphene

class Query(graphene.ObjectType):
    """Root GraphQL query."""
    health = graphene.String()

    def resolve_health(self, info):
        return "OK"

schema = graphene.Schema(query=Query)
'''
        (project_path / project_name / "schema.py").write_text(schema_content)

        # Add GraphQL URL to urls.py
        urls_path = project_path / project_name / "urls.py"
        graphql_urls = '''
from graphene_django.views import GraphQLView
from django.views.decorators.csrf import csrf_exempt

urlpatterns += [
    path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True)), name="graphql"),
]
'''
        with urls_path.open("a") as f:
            f.write(graphql_urls)
```

### 6.4 Modern Full-Stack Preset (TailwindCSS + Alpine.js / htmx)

```python
# ajo/presets/fullstack.py

class FullStackPreset(AbstractPreset):
    @property
    def manifest(self) -> PresetManifest:
        return PresetManifest(
            name="Full-Stack Modern",
            description="Django + TailwindCSS + Alpine.js/htmx",
            category="fullstack",
            dependencies=[
                "django-tailwind",  # or django-tailwind-cli
                "django-htmx",
            ],
            installed_apps_additions=[
                "django_tailwind",
                "django_htmx",
            ],
            middleware_additions=[
                "django_htmx.middleware.HtmxMiddleware",
            ],
        )

    async def post_scaffold(self, project_path: Path, project_name: str) -> None:
        # Generate package.json for Tailwind CSS
        package_json = {
            "name": project_name,
            "scripts": {
                "build:css": "tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify",
                "watch:css": "tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch",
            },
            "devDependencies": {
                "tailwindcss": "^3.4.0",
            },
        }
        (project_path / "package.json").write_text(
            json.dumps(package_json, indent=2) + "\n"
        )

        # Generate tailwind.config.js
        tailwind_config = '''/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html',
  ],
  theme: { extend: {} },
  plugins: [],
}
'''
        (project_path / "tailwind.config.js").write_text(tailwind_config)

        # Generate CSS input
        css_dir = project_path / "static" / "css"
        css_dir.mkdir(parents=True, exist_ok=True)
        (css_dir / "input.css").write_text(
            "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n"
        )

        # Update base.html to include Tailwind + Alpine/htmx
        base_html = project_path / "templates" / "base.html"
        # ... rewrite template with Tailwind classes and CDN scripts
```

### 6.5 Dockerization Preset

**Multi-stage Dockerfile optimized for uv:**

```dockerfile
# Dockerfile.j2 template
# Stage 1: Build
FROM python:3.12-slim AS builder

RUN pip install uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY . .

EXPOSE 8000
CMD [".venv/bin/python", "manage.py", "runserver", "0.0.0.0:8000"]
```

**docker-compose.yml.j2:**

```yaml
version: "3.9"
services:
  django:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - .:/app
    depends_on:
      - db
      - redis

  db:
    image: postgres:16-alpine  # or mysql:8
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"
      - "8025:8025"

volumes:
  pgdata:
```

**Preset implementation:**

```python
# ajo/presets/docker.py

class DockerPreset(AbstractPreset):
    """Generates Dockerfile + docker-compose.yml. Composable with other presets."""

    @property
    def manifest(self) -> PresetManifest:
        return PresetManifest(
            name="Docker Support",
            description="Multi-stage Dockerfile + docker-compose with DB, Redis, Mailhog",
            category="infra",
            dependencies=[],
        )

    async def post_scaffold(self, project_path: Path, project_name: str) -> None:
        from ajo.scaffolding.templates import render_template
        # Render Dockerfile from Jinja2 template
        dockerfile = render_template("Dockerfile.j2", project_name=project_name)
        (project_path / "Dockerfile").write_text(dockerfile)

        # Render docker-compose
        compose = render_template("docker-compose.yml.j2",
            project_name=project_name,
            db_type=self.db_type,  # SQLite → no db service; PostgreSQL → pg; MySQL → mysql
        )
        (project_path / "docker-compose.yml").write_text(compose)

        # Render .dockerignore
        (project_path / ".dockerignore").write_text(
            ".env\n.git\n__pycache__\n*.pyc\n.venv\n"
        )
```

---

## 7. DevEx & Fallback Resilience

### 7.1 Headless / Non-Interactive Mode

**Problem:** AJO can only run interactively. Impossible to script or use in CI.

**Solution:** Add `argparse` CLI with flags that bypass all interactive prompts:

```python
# ajo/cli.py (partial)

import argparse
import sys
from pathlib import Path

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ajo",
        description="Professional Django scaffolder — Cyberpunk TUI",
        epilog="Run without arguments for interactive mode.",
    )
    parser.add_argument("--version", action="store_true",
        help="Show version and exit")
    parser.add_argument("--headless", action="store_true",
        help="Non-interactive mode (requires --name)")
    parser.add_argument("-n", "--name", type=str,
        help="Project name (required with --headless)")
    parser.add_argument("-p", "--preset", type=str,
        choices=["monolith", "rest", "graphql", "fullstack"],
        default="monolith", help="Architecture preset")
    parser.add_argument("-d", "--database", type=str,
        choices=["sqlite", "postgresql", "mysql"],
        default="sqlite", help="Database type")
    parser.add_argument("--db-name", type=str, help="Database name")
    parser.add_argument("--db-user", type=str, help="Database user")
    parser.add_argument("--db-password", type=str, help="Database password")
    parser.add_argument("--db-host", type=str, default="localhost")
    parser.add_argument("--db-port", type=str)
    parser.add_argument("-y", "--yes", action="store_true",
        help="Accept all defaults (implies --headless)")
    parser.add_argument("--no-github", action="store_true",
        help="Skip GitHub setup")
    parser.add_argument("--no-cicd", action="store_true",
        help="Skip CI/CD setup")
    parser.add_argument("--no-docker", action="store_true",
        help="Skip Docker setup")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd(),
        help="Parent directory for project")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        from ajo import __version__
        print(f"ajo v{__version__}")
        return 0

    if args.headless or args.yes:
        return headless_main(args)
    else:
        return interactive_main()
```

**Shell completion (auto-generated via `argparse` → `shtab`):**

```bash
# Add to pyproject.toml
# [tool.shtab]
# shell = "bash"
# path = "ajo.cli:build_parser"
```

```bash
# Installation in user's .zshrc:
# eval "$(ajo --completion zsh)"
```

### 7.2 Terminal Capability Detection & Fallback

**Problem:** Nerd Font icons render as garbled characters on terminals without Nerd Font support.

**Solution:** Implement a terminal capability checker that detects Nerd Font support and falls back gracefully.

```python
# ajo/ui/terminal.py

from dataclasses import dataclass
import os
import shutil
import subprocess
import re

@dataclass
class TerminalCapabilities:
    nerd_font: bool = False
    color_256: bool = True
    unicode: bool = True
    width: int = 80
    height: int = 24

def detect_capabilities() -> TerminalCapabilities:
    """Detect terminal capabilities."""
    caps = TerminalCapabilities()

    # Check TERM_PROGRAM
    term_program = os.environ.get("TERM_PROGRAM", "")
    term = os.environ.get("TERM", "")

    # Nerd Font detection (heuristic)
    caps.nerd_font = _detect_nerd_font(term_program, term)

    # Color support
    if term in ("dumb", "unknown"):
        caps.color_256 = False

    # Unicode
    caps.unicode = os.environ.get("LANG", "").upper() in (
        "", "C", "POSIX"
    ) is False

    # Size
    try:
        size = shutil.get_terminal_size()
        caps.width = size.columns
        caps.height = size.lines
    except Exception:
        pass

    return caps

def _detect_nerd_font(term_program: str, term: str) -> bool:
    """Heuristic Nerd Font detection."""
    # Known good terminals
    nerd_font_terminals = {
        "kitty", "alacritty", "wezterm", "foot", "ghostty",
        "iTerm2", "tmux", "warp", "tabby",
    }
    if term_program.lower() in nerd_font_terminals:
        return True

    # VS Code terminal usually supports Nerd Fonts via settings
    if "vscode" in term_program.lower():
        return True

    # Check for Nerd Font in font config
    try:
        result = subprocess.run(
            ["fc-list", ":lang=en"],
            capture_output=True, text=True, timeout=1,
        )
        if "nerd" in result.stdout.lower() or "nerdfont" in result.stdout.lower():
            return True
    except Exception:
        pass

    return False
```

**Fallback icon system:**

```python
# ajo/ui/theme.py

from ajo.ui.terminal import detect_capabilities, TerminalCapabilities

_caps: TerminalCapabilities | None = None

def get_caps() -> TerminalCapabilities:
    global _caps
    if _caps is None:
        _caps = detect_capabilities()
    return _caps

class IconSystem:
    """Provides icons with automatic Nerd Font → Unicode fallback."""

    NF_MAP = {
        # (nerd_font_char, unicode_fallback)
        "check": ("󰄬", "✓"),
        "error": ("󰅖", "✗"),
        "warning": ("󰀪", "⚠"),
        "django": ("󰌾", "D"),
        "python": ("", "Py"),
        "github": ("󰊤", "GH"),
        "docker": ("󰡨", "D"),
        "server": ("󰌈", "■"),
        "database": ("󰆼", "🗄"),
        "migration": ("󰏘", "⇅"),
        "app": ("󰣆", "A"),
        "model": ("󰤤", "M"),
        "folder": ("󰉋", "📁"),
        "rocket": ("󱐋", "→"),
        "gear": ("󰒓", "⚙"),
        "user": ("󰙲", "👤"),
        "test": ("󰙨", "🧪"),
        "shell": ("󱓞", ">$"),
        "cache": ("󰩺", "∅"),
        "arrow": ("󰁔", "→"),
        "lock": ("󰌾", "🔒"),
    }

    @classmethod
    def get(cls, key: str) -> str:
        """Return best icon for current terminal."""
        nf_char, fallback = cls.NF_MAP.get(key, ("?", "?"))
        if get_caps().nerd_font:
            return nf_char
        return fallback
```

### 7.3 Transactional State Management

**Problem:** During scaffolding, if step 5/8 fails, the project directory is left in a broken state. Current `rollback_project()` only handles `CommandExecutionError` inside `scaffold()`.

**Solution:** Implement a formal **transactional state machine** that tracks each step and rolls back on any failure:

```python
# ajo/scaffolding/engine.py

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import List, Callable, Awaitable

class StepStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMMITTED = auto()
    ROLLED_BACK = auto()
    FAILED = auto()

@dataclass
class ScaffoldStep:
    name: str
    execute: Callable[[], Awaitable[bool]]
    rollback: Callable[[], Awaitable[None]] = lambda: None
    status: StepStatus = StepStatus.PENDING
    critical: bool = True  # If True, failure triggers full rollback

class ScaffoldEngine:
    """Transactional scaffold orchestrator."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.steps: List[ScaffoldStep] = []
        self.committed: List[ScaffoldStep] = []
        self._rolled_back = False

    def add_step(self, step: ScaffoldStep) -> "ScaffoldEngine":
        self.steps.append(step)
        return self

    async def execute_all(self) -> bool:
        """Execute all steps. On failure, rollback committed steps."""
        for step in self.steps:
            step.status = StepStatus.RUNNING
            try:
                success = await step.execute()
                if not success:
                    if step.critical:
                        await self._rollback_all(step.name)
                        return False
                    step.status = StepStatus.FAILED
                else:
                    step.status = StepStatus.COMMITTED
                    self.committed.append(step)
            except Exception as e:
                step.status = StepStatus.FAILED
                if step.critical:
                    await self._rollback_all(f"{step.name}: {e}")
                    return False

        return True

    async def _rollback_all(self, reason: str) -> None:
        self._rolled_back = True
        # Rollback in reverse order
        for step in reversed(self.committed):
            try:
                await step.rollback()
                step.status = StepStatus.ROLLED_BACK
            except Exception:
                pass  # Best-effort rollback
```

### 7.4 Robust Rollback & Error Recovery

**Enhanced rollback in `ajo/utils.py`:**

```python
# ajo/utils.py (enhanced)

import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ajo")

class RollbackManager:
    """Structured rollback with logging and recovery suggestions."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.snapshot_path: Optional[Path] = None
        self.created_dirs: list[Path] = []
        self.created_files: list[Path] = []

    def take_snapshot(self) -> None:
        """Save list of existing files before scaffold starts."""
        if self.project_path.exists():
            self.snapshot_path = self.project_path
            # We don't actually copy — we track what we create

    def track_creation(self, path: Path) -> None:
        if path.is_dir():
            self.created_dirs.append(path)
        else:
            self.created_files.append(path)

    def rollback(self, reason: str, fatal: bool = True) -> None:
        """Remove all tracked files/dirs in reverse order."""
        logger.warning(f"Rolling back: {reason}")
        # Remove files first (reverse order)
        for f in reversed(self.created_files):
            try:
                if f.exists():
                    f.unlink()
                    logger.info(f"  Removed: {f}")
            except Exception as e:
                logger.error(f"  Failed to remove {f}: {e}")

        # Remove dirs (reverse order)
        for d in reversed(self.created_dirs):
            try:
                if d.exists():
                    shutil.rmtree(d)
                    logger.info(f"  Removed: {d}")
            except Exception as e:
                logger.error(f"  Failed to remove {d}: {e}")

        # If project path is now empty, remove it
        if self.project_path.exists() and not any(self.project_path.iterdir()):
            try:
                self.project_path.rmdir()
                logger.info(f"  Removed empty project dir: {self.project_path}")
            except Exception as e:
                logger.error(f"  Failed to remove project dir: {e}")
```

---

## 8. Phased Implementation Roadmap

### 8.1 Milestone Table

| Phase | Name | Duration | Output | Dependencies |
|---|---|---|---|---|
| **P0** | Cleanup & Prep | 2 days | Delete dead code, extract constants, add `argparse` | None |
| **P1** | Performance Core | 5 days | Async gateway, parallel prereqs, native git branch, detection cache | P0 |
| **P2** | Smart Dashboard | 5 days | Reactive Live dashboard, SmartDjangoCLI integration, live alerts | P1 |
| **P3** | Feature Presets | 7 days | Preset plugin system, GraphQL, Full-Stack, Docker presets | P1 |
| **P4** | DevEx & Polish | 5 days | Headless mode, terminal detection, enhanced rollback, completion | P1–P3 |
| **P5** | Testing | 5 days | Pytest suite for validators, detector, scaffolder, presets | P1–P4 |

**Total:** ~29 working days

### 8.2 Phase 0 — Cleanup & Preparation (2 days)

**Actions:**

1. **Delete `backup_cli.py`** — dead code
2. **Remove dead comments** in `cli.py:1037-1039` (commented-out banner and prereqs)
3. **Create `ajo/core/constants.py`** — extract `NF` class and `Theme` class from `cli.py`
4. **Create `ajo/ui/theme.py`** — move icon/theme code, import from `core/constants.py`
5. **Add `argparse`** to `cli.py` with `--version` flag (wire to `__version__`)
6. **Rename `DetectorCache` integration point** in `detector.py`
7. **Add `ajo/core/exceptions.py`** — move from `ajo/exceptions.py` and add `StateError`, `RollbackError` (enhanced), `PresetError`

**Deliverables:**
- [x] `backup_cli.py` deleted
- [x] `cli.py` cleaned of dead code
- [x] `ajo/core/constants.py` created with `NF` + `Theme`
- [x] `ajo/ui/theme.py` created, imports from `core/constants.py`
- [x] `argparse --version` working
- [x] Exception hierarchy expanded

### 8.3 Phase 1 — Performance Core (5 days)

**Actions:**

1. **Create `ajo/gateway/` package** with async subprocess wrappers:
   - `ajo/gateway/uv.py` — `async def uv_add(...)`, `async def uv_init(...)`, `async def uv_run(...)`
   - `ajo/gateway/git.py` — `get_git_branch()` (pathlib), `async def git_init(...)`, `async def git_add(...)`, `async def git_commit(...)`
   - `ajo/gateway/gh.py` — `async def gh_create_repo(...)`

2. **Refactor `detector.py`** into `ajo/detector/` package:
   - `project.py` — `DjangoProjectDetector` with async methods
   - `smart_cli.py` — `SmartDjangoCLI` (extracted, enhanced with `SmartCommand` dataclass)
   - `cache.py` — `DetectorCache` with TTL

3. **Parallelize prerequisite checks** in `cli.py:main()`:
   ```python
   async def check_all_prerequisites():
       results = await anyio.gather(
           check_python(),
           check_uv(),
           check_git(),
           check_gh(),
       )
       return all(results)
   ```

4. **Replace `subprocess` for git branch** with `pathlib`-based `.git/HEAD` parsing

5. **Add `DetectorCache`** to avoid re-running heavy checks within the TTL window

6. **Remove `print_banner()` slow animation** — keep the ASCII art but render instantly

7. **De-duplicate database config** — keep only `database_manager.py`, remove inline dicts from `cli.py`

**Deliverables:**
- [x] Async gateway package created
- [x] Detector package refactored with async + cache
- [x] Prerequisite checks run in parallel
- [x] Git branch read from filesystem
- [x] Startup time <200ms to interactive prompt

### 8.4 Phase 2 — Smart Dashboard (5 days)

**Actions:**

1. **Wire `SmartDjangoCLI` into `cli.py:main()`** — replace inline `get_smart_commands()`

2. **Create reactive dashboard** using `rich.live.Live`:
   - Phase 1: Render fast data immediately
   - Phase 2: Show spinner for slow checks (migration state)
   - Phase 3: Update panel with final state + alerts

3. **Implement command priority system** using `SmartCommand.priority`:
   - Migration-needed warnings at top
   - Pending migration counts in badges
   - Color-coded alert levels

4. **Add nudges panel** below the dashboard:
   - Missing superuser → "Create one?"
   - Pending migrations → "Apply now"
   - Server not running → "Start dev server"

5. **Remove standalone `SmartDjangoCLI.execute_command()`** — route through `cli.py:run_command()` instead (avoids duplicate code)

**Deliverables:**
- [x] `SmartDjangoCLI` fully integrated
- [x] Reactive Live dashboard rendering
- [x] Dynamic command ordering with priority
- [x] Contextual alert nudges displayed

### 8.5 Phase 3 — Feature Presets (7 days)

**Actions:**

1. **Create `ajo/presets/` package** with `base.py` containing `AbstractPreset` and `PresetManifest`

2. **Extract existing preset logic** from `DjangoProjectScaffolder` into `ajo/presets/monolith.py`

3. **Implement `ajo/presets/rest_api.py`** — full DRF + CORS + drf-spectacular preset with post-scaffold URL injection

4. **Implement `ajo/presets/graphql.py`** — Graphene-Django schema generation + GraphiQL URL

5. **Implement `ajo/presets/fullstack.py`** — TailwindCSS config + Alpine.js/htmx middleware + base template rewrite

6. **Implement `ajo/presets/docker.py`** — multi-stage Dockerfile + docker-compose.yml with database/redis/mailhog

7. **Refactor `DjangoProjectScaffolder`** into `ajo/scaffolding/engine.py`:
   - `ScaffoldEngine` with transactional step execution
   - Individual step classes in `ajo/scaffolding/steps/`
   - Jinja2 template rendering for generated files

8. **Update `cli.py:show_features()`** — remove advertising of unimplemented features (or implement them)

**Deliverables:**
- [x] Preset plugin system with `AbstractPreset` base class
- [x] GraphQL preset implemented
- [x] Full-Stack preset implemented
- [x] Docker preset implemented
- [x] ScaffoldEngine with transactional steps
- [x] Feature grid accurately reflects implemented features

### 8.6 Phase 4 — DevEx & Polish (5 days)

**Actions:**

1. **Full headless mode** via `argparse`:
   - `ajo --headless --name myproject --preset rest --db postgresql --yes`
   - `ajo -n myproject -y` (shorthand)
   - Validate project name in headless mode (no interactive correction, fail fast)

2. **Terminal capability detection** (`ajo/ui/terminal.py`):
   - Nerd Font detection
   - Unicode fallback system
   - Width-aware panel sizing

3. **Enhanced `RollbackManager`** in `ajo/utils.py`:
   - Track created files/dirs during scaffold
   - Reverse-order cleanup on failure
   - Log rollback steps for debugging

4. **Shell completion** via `argparse` + `shtab`:
   - Generate bash/zsh completion scripts
   - Document in README

5. **Keyboard interrupt hardening**:
   - During `uv add deps`: catch gracefully, suggest retry
   - During `git push`: don't leave half-pushed repos
   - During scaffold: trigger rollback

6. **Improved error reporting**:
   - Structured JSON error output in headless mode
   - Report file paths and suggestions
   - Add `--verbose` flag for debug logging

**Deliverables:**
- [x] Headless/non-interactive mode fully functional
- [x] Terminal capability detection with Unicode fallback
- [x] Enhanced `RollbackManager`
- [x] Shell completion scripts
- [x] Robust error handling in all scaffold paths

### 8.7 Phase 5 — Testing Infrastructure (5 days)

**Actions:**

1. **pytest configuration** in `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   python_files = ["test_*.py"]
   ```

2. **Unit tests for validators** (`tests/test_validators.py`):
   - `ProjectNameValidator.validate()` — valid names, invalid names, edge cases
   - `ProjectNameValidator.sanitize()` — all transformation rules
   - `AppNameValidator.validate()` — valid/invalid/reserved

3. **Unit tests for detector** (`tests/test_detector.py`):
   - `DjangoProjectDetector._find_manage_py()` with temp directories
   - `DjangoProjectDetector._extract_project_name()` with mock manage.py files
   - `DjangoProjectDetector._check_venv()` with env var manipulation
   - `DjangoProjectDetector._get_git_branch()` with fake `.git/HEAD`

4. **Unit tests for scaffolder** (`tests/test_scaffolder.py`):
   - `DjangoProjectScaffolder._get_database_settings()` — SQLite, PostgreSQL, MySQL
   - `DjangoProjectScaffolder._get_env_variables()` — all DB types
   - `DjangoProjectScaffolder._create_manual_django_project()` with temp dir

5. **Unit tests for gateway** (`tests/test_gateway.py`):
   - `get_git_branch()` with mock `.git` directories
   - Mock `shutil.which` for prerequisite checks

6. **Integration test** (`tests/test_integration.py`):
   - Full scaffold in temp directory (SQLite, monolith, no GitHub)
   - Verify directory structure, files, settings content
   - Verify `uv run manage.py check` passes

7. **CI configuration** for the tool itself:
   - GitHub Actions running tests on PR
   - Ruff lint + format check
   - Coverage report

**Deliverables:**
- [x] pytest configured
- [x] Validator tests (10+ test cases)
- [x] Detector tests (10+ test cases)
- [x] Scaffolder tests (10+ test cases)
- [x] Gateway tests (5+ test cases)
- [x] Integration tests (2+ test cases)
- [x] CI workflow for ajo-cli itself

---

## 9. Risk Register & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Async migration breaks existing sync code paths** | Medium | High | Keep `cli.py` synchronous entry point; wrap async ops with `anyio.run()`. Write integration tests first. |
| **uv process incompatibility with `anyio.run_process`** | Low | High | Use `asyncio.create_subprocess_exec` with a compatibility shim; fallback to `subprocess.run` in `to_thread.run_sync`. |
| **Nerd Font detection is unreliable** | High | Low | Use heuristic (known terminals + fontconfig). Add user opt-out with `--no-icons` flag. Document Nerd Font requirement. |
| **Preset plugin API too abstract — hard to implement new presets** | Medium | Medium | Ship reference implementations (rest, graphql, docker). Keep `AbstractPreset` minimal — only 2 abstract methods. |
| **ScaffoldEngine step order is hard to override** | Low | Low | Use a builder pattern: `engine.add_step(...)` in specific order per preset. Presets can define custom step lists. |
| **Cannot test GitHub integration locally** | Medium | Medium | Use `unittest.mock.patch` to mock `gateway/gh.py`. Implement a `--dry-run` flag that prints instead of executing. |

---

## 10. Appendix: Key Technical Decisions

### A. Dependencies

| Package | Use | Version | Status |
|---|---|---|---|
| `rich` | TUI rendering panels, tables, progress | >=13.0.0 | Already present |
| `InquirerPy` | Interactive prompts, select, confirm | >=0.3.4 | Already present |
| `anyio` | Async runtime for concurrent I/O | >=4.0 | **NEW** — replaces manual threading |
| `Jinja2` | Template rendering for generated files | >=3.0 | **NEW** — replaces inline f-strings |
| `shtab` | Auto-generate shell completions from argparse | >=1.0 | **NEW** |
| `pytest` | Test framework | >=8.0 | **NEW** (dev dependency) |
| `pytest-asyncio` | Async test support | >=0.23 | **NEW** (dev dependency) |

### B. Python Version Support

| Python | Status | Reason |
|---|---|---|
| 3.10 | ✅ Minimum | `from __future__ import annotations` |
| 3.11 | ✅ Target | `anyio` compatibility |
| 3.12 | ✅ Target | CI matrix |
| 3.13 | ✅ Support | uv support |

### C. File Naming Conventions

- **Presets:** `ajo/presets/<name>.py` — snake_case matching preset CLI arg
- **Steps:** `ajo/scaffolding/steps/<name>.py` — snake_case matching step name
- **Templates:** `ajo/scaffolding/templates/<name>.j2` — Jinja2 extension for all templates
- **Gateway:** `ajo/gateway/<tool>.py` — matches tool name (`uv`, `git`, `gh`)

### D. Error Codes

| Code | Meaning | When |
|---|---|---|
| 0 | Success | Normal exit |
| 1 | Generic error | Unexpected failure |
| 10 | Prerequisite failure | Missing Python/uv/Git |
| 11 | Validation error | Invalid project/app name |
| 20 | Scaffold failure | Project creation failed |
| 21 | Rollback failure | Cleanup after scaffold failure |
| 30 | GitHub failure | Repo creation/push failed |
| 40 | Preset error | Preset class raised an error |
| 130 | User interrupt | Ctrl+C / KeyboardInterrupt |

---

## Implementation Order (Quick Reference)

```
Week 1-2:
  └── P0: Cleanup (2d) → P1: Performance Core (5d)

Week 3-4:
  └── P2: Smart Dashboard (5d) → P3a: Preset Plugin + REST/GraphQL (4d)

Week 5-6:
  └── P3b: Full-Stack + Docker (3d) → P4: DevEx Polish (5d)

Week 7:
  └── P5: Testing Infrastructure (5d)
```

---

*This document is a living blueprint. Update as implementation reveals new insights. All code snippets are illustrative patterns — actual implementation may vary to accommodate edge cases discovered during development.*
