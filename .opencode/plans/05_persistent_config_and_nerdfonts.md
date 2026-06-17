# Plan: Persistent Config System + Conditional Nerd Font Icons

**Date:** 2026-06-17
**Status:** Draft for review
**Target files:**
- `ajo/core/config.py` (new)
- `ajo/core/constants.py` (modify — `NF` class, new icon mapping)
- `ajo/ui/terminal_detector.py` (modify — lean on config)
- `ajo/cli.py` (modify — first-time prompt, icon injection)
- `tests/test_config.py` (new)
- `ajo/ui/capabilities.py` (minor — wire config into `has_nerd_fonts`)

---

## 1. Architectural Design — ConfigManager

### 1.1 What & Where

Create a new module `ajo/core/config.py`. It houses a **`ConfigManager`** class (not a singleton — just a plain class instantiated once at startup) that:

1. Reads `~/.config/ajo/config.json`
2. Merges with environment variables (env vars take precedence)
3. Provides a typed `.get(key, default)` / `.set(key, value)` / `.save()` API
4. Handles the **first-time prompt** for Nerd Font preference
5. Caches in memory for the lifetime of the process

### 1.2 File Location & Format

```
~/.config/ajo/
  └── config.json
```

JSON schema:

```jsonc
{
  "version": 1,
  "nerd_fonts": true,         // user preference; null means "ask first time"
  "theme": "cyberpunk",       // saved theme preference (future use)
  "updated_at": "2026-06-17T10:30:00Z"
}
```

### 1.3 Safe Read / Write Strategy

| Scenario | Behaviour |
|---|---|
| `~/.config/ajo/` missing | **Create it** (mkdir `0o755`). No error. |
| `config.json` missing | Return defaults (`nerd_fonts: None`). Prompt on first interactive use. |
| JSON parse error (corrupt) | Log a warning (via `console.print` dim), return defaults, **overwrite with fresh defaults on next `.save()`**. |
| PermissionError on read | Swallow silently, treat as missing, return defaults. |
| PermissionError on write | Print a single-line dim warning, skip save. Never crash. |
| Read-only filesystem | Same as PermissionError — graceful degradation. |
| Symlink attacks | Use `Path.resolve()` before any file operation. |

**Implementation sketch:**

```python
# ajo/core/config.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


CONFIG_DIR = Path("~/.config/ajo").expanduser().resolve()
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: dict = {
    "version": 1,
    "nerd_fonts": None,  # None = unset (first-time)
    "theme": None,       # None = use CLI arg default
    "updated_at": None,
}


class ConfigManager:
    """Reads/writes ~/.config/ajo/config.json with full error tolerance."""

    def __init__(self) -> None:
        self._data: dict = dict(DEFAULT_CONFIG)
        self._dirty: bool = False
        self._load()

    # ── Public API ────────────────────────────────────────────────────

    def get(self, key: str, default=None):
        value = self._data.get(key, default)
        if value is None and key in DEFAULT_CONFIG:
            return default
        return value

    def set(self, key: str, value, *, auto_save: bool = False) -> None:
        self._data[key] = value
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._dirty = True
        if auto_save:
            self.save()

    def save(self) -> None:
        if not self._dirty:
            return
        try:
            CONFIG_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self._dirty = False
        except (OSError, PermissionError) as exc:
            # Single-line dim warning — never crash
            from rich.console import Console
            Console().print(f"[dim]⚠ Could not save config: {exc}[/dim]")

    def is_first_run(self) -> bool:
        """True if nerd_fonts has never been set."""
        return self._data.get("nerd_fonts") is None

    # ── Internal ──────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if CONFIG_FILE.is_file():
                raw = CONFIG_FILE.read_text(encoding="utf-8")
                self._data = json.loads(raw)
                # Merge with defaults so new keys are always present
                for k, v in DEFAULT_CONFIG.items():
                    self._data.setdefault(k, v)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError):
            self._data = dict(DEFAULT_CONFIG)
```

### 1.4 Integration Points

| Call site | What it does |
|---|---|
| `ajo/cli.py` `_async_main()` (before anything else) | Instantiate `ConfigManager`, store on module or pass to functions. |
| `ajo/ui/capabilities.py` `has_nerd_fonts()` | Short-circuit: if config has a definite `True`/`False`, return that instead of auto-detecting. |
| `ajo/core/constants.py` NF fallback block | Use config value (if set) to decide whether to apply fallback icons. |
| `ajo/cli.py` first-time block | Ask the user "Do you use a Nerd Font?" and `.set("nerd_fonts", answer, auto_save=True)`. |

---

## 2. UX Workflow — First-Time Nerd Font Prompt

### 2.1 Flow Diagram

```
_async_main() starts
  │
  ├─ Parse args
  ├─ Init ThemeEngine
  ├─ Init ConfigManager
  │
  ├─ [HEADLESS] ──→ Skip prompt entirely. Use env var / auto-detect.
  │
  └─ [INTERACTIVE]
       │
       ├─ ConfigManager.is_first_run() == False
       │   └─ Use saved value. Skip prompt.
       │
       └─ ConfigManager.is_first_run() == True
            └─ Show prompt:
                "? Do you use a Nerd Font in your terminal?"
                (Yes / No)

                On answer:
                  - ConfigManager.set("nerd_fonts", answer, auto_save=True)
                  - Apply icon set immediately
```

### 2.2 Prompt Implementation

Uses **InquirerPy** `inquirer.confirm` to match the existing style:

```python
# In _async_main(), after theme init, before dashboard:
from ajo.core.config import ConfigManager

config = ConfigManager()

if config.is_first_run() and not (args.headless or args.yes):
    console.print()
    nerd_font = inquirer.confirm(
        message="Do you use a Nerd Font in your terminal?",
        default=False,
        style=INQUIRER_STYLE,
        qmark="?",
    ).execute()
    config.set("nerd_fonts", nerd_font, auto_save=True)
```

**Key details:**

- The `qmark="?"` is intentionally different from the scaffold prompts (`qmark="❯"`) — it signals a **setup/preference** question, not an action prompt.
- The question uses the minimalist style: no panel, no extra decoration, just the single line with `?` prefix.
- `default=False` is conservative — users who don't know what Nerd Fonts are will say No and get clean text fallbacks.
- The prompt appears **before** the dashboard and feature grid so the correct icon set is active for the whole session.

### 2.3 Headless / Non-Interactive Modes

| Mode | Behaviour |
|---|---|
| `--headless` | Skip prompt entirely. Use env var, then auto-detect, then default to False. |
| `--yes` | Skip prompt entirely. Same as headless. |
| `NERD_FONTS=1 env var` | Override everything — same as today, takes highest precedence. |
| `CI=true` / `NO_COLOR=1` | Treated as headless — skip prompt. |

### 2.4 Config Manager Precedence (highest to lowest)

```
1. CLI flag --no-nerd-font (future)
2. $NERD_FONTS env var
3. Saved config.json value
4. Auto-detection (TerminalDetector)
5. Default = False (text fallbacks)
```

---

## 3. Icon Mapping Matrix

### 3.1 Design Decision: Unified Icon Function

Rather than keeping two parallel sets (NF class for Nerd Font + ad-hoc Unicode in CLI), we introduce a single **`icon()`** function and a **canonical mapping table** in `ajo/core/constants.py`. All UI code calls `icon("key")` which returns the right glyph based on `ConfigManager` → `TerminalDetector` → `supports_nerd_fonts`.

The `NF` class is **refactored** from literal codepoints to a namespace of string names (the enum keys become the keys into the mapping). For backward compatibility, `NF.PYTHON` becomes a property that delegates to `icon("python")`.

### 3.2 Complete Mapping Table

| Key | Nerd Font Glyph | Codepoint | Text Fallback | Used In |
|---|---|---|---|---|
| `python` |  | `\ue835` | `"Py"` | Banner |
| `django` | 󰌾 | `\uf033e` | `"Dj"` | Banner |
| `uv` | 󱑍 | `\uf1c4d` | `"uv"` | Banner |
| `ruff` | 󱘗 | `\uf0617` | `"Rf"` | Banner |
| `git` | 󰊢 | `\uf0222` | `"git"` | Banner, status |
| `github` | 󰊤 | `\uf0224` | `"GH"`  (or `"🐙"`) | Completion, banner |
| `docker` | 󰡨 | `\uf0868` | `"Dk"` | Banner |
| `database` | 󰆼 | `\uf01bc` | `"DB"` | Completion, features |
| `sqlite` | 󰌾 | `\uf033e` | `"SQLite"` | Completion |
| `postgres` |  | `\ue75e` | `"PG"` | Completion |
| `mysql` |  | `\ue704` | `"MySQL"` | Completion |
| `check` | 󰄬 | `\uf012c` | `"✔"` | Success messages |
| `error` | 󰅖 | `\uf0156` | `"✖"` | Error messages |
| `warning` | 󰀪 | `\uf002a` | `"▲"` | Warning messages |
| `info` | 󰌶 | `\uf0336` | `"ℹ"` | Info messages |
| `bullet` | 󰅂 | `\uf0142` | `"❯"` | Feature lists, items |
| `arrow_right` | 󰁔 | `\uf0454` | `"❯"` | InquirerPy qmark |
| `arrow_down` | 󰁢 | `\uf0462` | `"↓"` | Menus |
| `rocket` | 󱐋 | `\uf044b` | `"🚀"` (or `">_"`) | Dashboard |
| `gear` | 󰒓 | `\uf0493` | `"⚙"` | Settings, config |
| `server` | 󰌈 | `\uf0308` | `"Srv"` | Dashboard, features |
| `folder` | 󰉋 | `\uf024b` | `"📁"` | File tree preview |
| `folder_open` | 󰉌 | `\uf024c` | `"📂"` | File tree preview |
| `file` | 󰡄 | `\uf0184` | `"📄"` | File tree preview |
| `app` | 󰣆 | `\uf08c6` | `"App"` | Completion, dashboard |
| `model` | 󰤤 | `\uf0924` | `"Md"` | Dashboard |
| `migration` | 󰏘 | `\uf03d8` | `"Mig"` | Dashboard |
| `user` | 󰙲 | `\uf0672` | `"👤"` | Smart commands |
| `plus` | `+` (NF `\uf067`) | `\uf067` | `"+"` | Add-ons |
| `cache` | 󰩺 | `\uf027a` | `"Cch"` | Add-on label |
| `lock` | 󰌾 | `\uf033e` | `"🔒"` | Security add-on |
| `test` | 󰙨 | `\uf0668` | `"Tst"` | Testing add-on |
| `terminal` | 󰆍 | `\uf018d` | `"$ _"` | Next steps |
| `url` | 󰌌 | `\uf030c` | `"🔗"` | Completion URL |
| `status_success` | 󰄬 | `\uf012c` | `"✔"` | Status labels |
| `status_error` | 󰅖 | `\uf0156` | `"✖"` | Status labels |
| `status_warning` | 󰀪 | `\uf002a` | `"▲"` | Status labels |
| `status_info` | 󰌶 | `\uf0336` | `"ℹ"` | Status labels |
| `status_running` | 󰝤 | `\uf0764` | `"▶"` | Server status |
| `status_stopped` | 󰅛 | `\uf015b` | `"■"` | Server status |

### 3.3 NF Class Refactor (backward-compatible)

```python
class NF:
    """Nerd Font icon constants — resolved via ConfigManager at runtime.

    Access like ``NF.PYTHON`` — returns the correct glyph for the
    current terminal configuration.
    """

    _resolved: dict[str, str] = {}

    @classmethod
    def _resolve(cls, key: str, nf_glyph: str, fallback: str) -> str:
        cached = cls._resolved.get(key)
        if cached is not None:
            return cached
        # Check ConfigManager first, then auto-detect
        from ajo.core.config import _global_config
        if _global_config is not None:
            pref = _global_config.get("nerd_fonts")
            if pref is True:
                result = nf_glyph
            elif pref is False:
                result = fallback
            else:
                result = _auto_resolve(key, nf_glyph, fallback)
        else:
            result = _auto_resolve(key, nf_glyph, fallback)
        cls._resolved[key] = result
        return result

    # Properties for each icon (preserves existing NF.PYTHON syntax)
    PYTHON = property(lambda cls: cls._resolve("python", "\ue835", "Py"))
    DJANGO = property(lambda cls: cls._resolve("django", "\uf033e", "Dj"))
    # ... all other icons follow the same pattern
```

The backward-compatible fallback block at the bottom of `constants.py` (lines 163-174) is **removed** — the new `NF._resolve()` replaces it entirely.

### 3.4 InquirerPy qmark Centralization

Instead of scattered hardcoded `qmark="❯"`, create a single access point:

```python
# In ajo/ui/theme.py or ajo/core/constants.py

def qmark() -> str:
    """Return the prompt prefix character."""
    return icon("arrow_right")  # ❯ or Nerd Font arrow
```

All InquirerPy prompts change from `qmark="❯"` to `qmark=qmark()`.

---

## 4. UI Injections — Checklist

### 4.1 `print_banner()` — `ajo/cli.py:252`

| Current | Change |
|---|---|
| Hardcoded `NF.PYTHON`, `NF.DJANGO`, `NF.UV`, `NF.RUFF` | Already using NF — will auto-resolve after refactor. |
| Static `__version__` formatting | No change needed. |

### 4.2 `show_error()` / `show_success()` / `show_info()` / `show_warning()` — `ajo/cli.py:272-302`

| Current | Change |
|---|---|
| `✖` hardcoded | → `icon("error")` |
| `✔` hardcoded | → `icon("check")` |
| `ℹ` hardcoded | → `icon("info")` |
| `▲` hardcoded | → `icon("warning")` |
| `❯` in suggestion line | → `icon("bullet")` |

### 4.3 `show_features()` — `ajo/cli.py:309`

| Current | Change |
|---|---|
| `❯` for feature bullets | → `icon("bullet")` |
| `❯` for preset bullets | → `icon("bullet")` |
| `⊕` for add-on bullets | → `icon("plus")` |

### 4.4 `check_prerequisites()` — `ajo/cli.py:384`

| Current | Change |
|---|---|
| `❯` for list prefix | → `icon("bullet")` |

### 4.5 Preset selection / DB selection / all InquirerPy prompts

| Current | Change |
|---|---|
| `qmark="❯"` (scattered) | → `qmark=qmark()` (centralized) |
| `qmark=""` for project name | No change (intentionally empty) |
| `qmark="?"` for Nerd Font prompt | New — see UX section |

### 4.6 Add-ons Selector — `ajo/cli.py:1628-1663`

| Current | Change |
|---|---|
| `qmark="❯"` | → `qmark=qmark()` |
| Static section header | No change needed. |

### 4.7 Scaffold Preview (FileTreePreview) — `ajo/ui/theme.py:311`

| Current | Change |
|---|---|
| Plain folder labels `"  dirname/"` | → prefix with `icon("folder")` |
| Plain file names | → prefix with `icon("file")` |
| Static title "Scaffold Preview" | No change needed. |

### 4.8 `show_completion()` — `ajo/cli.py:1161`

| Current | Change |
|---|---|
| `❯` for each info line | → `icon("bullet")` or `icon("check")` |
| Static `db_type.upper()` | → prefix with `icon(f"database")` |
| `❯` for next-steps bullets | → `icon("bullet")` |
| `➜` for URL | → `icon("url")` or keep static `➜` |
| Plain `"Created"` / `"Skipped"` | → prefix with `icon("check")` / `icon("error")` |

### 4.9 `show_dashboard()` + `DashboardRenderer` — `ajo/cli.py:737-843`

| Current | Change |
|---|---|
| Plain row labels like `"[dim]Project[/]"` | No change (keep dim style). |
| `venv_label()`, `server_label()`, etc. | Keep as-is (they use Text objects). |
| Dashboard uses styled labels | Could add `icon("server")` to Server row in future — **deferred**. |

### 4.10 Headless Completion Summary — `ajo/cli.py:1434-1454`

| Current | Change |
|---|---|
| `❯` for list items | → `icon("bullet")` |
| Static text | Add `icon("check")` for success states. |

### 4.11 Diagnostic Engine — `ajo/cli.py:876-884`

| Current | Change |
|---|---|
| `[{color}][{label}][/]` for severity | Could prefix with `icon("warning")` / `icon("error")` — **optional, low priority**. |

---

## 5. Testing Strategy

### 5.1 Test File: `tests/test_config.py`

All tests use **`pathlib.Path.tmpdir`** or **`tempfile.TemporaryDirectory`** so no real `~/.config/ajo` is ever touched.

### 5.2 Fixtures

```python
# tests/conftest.py additions

@pytest.fixture
def tmp_config_dir(tmp_path):
    """Return a temp directory that stands in for ~/.config/ajo."""
    d = tmp_path / ".config" / "ajo"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def config_manager(tmp_config_dir):
    """Return a ConfigManager pointed at the tmp dir (via monkeypatch)."""
    import ajo.core.config as cfg_mod
    cfg_mod.CONFIG_DIR = tmp_config_dir
    cfg_mod.CONFIG_FILE = tmp_config_dir / "config.json"
    mgr = cfg_mod.ConfigManager()
    return mgr
```

### 5.3 Test Cases

| Test | What it verifies |
|---|---|
| `test_defaults_on_missing_file` | No file exists → `is_first_run()` is `True`, `.get("nerd_fonts")` is `None`. |
| `test_reads_saved_file` | Write a valid JSON → `ConfigManager` reads it, `.get("nerd_fonts")` returns `True`. |
| `test_save_creates_file` | `.set("nerd_fonts", False, auto_save=True)` → file exists with correct content. |
| `test_save_creates_directory` | `.save()` when dir missing → creates `~/.config/ajo/` with correct mode. |
| `test_corrupt_json` | Write `{"broken":` → `ConfigManager` falls back to defaults, does not crash. |
| `test_permission_error_read` | Make file unreadable → silently returns defaults. |
| `test_permission_error_write` | Make dir unwritable → prints dim warning, does not crash. |
| `test_dirty_flag` | `.set()` marks dirty; `.save()` clears dirty; no-op save does nothing. |
| `test_updated_at` | `.set()` stamps ISO 8601 timestamp. |
| `test_merge_with_defaults` | File has partial keys → defaults fill the gaps. |
| `test_is_first_run` | `nerd_fonts: null` → `True`; `nerd_fonts: false` → `False`. |
| `test_global_config_reference` | After `ConfigManager()` init, `_global_config` is set. |

### 5.4 Mocking Strategy

- **File system**: Use `tmp_path` (built-in pytest fixture) + `monkeypatch` to redirect `CONFIG_DIR` and `CONFIG_FILE`.
- **No real `~/.config/ajo` is ever read or written** during tests.
- **No mocking of `Path.write_text` or `Path.read_text`** — use real temp directories for integration fidelity.
- For tests that need to simulate permission errors, use `monkeypatch` to replace `Path.write_text` with a function that raises `PermissionError`.

### 5.5 Running the Tests

```bash
# All config tests
uv run pytest tests/test_config.py -v

# Verify no real home dir access
strace -e openat uv run pytest tests/test_config.py 2>&1 | grep ".config/ajo" || echo "No access ✅"
```

---

## 6. Migration / Rollout Order

| Step | Description | Depends on |
|---|---|---|
| 1 | Create `ajo/core/config.py` with `ConfigManager` (no prompt wiring yet) | Nothing |
| 2 | Write `tests/test_config.py` — all 12 test cases | Step 1 |
| 3 | Refactor `NF` class in `constants.py` — add `_resolve()`, canonical mapping table | Step 1 (needs `_global_config`) |
| 4 | Add `icon()` helper and `qmark()` to `constants.py` or `theme.py` | Step 3 |
| 5 | Update all `show_*` functions in `cli.py` to use `icon()` | Step 4 |
| 6 | Update all InquirerPy prompts to use `qmark()` | Step 4 |
| 7 | Add first-time Nerd Font prompt in `_async_main()` | Step 1, Step 5 |
| 8 | Update `has_nerd_fonts()` in `capabilities.py` to check config | Step 1 |
| 9 | Remove old fallback block at end of `constants.py` (lines 163-174) | Step 3 |
| 10 | Manual smoke test: interactive, headless, `--yes`, env var override | All above |
| 11 | Update AGENTS.md with build/test commands | All above |

---

## 7. Open Questions / Future Considerations

| Question | Decision |
|---|---|
| Should we support `--no-nerd-font` CLI flag? | **Deferred.** Users can set `export NERD_FONTS=0` or answer No at the prompt. |
| Should theme preference also be persisted? | **Deferred.** The schema already includes `"theme"`, but the first iteration only persists `nerd_fonts`. |
| Should we migrate away from `NF.PYTHON` syntax entirely? | **No.** The property-based approach keeps `NF.PYTHON` working identically for all existing callers. |
| What about SSH sessions where the remote terminal doesn't have Nerd Fonts? | The auto-detection already handles this. The config is per-machine (`~/.config/ajo` on the local machine). If the user mounts home dirs across machines, they can set `$NERD_FONTS` per-session. |
| Should the prompt appear on every `ajo` upgrade? | **No.** Once `nerd_fonts` is set in config.json, it is never asked again. To re-prompt, users delete the file or set it to `null`. |
