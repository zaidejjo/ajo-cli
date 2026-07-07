# Plan: Professional CLI Development Roadmap

**File:** `.opencode/plans/06_professional_cli_roadmap.md`
**Version:** 1.0
**Created:** 2026-07-07
**Language:** English

---

## Table of Contents

1. [Core Features & Functions](#1-core-features--functions)
2. [User & Developer Experience](#2-user--developer-experience)
3. [Architecture & Performance](#3-architecture--performance)
4. [Phased Roadmap](#4-phased-roadmap)

---

## 1. Core Features & Functions

| Category | Feature | Status | Priority | Approach |
|---|---|---|---|---|
| **Updates** | `ajo upgrade` — self-update mechanism | Missing | High | Check PyPI JSON API; `pip install --upgrade ajo-cli` |
| **Completions** | Shell completions (bash/zsh/fish) | Missing | High | `shtab` — generates from argparse automatically |
| **Config** | Env-var override + per-project `.ajo/config.toml` | Partial | Medium | `python-dotenv` (dep exists) + `tomllib` (stdlib 3.11+) |
| **Offline** | Offline mode flag + degraded UI when no network | Partial | Medium | Extend `detector/cache.py` with `diskcache` or `sqlite3` |
| **Logging** | Structured logging with `-v`/`-vv`/`--log-file` | Missing | Low | `structlog` or `logging` (stdlib) |
| **Telemetry** | Opt-in anonymous usage stats | Missing | Low | `posthog` or local file — off by default |
| **Error Reporting** | Crash dump to `~/.config/ajo/crash/` | Missing | Low | `traceback` (stdlib) + `sys.excepthook` |
| **Changelog** | `ajo changelog` | Missing | Low | `importlib.metadata` + cached PyPI releases |
| **Doctor** | `ajo doctor` — system health check | Missing | Low | Extend existing `prereqs.py` |
| **Plugins** | 3rd-party plugin discovery via entry-points | Missing | Future | `importlib.metadata.entry_points()` |
| **Typo Correction** | Fuzzy typo correction for mistyped subcommands | Missing | High | `difflib.get_close_matches()` over argparse subcommands |
| **Environment** | Virtual environment / uv / pipx detection for correct subprocess delegation | Missing | High | Detect `VIRTUAL_ENV`, `UV_ACTIVE`, `PIPX_HOME`; route package commands accordingly |
| **Silent Updates** | Disable background update check via config or env var | Missing | Medium | `check_updates: false` in `config.json` or `AJO_NO_UPDATE_CHECK=1` |

### Auto-Update Design

```python
# ajo/core/updater.py
def check_for_updates() -> tuple[str, bool]:
    from importlib.metadata import version
    import urllib.request, json
    current = version("ajo-cli")
    url = "https://pypi.org/pypi/ajo-cli/json"
    resp = json.loads(urllib.request.urlopen(url).read())
    latest = resp["info"]["version"]
    return latest, latest != current

def upgrade() -> subprocess.CompletedProcess:
    import subprocess, sys
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "ajo-cli"]
    )
```

- Check on startup in background thread (non-blocking)
- Cache result for 24h to avoid rate-limiting
- Show notification in dashboard if update available
- Never auto-upgrade without explicit `ajo upgrade`

### Silent Update Configuration

Users in air-gapped networks, CI pipelines, or enterprise environments must be able to disable all outbound network checks:

```python
# In ajo/core/config.py — ConfigManager schema
DEFAULT_CONFIG: dict = {
    "check_updates": True,          # master toggle for background check
    "nerd_font": None,              # existing
    "theme": "cyberpunk",           # existing
    "telemetry": False,             # future
}

# In ajo/core/updater.py — gated check
import os
def _should_check_updates(config: dict) -> bool:
    if os.environ.get("AJO_NO_UPDATE_CHECK") in ("1", "true", "yes"):
        return False
    return config.get("check_updates", True)
```

| Mechanism | Precedence | Example |
|---|---|---|
| `AJO_NO_UPDATE_CHECK=1` env var | Overrides everything | `AJO_NO_UPDATE_CHECK=1 ajo` |
| `check_updates: false` in `~/.config/ajo/config.json` | Per-user persistent | `ajo config set check_updates false` |
| Config file absent (default) | Checks enabled | First-run default |

### Typo Correction Design

```python
# ajo/core/typo_correction.py (new)
from __future__ import annotations
import difflib

SUGGESTION_CUTOFF: float = 0.4   # similarity ratio floor

def suggest_command(bad: str, candidates: list[str]) -> str | None:
    """Return closest match, or None if nothing is close enough."""
    matches = difflib.get_close_matches(bad, candidates, n=1, cutoff=SUGGESTION_CUTOFF)
    return matches[0] if matches else None

def format_suggestion(bad: str, good: str) -> str:
    """Return user-facing message: 'Did you mean "scaffold'?" """
    return f"Did you mean \x1b[1m{good}\x1b[22m? (not \x1b[3m{bad}\x1b[23m)"
```

Integration point: in `cli.py` after argparse parses unknown args, before showing standard error:

```python
# In ajo/cli.py — near parse_known_args() or post-parse dispatch
from ajo.core.typo_correction import suggest_command, format_suggestion
import sys

def _dispatch(argv: list[str] | None = None) -> None:
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        candidates = list(parser._subparsers._group_actions[0].choices.keys())
        suggestion = suggest_command(unknown[0], candidates)
        if suggestion:
            print(format_suggestion(unknown[0], suggestion), file=sys.stderr)
            sys.exit(2)
        # else fall through to standard argparse error
    ...
```

If the user types `ajo scafold`, output:
```
$ ajo scafold
Did you mean "scaffold"? (not "scafold")
```

### Graceful SIGINT / Ctrl+C Handling Design

```python
# ajo/core/signals.py (new)
from __future__ import annotations
import signal
import sys
from typing import Any, Callable

_rollback_handler: Callable[[], Any] | None = None

def register_rollback_handler(fn: Callable[[], Any]) -> None:
    global _rollback_handler
    _rollback_handler = fn

def _sigint_handler(signum: int, frame: Any) -> None:
    """Handle Ctrl+C: close progress UI, run rollback, exit with code 130."""
    from ajo.ui.progress import close_progress  # lazy import
    close_progress()
    if _rollback_handler is not None:
        print("\n⚠ Interrupted — cleaning up...", file=sys.stderr)
        try:
            _rollback_handler()
        except Exception as exc:
            print(f"  Rollback error: {exc}", file=sys.stderr)
    sys.exit(130)

def install_signal_handlers() -> None:
    signal.signal(signal.SIGINT, _sigint_handler)
    signal.signal(signal.SIGTERM, _sigint_handler)  # same handler for SIGTERM
```

Integration with ScaffoldEngine:

```python
# In ajo/commands/scaffold.py — wiring
from ajo.core.signals import install_signal_handlers, register_rollback_handler
from ajo.scaffolding.engine import ScaffoldEngine

engine = ScaffoldEngine(...)
install_signal_handlers()
register_rollback_handler(lambda: engine.rollback_manager.rollback_all())

await engine.execute()  # Ctrl+C → rollback → exit 130
```

Handling for interactive prompts (InquirerPy already handles SIGINT gracefully by raising `KeyboardInterrupt` — just ensure this propagates to our handler instead of raw crash).

### Environment Detection Design

```python
# ajo/core/environment.py (new)
from __future__ import annotations
import os
import sys
from enum import Enum, auto
from pathlib import Path

class PythonEnvironment(Enum):
    GLOBAL = auto()       # pip install --system
    VIRTUALENV = auto()   # source .venv/bin/activate
    UV = auto()           # uv run / uv tool
    PIPX = auto()         # pipx install
    CONDA = auto()        # conda install
    UNKNOWN = auto()

def detect_environment() -> PythonEnvironment:
    if os.environ.get("PIPX_ACTIVE") or str(Path(sys.executable)).startswith(
        str(Path.home() / ".local" / "pipx")
    ):
        return PythonEnvironment.PIPX
    if os.environ.get("UV_ACTIVE"):
        return PythonEnvironment.UV
    if os.environ.get("CONDA_PREFIX"):
        return PythonEnvironment.CONDA
    if os.environ.get("VIRTUAL_ENV") or sys.prefix != sys.base_prefix:
        return PythonEnvironment.VIRTUALENV
    return PythonEnvironment.GLOBAL

def install_command() -> list[str]:
    """Return the correct 'install package' command for the current env."""
    env = detect_environment()
    if env == PythonEnvironment.UV:
        return ["uv", "add"]
    if env in (PythonEnvironment.PIPX, PythonEnvironment.GLOBAL):
        return [sys.executable, "-m", "pip", "install"]
    # virtualenv or conda — use sys.executable's pip
    return [sys.executable, "-m", "pip", "install"]

def run_command(args: list[str]) -> list[str]:
    """Return appropriate 'run a command' prefix (uv run vs direct)."""
    env = detect_environment()
    if env == PythonEnvironment.UV:
        return ["uv", "run"]
    return args  # direct execution
```

Integration with `ajo doctor`:

```
ajo doctor
├── ✓ Python 3.13.0 (>=3.10)
├── ✓ Environment: virtualenv (.venv)
├── ✓ uv 0.6.0
├── ✓ git 2.45.0
├── ...
```

### Shell Completions

```
ajo completion bash  > /etc/bash_completion.d/ajo
ajo completion zsh   > /usr/local/share/zsh/site-functions/_ajo
ajo completion fish  > ~/.config/fish/completions/ajo.fish
```

Using `shtab`: no manual maintenance — reads argparse definition at build time.

```python
# ajo/commands/completions.py
def run(shell: str) -> None:
    import shtab
    parser = build_parser()  # from cli.py
    print(shtab.complete(parser, shell=shell))
```

### Doctor Command Design

```
ajo doctor
├── ✓ Python 3.13.0 (>=3.10)
├── ✓ uv 0.6.0
├── ✓ git 2.45.0
├── ✓ gh 2.60.0
├── ✓ pip 25.0
├── ✓ Nerd Font: installed
├── ✓ TrueColor: supported
└── ✓ Config: ~/.config/ajo/config.json (valid)
```

Reuses existing `prereqs.py` + adds config validation, terminal detection checks.

---

## 2. User & Developer Experience

### Already Strong

- Rich TUI with 3 themes (cyberpunk, dracula, mono)
- InquirerPy interactive prompts (select, confirm, text, checkbox, fuzzy)
- Keyboard navigation, fuzzy finding
- Async progress bars with live rendering
- Smart reactive dashboard in existing Django projects
- Self-healing diagnostics with auto-fix

### Next-Level Improvements

| Area | Improvement | Effort | Details |
|---|---|---|---|
| **NO_COLOR** | `--no-color` / `NO_COLOR` env var | Low | Standard: `zavadil.no_color` |
| **Verbosity** | `-v` (info), `-vv` (debug), `-q` (silent) | Low | `logging` level mapping |
| **Exit Codes** | Standardize all: 0=ok, 1=error, 2=usage, 130=SIGINT | Low | Already partial (11 for validation) |
| **CI Detection** | Auto-disable spinners when `CI=true` or piped | Low | `sys.stdout.isatty()` check |
| **Dry Run** | `--dry-run` — show what would happen | Low | ScaffoldEngine already has transactional steps |
| **Help** | Subcommand-specific help with examples | Low | argparse `epilog` per subcommand |
| **Piping** | Strip ANSI when output is piped | Medium | Rich `Console(force_terminal=False)` |
| **ETA** | Estimated time remaining on installs | Medium | `ajo/ui/progress.py` enhancement |
| **Error Context** | Show file + line on error (Ruff-style) | Medium | Already possible via DiagnosticEngine |
| **Typo Correction** | `ajo scafold` → "Did you mean scaffold?" | Low | `difflib.get_close_matches()` on unknown subcommand |
| **SIGINT Grace** | Ctrl+C triggers RollbackManager + exits 130 without half-files | Medium | Signal handler in `ajo/core/signals.py` |
| **Undo** | `ajo undo` — reverse last scaffold | Medium | RollbackManager exists, needs persistent journal |

### `NO_COLOR` Implementation

```python
# In ajo/core/constants.py
import os, sys

def supports_color() -> bool:
    force = os.environ.get("FORCE_COLOR")
    if force is not None:
        return force not in ("0", "false", "")
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return True
```

### Verbosity System

```python
# ajo/core/logging.py (new)
import logging, sys

LOG_LEVEL_MAP = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}

def setup_logging(verbosity: int = 0, log_file: str | None = None) -> None:
    level = LOG_LEVEL_MAP.get(verbosity, logging.DEBUG)
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=level, handlers=handlers,
        format="%(levelname)s: %(message)s",
    )
```

---

## 3. Architecture & Performance

### Current State

- **Async core** with `asyncio` — event loop managed by `core/app.py`
- **Lazy imports** — <50ms startup via `core/lazy_imports.py`
- **Gateway layer** — all subprocess via `gateway/` async wrappers
- **Plugin registry** — `PRESET_REGISTRY` + `ADDON_REGISTRY` with decorator registration
- **Transactional scaffold** — `ScaffoldEngine` + `RollbackManager`
- **Terminal detection** — `ui/capabilities.py` + `ui/terminal_detector.py`
- **Reactive UI** — `rich.live.Live` for dashboard
- **Configuration** — `ConfigManager` at `~/.config/ajo/config.json`

### Proposed Directory Evolution

The primary architectural change is extracting `cli.py`'s subcommands into dedicated files to prevent god-module regrowth:

```
ajo/
├── cli.py                    # Thin entry point (argparse + dispatch only)
├── commands/                 # NEW — subcommand modules
│   ├── __init__.py
│   ├── scaffold.py           # extracted from cli.py
│   ├── doctor.py             # ajo doctor
│   ├── upgrade.py            # ajo upgrade
│   ├── changelog.py          # ajo changelog
│   ├── completions.py        # ajo completion bash/zsh/fish
│   ├── diagnostics.py        # ajo diagnostics (move from cli.py)
│   └── telemetry.py          # ajo telemetry on|off|status
├── core/                     # enhanced — add new files below
│   ├── typo_correction.py    # NEW — fuzzy subcommand correction
│   ├── environment.py        # NEW — venv/uv/pipx/conda detection
│   └── signals.py            # NEW — SIGINT/SIGTERM + rollback wiring
├── ui/                       # unchanged
├── presets/                  # unchanged
├── scaffolding/              # unchanged
├── detector/                 # unchanged
├── gateway/                  # unchanged
└── templates/                # REMOVE legacy django_app.py
```

### Specific Improvements

| Area | Recommendation | Why | Effort |
|---|---|---|---|---|
| **Subcommand extraction** | Move each command to `commands/` | Prevents god module, enables isolated testing | Medium |
| **Gateway timeouts** | Add `timeout=` to all subprocess calls | Prevents hangs on slow networks | Low |
| **Parallel I/O** | Run `uv add` + `git init` + `gh repo create` concurrently | Saves 10-20s on scaffold | Medium |
| **Persistent rollback journal** | Save rollback journal to `~/.config/ajo/journal/` | Enables `ajo undo` across sessions | Medium |
| **Typo Correction** | `ajo/core/typo_correction.py` with `difflib` | Catches mistakes early, improves UX | Low |
| **Signal Handling** | `ajo/core/signals.py` — SIGINT → RollbackManager | Prevents half-scaffolded projects on Ctrl+C | Medium |
| **Env Detection** | `ajo/core/environment.py` — venv/uv/pipx detection | Routes subprocess commands to correct Python context | Medium |
| **CI type-checking** | `mypy --strict` in CI | Catches bugs before runtime | Low |
| **CI benchmarking** | `pytest-benchmark` with performance gates | Catches regressions | Low |
| **Test parallelization** | `pytest-xdist` for test suite | Faster feedback | Low |
| **DI container** | `lagom` or manual DI | Makes testing easier, reduces singletons | Future |

### Parallel I/O Example

```python
# In scaffold command — concurrent subprocess calls
async def _run_parallel_steps(project_path: Path) -> None:
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(uv_add_dependencies())
        t2 = tg.create_task(git_init_and_commit(project_path))
        t3 = tg.create_task(gh_create_repo())
        t4 = tg.create_task(gen_docker_compose())
    # All four complete; rollback any that failed
```

### Performance Budget Targets (Maintain)

| Metric | Budget | Tool |
|---|---|---|
| Startup time | <50ms | `hyperfine` |
| AST parse (20 models) | <100ms | `pytest-benchmark` |
| Docker compose gen | <10ms | `timeit` |
| Theme switch | <5ms | `timeit` |
| Fuzzy filter (50 items) | <10ms | `timeit` |
| Dashboard render | <10ms | Rich internal |
| Diagnostic full scan | <200ms | `timeit` |

---

## 4. Phased Roadmap

### Phase 0 — Quick Wins (Week 1)

| # | Task | File(s) | Acceptance |
|---|---|---|---|
| 0.1 | `--no-color` / `NO_COLOR` / `FORCE_COLOR` support | `ajo/core/constants.py` | `NO_COLOR=1 ajo --version` outputs no ANSI |
| 0.2 | `-v` / `-vv` / `-q` verbosity + logging | `ajo/core/logging.py` (new), `ajo/cli.py` | `ajo -vv doctor` shows debug output |
| 0.3 | `ajo doctor` command | `ajo/commands/doctor.py` (new) | Reports all tool versions + config health |
| 0.4 | `ajo completion bash\|zsh\|fish` | `ajo/commands/completions.py` (new) | Generates valid shell completion scripts |
| 0.5 | Gateway timeouts (30s default) | `ajo/gateway/utils.py` | Long-running commands don't hang on Ctrl+C |
| 0.6 | `--dry-run` for scaffold | `ajo/cli.py`, `ajo/scaffolding/engine.py` | Shows planned files without creating anything |
| 0.7 | Auto-disable spinners when `CI=true` or non-TTY | `ajo/ui/progress.py`, `ajo/cli.py` | `ajo --help | cat` has no ANSI codes |
| 0.8 | Fuzzy typo correction for subcommands | `ajo/core/typo_correction.py` (new), `ajo/cli.py` | `ajo scafold` → "Did you mean scaffold?" |
| 0.9 | Virtual environment detection + correct subprocess delegation | `ajo/core/environment.py` (new), `ajo/gateway/` | `ajo doctor` shows env type; install commands use `uv add` in uv envs |
| 0.10 | Graceful SIGINT handler with rollback cleanup | `ajo/core/signals.py` (new), `ajo/commands/scaffold.py` | Ctrl+C during scaffold → rollback + exit 130, no leftover files |

### Phase 1 — Distribution & Updates (Week 2)

| # | Task | File(s) | Acceptance |
|---|---|---|---|
| 1.1 | `ajo upgrade` command + background version check | `ajo/commands/upgrade.py` (new), `ajo/core/updater.py` (new) | `ajo upgrade` updates to latest PyPI version |
| 1.2 | `ajo changelog` command | `ajo/commands/changelog.py` (new) | Shows last 10 releases with dates |
| 1.3 | Homebrew tap formula | `contrib/homebrew/ajo.rb` (new) | `brew install ajo-cli` works |
| 1.4 | AUR PKGBUILD | `contrib/aur/PKGBUILD` (new) | `yay -S ajo-cli-bin` works |
| 1.5 | CI: auto-publish to PyPI on tag | `.github/workflows/publish.yml` (new) | Tag push triggers PyPI release |
| 1.6 | CI: generate shell completions in build step | `pyproject.toml`, Makefile | Completion files in release artifacts |
| 1.7 | CI: performance gate | `.github/workflows/performance.yml` (new) | PR fails if startup >50ms |
| 1.8 | Silent update configuration (`AJO_NO_UPDATE_CHECK` env var + `check_updates: false` config) | `ajo/core/updater.py`, `ajo/core/config.py` | `AJO_NO_UPDATE_CHECK=1 ajo` makes no outbound calls; `ajo config set check_updates false` persists |

### Phase 2 — DevEx Hardening (Week 3)

| # | Task | File(s) | Acceptance |
|---|---|---|---|
| 2.1 | Extract `commands/` module from `cli.py` | `ajo/commands/*.py`, `ajo/cli.py` | All subcommands work identically |
| 2.2 | Persistent rollback journal for `ajo undo` + SIGINT rollback integration | `ajo/scaffolding/engine.py`, `ajo/core/journal.py` (new), `ajo/core/signals.py` | `ajo undo` reverses last scaffold; Ctrl+C rolls back partial scaffold via same journal |
| 2.3 | Parallel I/O for scaffold steps | `ajo/commands/scaffold.py`, `ajo/gateway/` | Dep install + git + gh run concurrently |
| 2.4 | ETA + throughput in progress bars | `ajo/ui/progress.py` | Long operations show "3m 12s remaining" |
| 2.5 | `mypy --strict` in CI | `pyproject.toml`, `.github/workflows/ci.yml` | `mypy ajo/ --strict` passes |
| 2.6 | `pytest-benchmark` for performance | `tests/benchmarks/` (new dir) | Benchmarks on every PR |
| 2.7 | Ruff format + lint gate in CI | `.github/workflows/ci.yml` | `ruff check . && ruff format --check .` passes |

### Phase 3 — Plugin System & Telemetry (Week 4)

| # | Task | File(s) | Acceptance |
|---|---|---|---|
| 3.1 | Entry-point based plugin discovery | `ajo/presets/plugin.py` (new) | `pip install ajo-plugin-x` registers a new preset |
| 3.2 | Opt-in telemetry (`ajo telemetry on\|off\|status`) | `ajo/commands/telemetry.py` (new), `ajo/core/telemetry.py` (new) | Telemetry off by default; stored in config |
| 3.3 | Crash dump handler | `ajo/__init__.py` (modify), `ajo/core/crash.py` (new) | Unhandled exception saves to `~/.config/ajo/crash/` |
| 3.4 | Offline mode (`--offline`) | `ajo/cli.py`, `ajo/gateway/utils.py` | Skips all network calls, warns user, uses cache |
| 3.5 | Man page generation in CI | `scripts/generate_man.sh` (new) | `man ajo` works post-install |
| 3.6 | `--timeout` flag for scaffold | `ajo/cli.py`, `ajo/scaffolding/engine.py` | User can set per-step timeout |

### Phase 4 — Production Polish (Ongoing)

| # | Task | Acceptance |
|---|---|---|
| 4.1 | Test coverage >= 85% (`pytest --cov --cov-fail-under=85`) | CI fails below threshold |
| 4.2 | Benchmark gate in CI | PR fails if any budget exceeded |
| 4.3 | Edge case hardening: non-Django dirs, empty dirs, no network, minimal terminals | Integration tests pass |
| 4.4 | Full `--help` with examples per subcommand | `ajo scaffold --help` shows 3 examples |
| 4.5 | Changelog automation (`towncrier` or `scriv`) | `git tag` generates CHANGELOG.md |
| 4.6 | SIGINT + rollback stress testing: interrupt scaffold at every step, verify zero leftover files | Integration suite passes 5 interrupt-point scenarios |
| 4.7 | Environment isolation validation: scaffold in global, venv, uv, pipx — verify correct pip/uv commands used | All four environments produce identical output |
| 4.8 | Security audit: command injection, path traversal, secret exposure | No `shell=True`, no hardcoded secrets |
| 4.9 | Remove legacy `ajo/templates/django_app.py` | All scaffold paths use `ScaffoldEngine` |
| 4.10 | Documentation site / man page parity | README, man page, `--help` all in sync |

---

## Key Metrics

| Metric | Current | Target |
|---|---|---|
| Startup time | ~40-50ms | <50ms (maintain) |
| Test count | ~159 | 200+ |
| Test coverage | ~70% est. | >=85% |
| CLI entry points | ~15 | 20+ |
| Source lines | ~6000 | <8000 (with more features) |
| PyPI distribution | pip only | PyPI + Homebrew + AUR + pipx |
| CI gates | basic pytest | pytest + mypy + ruff + perf + coverage |

---

## Appendix: Key Technical Decisions

1. **shtab over argcomplete** — declarative, generates files at build time, zero runtime overhead
2. **PyPI JSON API over custom update server** — zero infrastructure, free, reliable
3. **entry-points over pip install plugins** — stdlib, no extra deps, works with any package manager
4. **logging stdlib over structlog** — zero dependency, sufficient for a CLI tool
5. **diskcache over redis** — CLI tool runs locally, no server dependency
6. **tomllib over configparser** — modern, supports nested structures, stdlib 3.11+
7. **`commands/` module over click groups** — keeps argparse (existing investment), adds modularity without migration cost
8. **Parallel I/O via TaskGroup** — Python 3.11+ feature, structured concurrency, automatic cleanup on error
9. **difflib over Levenshtein for typo correction** — stdlib, zero dependencies, sufficient accuracy for CLI command names
10. **sys.excepthook + signal.signal over contextlib for SIGINT** — global catch-all prevents any code path from leaving half-files
11. **VIRTUAL_ENV / UV_ACTIVE / PIPX_ACTIVE over probing sys.path** — env vars are the canonical signal; zero false positives
12. **AJO_NO_UPDATE_CHECK env var over --no-update-check flag** — can be set in CI/air-gapped shell profile without modifying command invocations
