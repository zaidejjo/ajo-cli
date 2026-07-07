## Goal
- Complete the composable add-on module system for ajo-cli across all plan phases, including full test coverage as specified in Section 12.

## Constraints & Preferences
- Plan stored in `.opencode/plans/04_addons_module_system.md` (1126 lines).
- Must maintain backward compatibility with existing presets and CLI flags.
- Add-ons are composable on top of any preset (Monolith, REST API, Ninja API, GraphQL, Docker).
- Settings injection is regex-based via `SettingsInjector`, not AST-based.
- All 14 test files from Section 12 of the plan must be created and passing.

## Progress
### Done
- **Phase 1** (Foundation): `ajo/presets/addons/__init__.py` with `AbstractAddon`, `ADDON_REGISTRY`, `register_addon()`, `get_addon()`, `resolve_addons()`, `get_addon_choices()`. `_settings.py` with full `SettingsInjector`. `ScaffoldEngine` updated with `addons` parameter and `_step_addon()`. CLI parser with `--addons`/`--no-addons` flags and interactive addon selection.
- **Phase 2** (Auth): `AuthAddon` with `AUTH_USER_MODEL`, `admin.py`, `forms.py`, 3 preset code paths (DRF endpoints, Ninja schemas/routers, monolith views), 6 Bootstrap 5 templates (login, signup, password reset flow), profile detail/edit templates for monolith.
- **Phase 3** (Cache): `CacheAddon` with `UpdateCacheMiddleware` (first) + `FetchFromCacheMiddleware` (last) ordering, Redis `CACHES` config, connection pooling, `debug_toolbar`, demo `core/views.py` with `@cache_page`/`@vary_on_cookie`.
- **Phase 4** (Security): `SecurityAddon` with Axes, OTP, CSP, HTTPS secure settings, security middleware.
- **Phase 5** (Testing): `TestingAddon` with AST-based model discovery (`_discover_models`), per-app `tests/` directories, `factories.py` generation from discovered models, `test_models.py`/`test_apis.py` stubs, UserFactory fallback for apps with no models.
- **Phase 6** (CLI Polish): `show_features()` displays add-on modules, `preset_key` threaded through `env_config` for preset-aware code generation.
- **Testing (Section 12)**: All 14 test files created and passing — `test_settings_injector.py`, `test_registry.py`, `test_auth_addon.py`, `test_cache_addon.py`, `test_security_addon.py`, `test_testing_addon.py`, `test_scaffold_with_addons.py`, `test_headless_addons.py`, `test_addon_compatibility.py`, `test_addon_rollback.py`, `test_generated_settings.py`, `test_generated_urls.py`, `test_generated_models.py`, `test_generated_factories.py`.

### Bug fixes during test validation
- `_inject_list` dedup: strip surrounding quotes from existing entries so `"django.contrib.admin"` matches `"'django.contrib.admin'"`.
- `inject_urls` line number fix: `match.start()` returns a **character index**, not a line number. Changed to `urls_text[:match.start()].count("\n")` to get the correct line for `_find_list_end`.
- `_url_block` (fallback) updated to accept `needs_include` parameter and use `include()` for URL includes — previously it always generated direct imports even when the pattern needed `include()`.
- `_extract_module` / `_extract_name`: handle `module:attr` colon notation (e.g., `debug_toolbar.toolbar:debug_toolbar_urlpatterns`) so generated `from ... import` statements are valid Python.
- `test_register_addon_duplicate_raises`: made self-contained instead of relying on leaked add-ons from other test files.
- `_cleanup_stray_addons` fixture: moved to module-level and changed to remove all non-standard add-on keys, preventing cross-test pollution.

### In Progress
- (none — all phases complete)

### Blocked
- (none)

## Key Decisions
- `inject_urls()` detects URL includes (paths ending in `.urls`) and generates `path('route', include('accounts.urls'))` instead of `path('route', urls)`. Falls back to direct view import for non-include patterns.
- `_inject_list` dedup strips `'` / `"` from existing entries before comparison so `"django.contrib.admin"` matches `"'django.contrib.admin'"`.
- Add-on `apply()` receives preset key via `env_config['preset_key']` to conditionally generate DRF endpoints, Ninja routers, or monolith views.
- Module-level `_cleanup_stray_addons` autouse fixture removes any key not in `_KNOWN_ADDONS = {"auth", "cache", "security", "testing"}` after each test to prevent registry pollution.
- `pytest` and `pytest-asyncio` added as dev dependencies for test execution.

## Next Steps
- (none — all phases of the plan are complete)

## Critical Context
- **All 159 tests pass** (1 skipped — asyncio strict mode in `test_addon_rollback.py`).
- Pre-existing LSP errors in `cli.py` (lazy proxy types, `InquirerPy.inquirer.confirm`) — not from our changes.
- Pre-existing type warning at `ajo/presets/__init__.py:78` — not from our changes.
- LSP "Import 'pytest' could not be resolved" warnings in `tests/*.py` are expected — pytest is a dev dependency.
- LSP errors about `_discover_models`, `_generate_factories`, `preview_files` on `AbstractAddon` type are false positives — the concrete addon classes have these at runtime.
- The `addon.apply()` signature is `(self, project_path, project_name, env_config)` — env_config contains `preset_key` for conditional code generation.

## Relevant Files
- `.opencode/plans/04_addons_module_system.md`: Full plan specification (1126 lines).
- `ajo/presets/addons/__init__.py`: Core registry and `AbstractAddon` (392 lines).
- `ajo/presets/addons/_settings.py`: SettingsInjector with all injection methods (434 lines, includes URL `include()` fix and `module:attr` colon handling).
- `ajo/presets/addons/auth.py`: Preset-aware auth add-on (DRF/Ninja/monolith code paths).
- `ajo/presets/addons/cache.py`: Cache add-on with middleware ordering and demo view.
- `ajo/presets/addons/security.py`: Security hardening add-on.
- `ajo/presets/addons/testing.py`: Testing add-on with model discovery and per-app factories.
- `ajo/scaffolding/engine.py`: Updated with `addons` parameter and `_step_addon()`.
- `ajo/cli.py`: Updated with `--addons`/`--no-addons` flags, interactive checkbox, `preset_key` in env_config, addon features display.
- `tests/conftest.py`: Shared fixtures (`SAMPLE_SETTINGS`, `temp_project`, `env_config` variants).
- `tests/test_*.py`: 14 test files covering SettingsInjector, registry, per-addon, integration, rollback, and generated project verification.
