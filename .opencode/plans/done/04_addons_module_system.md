# Plan: Composable Add-on Module System — Auth, Caching, Security, Testing

**Reference:** `.opencode/plans/04_addons_module_system.md`
**Version:** 1.0
**Created:** 2026-06-17

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture: The Add-on System](#2-architecture-the-add-on-system)
3. [Add-on 1: Auth & Users](#3-add-on-1-auth--users)
4. [Add-on 2: Caching & Performance](#4-add-on-2-caching--performance)
5. [Add-on 3: Security Hardening](#5-add-on-3-security-hardening)
6. [Add-on 4: Testing Infrastructure](#6-add-on-4-testing-infrastructure)
7. [CLI Integration & UX](#7-cli-integration--ux)
8. [ScaffoldEngine Changes](#8-scaffoldengine-changes)
9. [Implementation Phases](#9-implementation-phases)
10. [File Manifest](#10-file-manifest)
11. [Risk Matrix](#11-risk-matrix)
12. [Testing Strategy](#12-testing-strategy)

---

## 1. Executive Summary

**Goal:** Transform `ajo-cli` from a scaffold-only tool into a **comprehensive Django project generator** by adding four composable add-on modules that layer authentication, caching, security, and testing onto any architecture preset.

**Current limitation:** Presets are mutually exclusive (you pick one: Monolith, REST API, Ninja API, GraphQL, Docker). There is no way to add JWT auth to a Ninja API project, or add Redis caching to a DRF project, without manual post-scaffold work.

**Solution:** Create an `AbstractAddon` base class and a registry system that runs modular feature add-ons *after* the preset scaffold step, injecting settings, generating files, and installing dependencies.

**Impact:** Reduces post-scaffold setup from hours to zero for the four most-requested Django production-readiness features.

---

## 2. Architecture: The Add-on System

### 2.1 Core Concept

```
┌─────────────────────────────────────────────────────────────────────┐
│                       ScaffoldEngine.execute()                       │
│                                                                      │
│  1. Create project directory                                         │
│  2. Create .env                                                      │
│  3. Create .gitignore                                                │
│  4. Install preset dependencies                                      │
│  5. Install preset dev-dependencies                                  │
│  6. Git init                                                         │
│  7. uv init                                                          │
│  8. ─── RUN PRESET SCAFFOLD ─────────────────────────────           │
│     MonolithPreset | RestAPIPreset | NinjaAPIPreset | ...            │
│  9. ─── RUN SELECTED ADD-ONS ──────────────────────────              │
│     AuthAddon  →  CacheAddon  →  SecurityAddon  →  TestAddon        │
│ 10. uv sync                                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 `AbstractAddon` Base Class

New file: `ajo/presets/addons/__init__.py`

```python
class AbstractAddon(ABC):
    """A composable feature module that layers onto any preset.

    Each add-on can:
    - Install extra PyPI dependencies
    - Inject settings into settings.py (INSTALLED_APPS, MIDDLEWARE, etc.)
    - Add URL patterns to urls.py
    - Append environment variables to .env
    - Generate new files (models, views, templates, tests)
    - Run arbitrary async setup code

    Add-ons are ordered by dependency. The registry ensures
    no duplicate or conflicting add-ons are applied together.
    """

    # Metadata
    name: str                                      # "JWT Auth"
    description: str                               # "JWT + registration + profile"
    dependencies: list[str]                        # Extra pip packages
    dev_dependencies: list[str]                    # Extra dev pip packages
    compatible_presets: list[str] | None = None    # None = all presets
    conflicts_with: list[str] = []                 # Add-on keys that conflict

    # Configuration templates
    installed_apps: list[str] = []
    middleware: list[str] = []
    url_patterns: list[tuple[str, str]] = []       # (path, import_string)
    env_vars: dict[str, str] = {}
    settings_blocks: list[str] = []

    @abstractmethod
    async def apply(
        self,
        project_path: Path,
        project_name: str,
        env_config: dict[str, Any],
    ) -> None:
        """Execute add-on scaffolding. Called after preset.scaffold()."""
```

### 2.3 Add-on Registry

Also in `ajo/presets/addons/__init__.py`:

```python
ADDON_REGISTRY: dict[str, type[AbstractAddon]] = {}

def register_addon(cls: type[AbstractAddon]) -> type[AbstractAddon]:
    """Decorator to register an add-on class."""
    key = cls.__name__.replace("Addon", "").lower()
    ADDON_REGISTRY[key] = cls
    return cls

def get_addon(key: str) -> type[AbstractAddon]:
    """Look up an add-on by key."""
    ...

def resolve_addons(selected: list[str]) -> list[AbstractAddon]:
    """Resolve + validate + order a list of add-on keys.
    
    - Checks compatibility with the chosen preset
    - Detects conflicts
    - Orders by dependency graph
    - Returns instantiated add-on objects
    """
    ...
```

### 2.4 Settings Injection Strategy

Each add-on needs to inject config into `settings.py`. The current `RestAPIPreset` uses naive string replacement (`INSTALLED_APPS = [` → inject block). This is fragile. We need a **structured settings parser**.

New file: `ajo/presets/addons/_settings.py`

```python
class SettingsInjector:
    """Parse settings.py and inject add-on configurations at
    the correct positions (INSTALLED_APPS, MIDDLEWARE, end-of-file).

    Uses regex/ast-based position detection rather than
    fragile string matching.
    """

    INSTALLED_APPS_PATTERN = re.compile(
        r"(INSTALLED_APPS\s*=\s*\[)",
        re.MULTILINE,
    )
    MIDDLEWARE_PATTERN = re.compile(
        r"(MIDDLEWARE\s*=\s*\[)",
        re.MULTILINE,
    )

    @classmethod
    def inject_apps(cls, settings_text: str, apps: list[str]) -> str:
        """Add entries to INSTALLED_APPS list."""
        ...

    @classmethod
    def inject_middleware(cls, settings_text: str, middleware: list[str],
                          *, at_beginning: bool = False) -> str:
        """Add entries to MIDDLEWARE list."""
        ...

    @classmethod
    def append_block(cls, settings_text: str, block: str) -> str:
        """Append a config block to the end of settings.py."""
        ...
```

---

## 3. Add-on 1: Auth & Users

**Key:** `auth`
**File:** `ajo/presets/addons/auth.py`
**Dependencies:** `djangorestframework-simplejwt` (DRF) or `django-ninja-jwt` (Ninja)

### 3.1 What It Generates

#### For ALL presets:

| File | Content |
|------|---------|
| `accounts/models.py` | Custom `User` model extending `AbstractUser` with `bio`, `avatar`, `phone`, `date_of_birth` fields |
| `accounts/admin.py` | Custom `UserAdmin` with new fields |
| `accounts/forms.py` | `UserCreationForm` + `UserChangeForm` with new fields |
| `accounts/apps.py` | `AccountsConfig` with `verbose_name` |
| `accounts/__init__.py` | Empty |
| `templates/registration/login.html` | Bootstrap 5 login page |
| `templates/registration/signup.html` | Bootstrap 5 registration page |
| `templates/registration/password_reset_form.html` | Password reset form |
| `templates/registration/password_reset_done.html` | Reset email sent page |
| `templates/registration/password_reset_confirm.html` | New password form |
| `templates/registration/password_reset_complete.html` | Password reset done |

#### For DRF preset (`rest-api`):

| File | Content |
|------|---------|
| `accounts/api/serializers.py` | `UserSerializer`, `RegisterSerializer`, `LoginSerializer` |
| `accounts/api/views.py` | `RegisterView`, `LoginView`, `UserProfileView`, `TokenRefreshView` |
| `accounts/api/urls.py` | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/me/`, `/api/auth/token/refresh/` |

- Injects `rest_framework_simplejwt` into `INSTALLED_APPS`
- Adds `SIMPLE_JWT` settings block (access 30min, refresh 1 day, rotate + blacklist)
- Wires `api_router.py` or `urls.py` with auth endpoints

#### For Ninja preset (`ninja-api`):

| File | Content |
|------|---------|
| `accounts/api/schemas.py` | `UserOut`, `RegisterIn`, `LoginIn`, `TokenOut` |
| `accounts/api/endpoints.py` | Router with `register`, `login`, `me`, `refresh` endpoints |
| `accounts/api/auth_jwt.py` | `AuthBearer` or `AuthJWTCookie` middleware for NinjaAPI |

- Patches `api.py` to add `AuthBearer` to the NinjaAPI instance
- Wires `/api/auth/` router

#### For Monolith preset:

- Only creates the `accounts` app with models + templates (no API)
- Adds `django.contrib.auth` URLs (`/accounts/login/`, `/accounts/logout/`)

### 3.2 Configuration Injections

| Setting | Value |
|---------|-------|
| `INSTALLED_APPS` | `'accounts'`, `'rest_framework_simplejwt'` (DRF) or `'ninja_jwt'` (Ninja) |
| `AUTH_USER_MODEL` | `'accounts.User'` |
| `LOGIN_URL` | `'/accounts/login/'` |
| `LOGIN_REDIRECT_URL` | `'/'` |
| `LOGOUT_REDIRECT_URL` | `'/'` |
| `SIMPLE_JWT` | Block with `ACCESS_TOKEN_LIFETIME`, `REFRESH_TOKEN_LIFETIME`, `ROTATE_REFRESH_TOKENS`, `BLACKLIST_AFTER_ROTATION` |
| `NINJA_JWT` | Block with similar settings |

### 3.3 .env Additions

```
JWT_SECRET=
JWT_ACCESS_LIFETIME=30
JWT_REFRESH_LIFETIME=1
```

### 3.4 Migration Note

The custom `User` model requires `AUTH_USER_MODEL` before the first migration. The add-on must **set this before** `manage.py migrate` would run. Since ScaffoldEngine runs `uv sync` but NOT `migrate`, this is safe — the user runs migrations themselves.

---

## 4. Add-on 2: Caching & Performance

**Key:** `cache`
**File:** `ajo/presets/addons/cache.py`
**Dependencies:** `django-redis` (or `redis`)

### 4.1 What It Does

| Action | Detail |
|--------|--------|
| **Redis cache backend** | Injects `CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache", ...}}` |
| **Session backend** | Sets `SESSION_ENGINE = "django.contrib.sessions.backends.cache"` |
| **Cache middleware** | Adds `UpdateCacheMiddleware` (first) + `FetchFromCacheMiddleware` (last) in `MIDDLEWARE` |
| **Cache timeout** | Sets default cache timeout to 300s |
| **Example view** | Generates `core/views.py` with `@cache_page(60)` demo |
| **Compressor** | Optionally installs `django-compressor` for static file caching |

### 4.2 Configuration Injections

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {"max_connections": 50, "timeout": 20},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
        },
        "KEY_PREFIX": project_name,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = project_name
```

### 4.3 Middleware Order

The `UpdateCacheMiddleware` must be **first** in `MIDDLEWARE`, and `FetchFromCacheMiddleware` must be **last**. The `SettingsInjector` must handle positional ordering.

```
MIDDLEWARE = [
    'django.middleware.cache.UpdateCacheMiddleware',   # ← injected first
    'django.middleware.security.SecurityMiddleware',
    ...
    'django.middleware.cache.FetchFromCacheMiddleware', # ← injected last
]
```

### 4.4 .env Additions

```
REDIS_URL=redis://localhost:6379/0
CACHE_TIMEOUT=300
```

### 4.5 Generated Files

| File | Content |
|------|---------|
| `core/views.py` | `CachedDemoView` with `@cache_page(60)` and `CacheApiMixin` |
| `core/urls.py` | URL for the demo view |

---

## 5. Add-on 3: Security Hardening

**Key:** `security`
**File:** `ajo/presets/addons/security.py`
**Dependencies:** `django-axes`, `django-csp`, `django-ratelimit`

### 5.1 What It Does

| Feature | Implementation |
|---------|---------------|
| **Brute force protection** | `django-axes` — tracks login attempts, locks after `AXES_FAILURE_LIMIT=5` |
| **CSP headers** | `django-csp` — Content-Security-Policy with sensible defaults |
| **Rate limiting** | `django-ratelimit` — `@ratelimit(key='ip', rate='5/m')` decorator on auth views |
| **HTTPS redirect** | `SECURE_SSL_REDIRECT` + `SECURE_HSTS_SECONDS` + `SECURE_HSTS_INCLUDE_SUBDOMAINS` + `SECURE_HSTS_PRELOAD` |
| **Secure cookies** | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY` |
| **Clickjacking** | `X_FRAME_OPTIONS = "DENY"` |
| **Content sniffing** | `SECURE_CONTENT_TYPE_NOSNIFF = True` |
| **Referrer policy** | `SECURE_REFERRER_POLICY = "same-origin"` |

### 5.2 Configuration Injections

```python
INSTALLED_APPS += ['axes']

MIDDLEWARE += [
    'axes.middleware.AxesMiddleware',          # after auth
    'csp.middleware.CSPMiddleware',            # anywhere
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ── Axes ──
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1      # hours
AXES_RESET_ON_SUCCESS = True
AXES_LOCK_OUT_AT_FAILURE = True
AXES_ONLY_USER_FAILURES = False

# ── CSP ──
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "https://cdn.jsdelivr.net")

# ── HTTPS / Security ──
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
```

### 5.3 Generated Files

| File | Content |
|------|---------|
| `core/middleware.py` | Optional: custom `HealthCheckMiddleware` + `SecurityHeadersMiddleware` |
| No other files — all configuration is injected into `settings.py` |

### 5.4 .env Additions

```
AXES_ENABLED=True
AXES_FAILURE_LIMIT=5
SECURE_SSL_REDIRECT=False
```

### 5.5 Conflict Detection

- `security` add-on should warn when combined with `DEBUG=True` (many settings become ineffective)
- Compatible with all presets

---

## 6. Add-on 4: Testing Infrastructure

**Key:** `testing`
**File:** `ajo/presets/addons/testing.py`
**Dependencies:** `pytest`, `pytest-django`, `factory-boy`, `coverage` (dev-dependencies only)

### 6.1 What It Generates

#### pyproject.toml Config Injection:

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "{project_name}.settings"
testpaths = ["*/tests"]
python_files = ["test_*.py", "*_tests.py"]
addopts = "--reuse-db --strict-markers --tb=short"

[tool.coverage.run]
source = ["{project_name}", "apps"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
show_missing = true
fail_under = 80
```

#### Per-App Test Files:

For every app detected in the project (including `accounts` if auth add-on is active):

```
{app_name}/tests/
├── __init__.py
├── factories.py        # factory_boy factories for each model
├── test_models.py      # Model validation tests
├── test_views.py       # View/endpoint tests
└── conftest.py         # pytest fixtures (client, user, db)
```

#### Example Factory (`factories.py`):

```python
import factory
from django.contrib.auth import get_user_model

User = get_user_model()

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123!")
```

#### Base Test Class (`core/tests/base.py`):

```python
import pytest
from rest_framework.test import APIClient
from ninja.testing import TestClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client

@pytest.fixture
def user():
    from ..tests.factories import UserFactory
    return UserFactory()
```

### 6.2 Generated Files

| File | Content |
|------|---------|
| `pyproject.toml` (inject) | pytest + coverage tool config |
| `.coveragerc` | Coverage configuration (alternative to pyproject.toml) |
| `pytest.ini` | Pytest config (if not using pyproject.toml) |
| `{app}/tests/__init__.py` | Empty |
| `{app}/tests/factories.py` | factory_boy factories for each model |
| `{app}/tests/test_models.py` | Model creation + validation tests |
| `{app}/tests/test_views.py` | HTTP endpoint tests |
| `{app}/tests/conftest.py` | Shared fixtures |
| `core/tests/base.py` | Base test utilities, client fixtures |

### 6.3 AST Integration

The testing add-on should use the same AST analyzer (`ModelRelationshipAnalyzer`) to discover models and generate appropriate factories:

```python
# For each model discovered by AST:
class {ModelName}Factory(factory.django.DjangoModelFactory):
    class Meta:
        model = {model_module}.{ModelName}

    # Auto-generated for each field:
    name = factory.Sequence(lambda n: f"{model_name}_{n}")
    # For ForeignKey → create a child factory
    # For ChoiceField → pick from choices
    # For unique fields → Sequence
```

### 6.4 Dev Dependencies

```
pytest>=8.0.0
pytest-django>=4.5.0
factory-boy>=3.3.0
coverage>=7.2.0
pytest-cov>=4.1.0
model-bakery>=1.10.0     # Alternative/simpler fixtures
```

---

## 7. CLI Integration & UX

### 7.1 New Interactive Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ajo v3.0.1  —  Django Scaffolder              │
│  Python 3.10+  Django 5.0+  uv  Ruff                                │
├─────────────────────────────────────────────────────────────────────┤
│  Features                                                           │
│  ❯ Multi-Database Support  …  ❯ GitHub Integration       …          │
│  ❯ CI/CD with Ruff         …  ❯ Docker Support           …          │
├─────────────────────────────────────────────────────────────────────┤
│  Architecture Presets                                               │
│  ❯ Standard Monolith  — Traditional Django …  HTML + Bootstrap 5   │
│  ❯ REST API Ready     — DRF + CORS …           DRF + JWT + Swagger │
│  ❯ Ninja API          — django-ninja …          Swagger UI + Schema │
│  ❯ GraphQL API        — Graphene …              GraphiQL + Relay   │
├─────────────────────────────────────────────────────────────────────┤
│  Project Setup                                                      │
│  ❯ Project name: my_blog                                            │
│  ❯ Architecture preset: [Ninja API — django-ninja + Swagger UI]    │
│                                                                      │
│  ❯ Add-ons (space to select, enter to confirm):                    │
│    ◉ Auth & Users          JWT + registration + user profile        │
│    ◻ Caching               Redis cache + session backend            │
│    ◉ Security              django-axes + CSP + rate limiting         │
│    ◉ Testing               pytest + factories + coverage            │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Headless Mode Flags

New CLI flags:

```
--addons          Comma-separated add-on keys (e.g. "auth,cache,security,testing")
--no-addons       Skip all add-ons
```

```
ajo --headless --name myblog --preset ninja-api --addons auth,security,testing
```

### 7.3 Argparse Changes

Add to `build_parser()` in `ajo/cli.py`:

```python
parser.add_argument(
    "--addons",
    type=str,
    default="",
    help="Comma-separated add-on keys: auth, cache, security, testing",
)
parser.add_argument(
    "--no-addons",
    action="store_true",
    help="Skip all add-on selection",
)
```

### 7.4 Interactive Prompt (New Function)

```python
async def select_addons(preset_type: str) -> list[str]:
    """Interactive multi-select for add-ons after preset choice."""
    from ajo.presets.addons import get_addon_choices

    available = get_addon_choices(preset_type)
    if not available:
        return []

    selected = inquirer.checkbox(
        message="Add-ons (space to select):",
        choices=[
            Choice(value=key, name=f"{info['name']:20s} {info['description']}")
            for key, info in available.items()
        ],
        style=INQUIRER_STYLE,
        qmark="❯",
    ).execute()

    return selected
```

---

## 8. ScaffoldEngine Changes

### 8.1 New `execute()` Signature

```python
async def execute(
    self,
    preset: AbstractPreset | None = None,
    addons: list[AbstractAddon] | None = None,
) -> bool:
```

### 8.2 Modified Step Pipeline

The step list currently ends at step 9 (uv sync). We insert add-on steps between the preset step and uv sync:

```python
# After preset step, before uv sync:
if addons:
    for addon in addons:
        steps.append((
            f"Applying {addon.name} add-on",
            lambda a=addon: self._step_addon(a),
        ))
```

### 8.3 `_step_addon()` Implementation

```python
async def _step_addon(self, addon: AbstractAddon) -> None:
    """Run a single add-on's apply() with rollback support."""
    project_name = self.env_config.get("project_name", self.project_path.name)

    installed = str(self.project_path / "installed_addons.txt")
    try:
        await addon.apply(
            project_path=self.project_path,
            project_name=project_name,
            env_config=self.env_config,
        )
        # Track applied add-ons for rollback
        with open(installed, "a") as f:
            f.write(f"{addon.__class__.__name__}\n")
    except OSError as exc:
        raise PresetError(f"Add-on {addon.name} failed: {exc}") from exc

    self._rollback.push(
        f"rollback add-on {addon.name}",
        lambda: self._rollback_addon(addon),
    )
```

### 8.4 Add-on Dependency Installation

If an add-on has `dependencies` or `dev_dependencies`, we install them. Currently, the engine installs preset deps in steps 4-5, then runs the preset scaffold. Add-on deps should be installed **before** the add-on's `apply()` runs.

Modified step order:

```
1. Create directory
2. .env
3. .gitignore
4. Install preset deps
5. Install preset dev-deps
6. Git init
7. uv init
8. Run preset scaffold
9. Install add-on deps (NEW — for all add-ons combined)
10. Install add-on dev-deps (NEW)
11. Run each add-on apply() (NEW)
12. uv sync
```

### 8.5 Config Block

Add to `env_config`:

```python
env_config["addons"] = [addon.__class__.__name__ for addon in (addons or [])]
```

This allows add-ons to know which other add-ons are active (e.g., the auth add-on can adapt if the testing add-on is also selected — generating test factories for the User model).

---

## 9. Implementation Phases

### Phase 1: Add-on Foundation (Day 1-2)

| Task | Files | Details |
|------|-------|---------|
| 1.1 Create `ajo/presets/addons/` package | `addons/__init__.py` | `AbstractAddon`, `ADDON_REGISTRY`, `register_addon()`, `get_addon()`, `resolve_addons()` |
| 1.2 Create `SettingsInjector` | `addons/_settings.py` | `inject_apps()`, `inject_middleware()`, `append_block()` |
| 1.3 Update `ScaffoldEngine` | `scaffolding/engine.py` | `addons` parameter, `_step_addon()`, modified step pipeline |
| 1.4 Update CLI argparser | `cli.py` | `--addons`, `--no-addons` flags |

**Verification:** `import ajo.presets.addons` works, registry populates, `SettingsInjector` can parse and inject into a sample settings.py

### Phase 2: Auth Add-on (Day 3-4)

| Task | Files | Details |
|------|-------|---------|
| 2.1 Create `AuthAddon` | `addons/auth.py` | `@register_addon`, implement `apply()` |
| 2.2 Generate `accounts/` app | `addons/auth.py` | `models.py`, `admin.py`, `forms.py`, `apps.py` |
| 2.3 Generate API endpoints (DRF path) | `addons/auth.py` | If preset is rest-api, generate serializers/views/urls |
| 2.4 Generate API endpoints (Ninja path) | `addons/auth.py` | If preset is ninja-api, generate schemas/endpoints |
| 2.5 Generate templates | `addons/auth.py` | Login, signup, password-reset Bootstrap 5 templates |
| 2.6 Inject settings | `addons/auth.py` | `AUTH_USER_MODEL`, JWT config, `INSTALLED_APPS` |
| 2.7 Inject URLs | `addons/auth.py` | Wire `/accounts/`, `/api/auth/` into root urlconf |

**Verification:** Scaffold a Ninja API project with auth add-on, verify `accounts/` app exists, verify settings contain `AUTH_USER_MODEL`, verify `/api/auth/` endpoints exist

### Phase 3: Cache Add-on (Day 5)

| Task | Files | Details |
|------|-------|---------|
| 3.1 Create `CacheAddon` | `addons/cache.py` | `@register_addon`, implement `apply()` |
| 3.2 Inject Redis cache block | `addons/cache.py` | `CACHES` with `django_redis.RedisCache` |
| 3.3 Inject middleware | `addons/cache.py` | `UpdateCacheMiddleware` + `FetchFromCacheMiddleware` with correct ordering |
| 3.4 Generate demo view | `addons/cache.py` | `core/views.py` with `@cache_page` |

**Verification:** Scaffold a monolith project with cache add-on, verify `CACHES` in settings, verify middleware order

### Phase 4: Security Add-on (Day 6)

| Task | Files | Details |
|------|-------|---------|
| 4.1 Create `SecurityAddon` | `addons/security.py` | `@register_addon`, implement `apply()` |
| 4.2 Inject axes config | `addons/security.py` | `INSTALLED_APPS`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS`, `AXES_*` |
| 4.3 Inject CSP config | `addons/security.py` | `CSP_*` settings |
| 4.4 Inject HTTPS/Secure config | `addons/security.py` | All `SECURE_*`, `SESSION_COOKIE_*`, `CSRF_COOKIE_*` |
| 4.5 Inject middleware | `addons/security.py` | CSP middleware |
| 4.6 .env additions | `addons/security.py` | `AXES_ENABLED`, `AXES_FAILURE_LIMIT`, `SECURE_SSL_REDIRECT` |

**Verification:** Scaffold with security add-on, verify all security settings present, verify `axes` is importable

### Phase 5: Testing Add-on (Day 7-8)

| Task | Files | Details |
|------|-------|---------|
| 5.1 Create `TestingAddon` | `addons/testing.py` | `@register_addon`, implement `apply()` |
| 5.2 Inject pytest config | `addons/testing.py` | `pyproject.toml` tool config or `pytest.ini` |
| 5.3 Inject coverage config | `addons/testing.py` | `.coveragerc` or `pyproject.toml` |
| 5.4 Generate per-app test dirs | `addons/testing.py` | `tests/__init__.py`, `conftest.py` |
| 5.5 Generate factories | `addons/testing.py` | Use AST analyzer to discover models, generate factory classes |
| 5.6 Generate test stubs | `addons/testing.py` | `test_models.py`, `test_apis.py` with auto-generated test methods |
| 5.7 Generate base test class | `addons/testing.py` | `core/tests/base.py` with `api_client`, `auth_client`, `user` fixtures |

**Verification:** Scaffold with testing add-on, verify `pytest.ini` exists, verify `tests/factories.py` exists for each app, verify factories reference correct models

### Phase 6: CLI Integration & Polish (Day 9-10)

| Task | Files | Details |
|------|-------|---------|
| 6.1 Interactive add-on selection | `cli.py` | `select_addons()` function |
| 6.2 Headless add-on parsing | `cli.py` | Parse `--addons` flag, validate against registry |
| 6.3 Conflict detection UI | `addons/__init__.py` | Show warning when conflicting add-ons selected |
| 6.4 Compatibility filtering | `addons/__init__.py` | Hide add-ons incompatible with chosen preset |
| 6.5 Update show_features | `cli.py` | Show add-on options in features display |
| 6.6 Edge case handling | `cli.py` | Empty addons list, all addons, re-scaffold without addons |
| 6.7 Add NF icon constants | `constants.py` | New icons for add-on features (optional) |

**Verification:** Full interactive flow: pick preset → pick add-ons → scaffold → verify all files generated

---

## 10. File Manifest

### New Files (8)

| File | Purpose |
|------|---------|
| `ajo/presets/addons/__init__.py` | `AbstractAddon`, `ADDON_REGISTRY`, `register_addon()`, `get_addon()`, `resolve_addons()` |
| `ajo/presets/addons/_settings.py` | `SettingsInjector` class for structured settings.py manipulation |
| `ajo/presets/addons/auth.py` | `AuthAddon` — JWT auth, user registration, profile API, login templates |
| `ajo/presets/addons/cache.py` | `CacheAddon` — Redis cache backend, session caching, middleware |
| `ajo/presets/addons/security.py` | `SecurityAddon` — django-axes, CSP, HTTPS, secure cookies |
| `ajo/presets/addons/testing.py` | `TestingAddon` — pytest, factories, coverage, test stubs |

### Modified Files (4)

| File | Change |
|------|--------|
| `ajo/cli.py` | Add `--addons`/`--no-addons` flags, `select_addons()` interactive prompt, `_headless_execute` addons passthrough |
| `ajo/scaffolding/engine.py` | Add `addons` parameter to `execute()`, `_step_addon()`, modified step pipeline |
| `ajo/core/constants.py` | (Optional) New NF icons for add-on features |
| `.opencode/plans/04_addons_module_system.md` | This file |

### Files Generated by Add-ons (at scaffold time)

| Add-on | Generated Files |
|--------|-----------------|
| **auth** | `accounts/models.py`, `accounts/admin.py`, `accounts/forms.py`, `accounts/apps.py`, `accounts/api/serializers.py` (DRF), `accounts/api/views.py` (DRF), `accounts/api/urls.py` (DRF), `accounts/api/schemas.py` (Ninja), `accounts/api/endpoints.py` (Ninja), `templates/registration/*.html` (6 files) |
| **cache** | `core/views.py`, `core/urls.py` |
| **security** | (none — all config injection) |
| **testing** | `pytest.ini`, `.coveragerc`, `{app}/tests/__init__.py`, `{app}/tests/factories.py`, `{app}/tests/test_models.py`, `{app}/tests/test_apis.py`, `{app}/tests/conftest.py`, `core/tests/base.py` |

---

## 11. Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **settings.py string matching breaks** with non-standard formatting | Medium | High | Use AST-based settings parser (`_settings.py`) instead of regex. Fall back to `append_block()` if parsing fails. |
| **Add-on conflicts** (e.g., two add-ons both inject `AUTH_USER_MODEL`) | Low | High | `resolve_addons()` checks `conflicts_with`. First-come-first-served with warning. |
| **Middleware ordering wrong** (cache middleware must be first/last) | Medium | Medium | `SettingsInjector` uses positional markers (`# FIRST` / `# LAST`) for ordering-sensitive middleware. |
| **Custom User model migration** fails if `AUTH_USER_MODEL` set after first migration | Low | Medium | Set `AUTH_USER_MODEL` before any migration runs. ScaffoldEngine doesn't run `migrate`, so this is safe. |
| **pytest config conflicts** with existing project configuration | Low | Low | Only inject if no existing pytest config found. |
| **auth add-on incompatible** with GraphQL preset | Medium | Low | `compatible_presets` on `AuthAddon` excludes GraphQL if JWT integration is unclear. Show clear warning. |
| **django-axes migration** needed but not run | Medium | Low | Add note in completion message. The user runs `migrate` themselves. |
| **.env vars duplicated** across add-ons (e.g., both auth and security write `SECRET_KEY`) | Low | Low | Deduplicate env vars across add-ons before writing. |

---

## 12. Testing Strategy

### 12.1 Unit Tests (per add-on)

| Test | What it verifies |
|------|-----------------|
| `test_settings_injector.py` | `SettingsInjector` correctly adds apps, middleware, and blocks to sample settings.py |
| `test_registry.py` | All add-ons registered, `get_addon()` lookup, `resolve_addons()` ordering |
| `test_auth_addon.py` | `AuthAddon.apply()` generates correct files for each preset type |
| `test_cache_addon.py` | `CacheAddon.apply()` injects correct CACHES block and middleware |
| `test_security_addon.py` | `SecurityAddon.apply()` injects axes, CSP, secure settings |
| `test_testing_addon.py` | `TestingAddon.apply()` generates pytest config, factories, test dirs |

### 12.2 Integration Tests

| Test | What it verifies |
|------|-----------------|
| `test_scaffold_with_addons.py` | Full scaffold pipeline with all 4 add-ons, verify all files exist |
| `test_headless_addons.py` | `--preset ninja-api --addons auth,cache,security,testing` creates correct project |
| `test_addon_compatibility.py` | Incompatible preset+addon combinations raise clear errors |
| `test_addon_rollback.py` | If add-on fails, project directory is cleaned up |

### 12.3 Generated Project Verification

| Test | What it verifies |
|------|-----------------|
| `test_generated_settings.py` | Generated settings.py is valid Python |
| `test_generated_urls.py` | Generated urls.py can be imported (no ImportError) |
| `test_generated_models.py` | Generated models.py contains valid Django model classes |
| `test_generated_factories.py` | Generated factories.py references correct model classes |

---

## Appendix A: `ajo/presets/addons/__init__.py` — Full Specification

```python
"""Composable add-on module system.

Add-ons are lightweight, composable feature modules that layer onto
any architecture preset after the main scaffold step.  They handle
settings injection, file generation, and dependency installation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ajo.core.exceptions import PresetError


# ── Registry ────────────────────────────────────────────────────────────

ADDON_REGISTRY: dict[str, type[AbstractAddon]] = {}
"""Mapping of add-on keys (e.g. ``"auth"``, ``"cache"``) to their
concrete :class:`AbstractAddon` subclasses."""


def register_addon(
    cls: type[AbstractAddon],
) -> type[AbstractAddon]:
    """Decorator / direct-call to register an add-on class.

    Usage::

        @register_addon
        class AuthAddon(AbstractAddon):
            ...
    """
    key = cls.__name__.replace("Addon", "").lower()
    if key in ADDON_REGISTRY:
        raise PresetError(
            f"Add-on {key!r} already registered "
            f"({ADDON_REGISTRY[key].__name__})"
        )
    ADDON_REGISTRY[key] = cls
    return cls


def get_addon(key: str) -> type[AbstractAddon]:
    """Look up an add-on class by its registry key."""
    try:
        return ADDON_REGISTRY[key]
    except KeyError:
        available = ", ".join(sorted(ADDON_REGISTRY))
        raise PresetError(
            f"Unknown add-on {key!r}. Available: {available}"
        ) from None


def resolve_addons(
    selected: list[str],
    preset_key: str | None = None,
) -> list[AbstractAddon]:
    """Resolve, validate, and order a list of add-on keys.

    Args:
        selected: List of add-on keys (e.g. ``["auth", "cache"]``).
        preset_key: The preset being used (for compatibility checks).

    Returns:
        Ordered list of instantiated add-on objects.

    Raises:
        PresetError: If any add-on is incompatible with the preset
            or conflicts with another selected add-on.
    """
    addons: list[AbstractAddon] = []
    seen: set[str] = set()

    for key in selected:
        cls = get_addon(key)
        instance = cls()

        # Compatibility check
        if (
            preset_key
            and instance.compatible_presets is not None
            and preset_key not in instance.compatible_presets
        ):
            raise PresetError(
                f"Add-on '{key}' is not compatible with "
                f"preset '{preset_key}'"
            )

        # Conflict check
        for conflict in instance.conflicts_with:
            if conflict in seen:
                raise PresetError(
                    f"Add-on '{key}' conflicts with '{conflict}'"
                )

        addons.append(instance)
        seen.add(key)

    return addons


def get_addon_choices(
    preset_key: str | None = None,
) -> dict[str, dict[str, str]]:
    """Return available add-ons as a dict for InquirerPy checkbox.

    Filters out add-ons incompatible with *preset_key*.

    Returns:
        ``{"auth": {"name": "Auth & Users", "description": "..."}, ...}``
    """
    choices: dict[str, dict[str, str]] = {}
    for key, cls in sorted(ADDON_REGISTRY.items()):
        instance = cls()
        if (
            preset_key
            and instance.compatible_presets is not None
            and preset_key not in instance.compatible_presets
        ):
            continue  # Skip incompatible
        choices[key] = {
            "name": instance.name,
            "description": instance.description,
        }
    return choices


# ── Abstract base ───────────────────────────────────────────────────────


class AbstractAddon(ABC):
    """Base class for composable feature add-ons.

    Subclasses define what settings to inject, files to generate, and
    dependencies to install when applied to a scaffolded project.
    """

    # ── Metadata (override in subclasses) ─────────────────────────────

    name: str = ""
    description: str = ""

    #: Extra PyPI packages to install (added to ``uv add``).
    dependencies: list[str] = []

    #: Extra dev-only PyPI packages (added to ``uv add --dev``).
    dev_dependencies: list[str] = []

    #: If not ``None``, only these preset keys are compatible.
    #: ``None`` means compatible with all presets.
    compatible_presets: list[str] | None = None

    #: Add-on keys that conflict with this one.
    conflicts_with: list[str] = []

    # ── Settings / config templates (override in subclasses) ──────────

    #: App labels to inject into ``INSTALLED_APPS``.
    installed_apps: list[str] = []

    #: Middleware class paths to inject into ``MIDDLEWARE``.
    #: Use ``("path", "first")`` to insert at the beginning,
    #: ``("path", "last")`` to append at the end.
    middleware: list[tuple[str, str]] = []

    #: ``(url_path, import_string)`` tuples for urlpatterns.
    url_patterns: list[tuple[str, str]] = []

    #: Environment variables to add to ``.env``.
    env_vars: dict[str, str] = {}

    #: Raw Python code blocks to append to ``settings.py``.
    settings_blocks: list[str] = []

    # ── Abstract method ───────────────────────────────────────────────

    @abstractmethod
    async def apply(
        self,
        project_path: Path,
        project_name: str,
        env_config: dict[str, Any],
    ) -> None:
        """Execute add-on scaffolding.

        This method is called **after** the main preset scaffold
        has created the Django project structure.  Implementations
        should:

        * Create additional app directories and files.
        * Call ``self._inject_settings()`` to modify ``settings.py``.
        * Call ``self._wire_urls()`` to modify ``urls.py``.
        * Call ``self._update_env()`` to extend ``.env``.

        Args:
            project_path: Root directory of the scaffolded project.
            project_name: Django project package name.
            env_config: Project-wide configuration (db, secret key, etc.).
        """
        ...

    # ── Concrete helpers ──────────────────────────────────────────────

    async def _inject_settings(self, project_path: Path) -> None:
        """Inject installed_apps, middleware, and settings_blocks
        into the project's ``settings.py``."""
        ...

    async def _wire_urls(self, project_path: Path, project_name: str) -> None:
        """Add url_patterns to the project's ``urls.py``."""
        ...

    async def _update_env(self, project_path: Path) -> None:
        """Append env_vars to ``.env``."""
        ...

    def _write_file(
        self,
        path: Path,
        content: str,
        *,
        overwrite: bool = False,
    ) -> None:
        """Write a file, creating parent directories."""
        ...

    def _discover_apps(self, project_path: Path) -> list[str]:
        """Return list of discovered Django app directories."""
        ...

    @classmethod
    def registry_key(cls) -> str:
        """Derive registry key from class name."""
        return cls.__name__.replace("Addon", "").lower()


# ── Lazy import add-on implementations so they register themselves ──────

from ajo.presets.addons.auth import AuthAddon  # noqa: E402, F811
from ajo.presets.addons.cache import CacheAddon  # noqa: E402, F811
from ajo.presets.addons.security import SecurityAddon  # noqa: E402, F811
from ajo.presets.addons.testing import TestingAddon  # noqa: E402, F811

__all__ = [
    "ADDON_REGISTRY",
    "register_addon",
    "get_addon",
    "resolve_addons",
    "get_addon_choices",
    "AbstractAddon",
]
```
