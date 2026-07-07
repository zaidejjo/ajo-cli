# Plan: TUI Main Menu for Interactive `ajo`

## Goal

Replace the current behaviour of typing bare `ajo` (no arguments, no subcommand) — which today jumps straight into project creation — with a rich welcome menu of all available actions, Cyberpunk-styled using the existing Rich/InquirerPy TUI infrastructure.

---

## Current Behaviour

```
ajo (no args)
  ├── Parse args, init theme, config, signals, background check
  ├── If Django project detected
  │     └── Show dashboard + smart command menu (diagnostics, new project, exit)
  └── If NOT a Django project
        └── Jump straight into project creation (project name prompt)
```

**Problem:** There is no welcome screen offering the user a choice. Running `ajo` from an empty directory immediately prompts for "Project name:" with no context or alternatives.

---

## Desired Behaviour

```
ajo (no args)
  ├── [always] Show welcome screen (banner, version, tagline)
  ├── [always] Show main menu with themed choices
  │
  │     ┌─────────────────────────────────────────┐
  │     │  🚀 Welcome to ajo v3.3.0               │
  │     │  Professional Django scaffolder         │
  │     │                                         │
  │     │  What would you like to do?             │
  │     │                                         │
  │     │  🏗️  Create New Project                 │
  │     │  🔍  Scan Django Project   [scan]       │
  │     │  🩺  Run Diagnostics       [doctor]     │
  │     │  📋  Generate Report      [report]      │
  │     │  📦  Check for Updates    [upgrade]     │
  │     │  📖  View Changelog       [changelog]   │
  │     │  ⚙️  Shell Completions    [completion]  │
  │     │  ❌  Exit                               │
  │     └─────────────────────────────────────────┘
  │
  └── Route to the chosen action (reuse existing subcommand run() functions)
```

---

## Files to Modify

| File | Change |
|------|--------|
| `ajo/cli.py` | Add `_show_main_menu()` async function; restructure `_async_main()` to show menu before Django detection |
| `ajo/commands/menu.py` | **(new)** Extract menu logic into its own module for testability and clean imports |

---

## Detailed Steps

### Step 1: Create `ajo/commands/menu.py`

New module containing:

```python
async def show_main_menu() -> str:
    """Render the welcome banner and main menu, return the chosen action."""
```

- **Welcome banner**: Use Rich `Panel` with acyberpunk-styled title (`"ajo v{version}"`), a tagline, and a separator.
- **Menu choices**: `inquirer.select` with `Choice` objects for each command, styled with existing `INQUIRER_STYLE` and `qmark()`.
- **Action values** (strings): `"new_project"`, `"scan"`, `"doctor"`, `"report"`, `"upgrade"`, `"changelog"`, `"completion"`, `"exit"`.
- Reuse existing icons: `rocket` (`🚀`), `django` (`🦄`), `api` (`󱂛`), `ninja` (`󰝴`).
- Each menu item prefixed with an icon and suffixed with a dim help hint.

### Step 2: Restructure `_async_main()` in `ajo/cli.py`

Current flow (pseudocode):

```
async def _async_main():
    parse_args()
    install_signal_handlers()
    if command: dispatch_subcommand()
    init_theme()
    init_config()
    background_check()
    first_run_prompt()
    if headless: return headless_execute()
    # Interactive
    detector = DjangoProjectDetector()
    if detector.is_django_project:
        show_dashboard()
        show_smart_menu()
    # else: straight to project creation
    project_creation_flow()
```

New flow:

```
async def _async_main():
    parse_args()
    install_signal_handlers()
    if command: dispatch_subcommand()
    init_theme()
    init_config()
    background_check()
    first_run_prompt()
    if headless: return headless_execute()
    # Interactive — show main menu
    action = await show_main_menu()
    if action == "exit": return 0
    if action == "new_project": project_creation_flow()
    if action == "doctor": run_doctor(args_with_no_command)
    if action == "scan": run_scan(args_with_no_command)
    if action == "report": run_report(args_with_no_command)
    if action == "upgrade": run_upgrade(args_with_no_command)
    if action == "changelog": run_changelog(args_with_no_command)
    if action == "completion": run_completion(args_with_no_command)
```

**Key considerations:**
- For subcommand actions (scan, doctor, report, upgrade, changelog, completion): construct a minimal `argparse.Namespace` with default flags so the existing `run_*()` functions work unchanged.
- `run_doctor` expects `args` with `.json` attribute → default `False`.
- `run_upgrade` expects `args` with `.check` and `.yes` → default `False`.
- `run_changelog` expects `args` with `.latest` → default `False`.
- `run_scan` expects `args` with `.json` → default `False`.
- `run_report` expects `args` with `.output`, `.clipboard`, `.stdout` → all `None`/`False`.
- `run_completion` expects `args` with `.shell` → default `"bash"`.

### Step 3: Adjust Dashboard Flow

When in a Django project, we have **two options**:

**Option A**: Show main menu first, then if user picks "Create New Project" and we detect a Django project, show the dashboard/smart menu before creation. *(Simpler, less disruptive.)*

**Option B**: Keep the existing Django dashboard + smart menu as a separate `ajo dashboard` subcommand, and always show the unified main menu. *(Cleaner separation, but removes the automatic Django dashboard.)*

**Recommendation: Option A** — Minimal change. The main menu replaces the hard jump into project creation. Django project detection still works: when "Create New Project" is selected and a Django project is detected, show the dashboard + smart menu as before.

### Step 4: Tests

| Test file | Tests |
|-----------|-------|
| `tests/commands/test_menu.py` | **(new)** Verify menu renders, all expected choices present, each action routes correctly |
| Update existing CLI tests | Ensure `ajo` with no args now shows menu (not immediate prompt) |

### Step 5: Verify

- `ajo` (no args) → shows welcome menu
- Each menu choice → dispatches to correct command
- `ajo --help` untouched
- `ajo doctor` (subcommand) untouched
- `ajo --yes --name myproject` (headless) untouched
- All 652 existing tests still pass

---

## Files to Create

- `ajo/commands/menu.py`
- `tests/commands/test_menu.py`

## Files to Modify

- `ajo/cli.py`
- `tests/commands/__init__.py` (ensure package exists)

---

## Out of Scope

- Adding new subcommands or modifying existing `run_*()` functions
- Changing the headless/CI flow
- Changing `--help` output
- Adding persistent menu configuration/settings screen (future work)
