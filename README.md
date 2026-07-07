<p align="center">
  <img src="./logo.png" width="140" alt="AJO CLI Logo">
</p>

<h1 align="center">AJO</h1>
<p align="center"><em>Professional Django Scaffolder with Cyberpunk TUI</em></p>

<p align="center">
  <img src="https://img.shields.io/pypi/v/ajo-cli?color=%2300f2fe&style=flat-square" alt="PyPI">
  <img src="https://img.shields.io/pypi/pyversions/ajo-cli?color=%234facfe&style=flat-square" alt="Python">
  <img src="https://img.shields.io/aur/version/ajo-cli?color=%23f355da&style=flat-square" alt="AUR">
  <img src="https://img.shields.io/github/license/zaidejjo/ajo-cli?color=%2300ffcc&style=flat-square" alt="License">
</p>

<p align="center">
  <a href="#english">🇺🇸 English</a> · <a href="#العربية">🇸🇦 العربية</a>
</p>

<p align="center">
  <a href="https://ajo-cli.pages.dev"><strong>🌐 Explore the Website & Web Simulator</strong></a>
</p>

---

## English

**AJO** is an interactive CLI tool that generates production-ready Django projects with a beautiful cyberpunk-themed terminal UI. Pick your architecture, database, and add-on modules — ajo handles the rest.

```bash
ajo       # Interactive mode
ajo --headless --name myproject -p rest-api -d postgresql
```

### ✨ Features

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

### 🚀 Installation

#### Recommended (One-liner Scripts)

The fastest way to install AJO on any platform.

**macOS / Linux**

```bash
curl -fsSL https://ajo-cli.pages.dev/install | sh
```

**Windows (PowerShell)**

```powershell
iwr -useb https://ajo-cli.pages.dev/install.ps1 | iex
```

#### Alternative Methods

If you prefer a specific package manager:

```bash
# Using uv (isolated, fastest)
uv tool install ajo-cli

# Using pipx (isolated)
pipx install ajo-cli

# Using pip (global)
pip install ajo-cli
```

#### AUR (Arch Linux)

```bash
yay -S ajo-cli
# or
paru -S ajo-cli
```

#### From Source

```bash
git clone https://github.com/zaidejjo/ajo-cli.git
cd ajo-cli
uv sync
ajo --version
```

### 🏗️ Architecture Presets

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

### 🧩 Add-on Modules

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

### 🎨 Themes

AJO ships with three visual themes. Pass `--theme` to switch:

```bash
ajo --theme cyberpunk          # Neon cyan (default)
ajo --theme dracula            # Dracula purple/pink
ajo --theme monochromatic      # Clean greyscale/blue
ajo --theme mono               # Alias for monochromatic
```

Themes are applied to both the Rich terminal output and all InquirerPy interactive prompts. Terminal colour depth (TrueColor, 256, 16) is auto-detected.

### ⚡ Quickstart

#### Create a new Django project (interactive)

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

#### One-shot (headless)

```bash
ajo --headless --name myproject \
    --preset rest-api \
    --database postgresql \
    --addons auth cache testing \
    --no-github
```

**Flags:**

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

### 🤖 Smart CLI — Manage Existing Projects

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

### 🩺 Diagnostics

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

### 🐳 Docker

The **Docker preset** generates a production-ready container setup:

```bash
ajo --preset docker
```

Creates:
- **Dockerfile** — Multi-stage build with uv caching, `python manage.py collectstatic`
- **docker-compose.yml** — `web` service + PostgreSQL/MySQL + Redis + Mailhog
- **.dockerignore** — venv, cache, git

Optionally integrates with Celery worker.

### ⚙️ Persistent Configuration

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

### 🛠️ Development

#### Setup

```bash
git clone https://github.com/zaidejjo/ajo-cli.git
cd ajo-cli
uv sync
```

#### Run tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=ajo

# Specific file
uv run pytest tests/test_config.py -v
```

#### Project structure

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

### 📋 Requirements

- **Python 3.10+**
- **uv** — the Astral Python package manager (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **git** — optional, for version control
- **GitHub CLI (`gh`)** — optional, for GitHub repo creation

### 📄 License

MIT — see [LICENSE](LICENSE).

---

## العربية

<p dir="rtl">
<strong>AJO</strong> هو أداة CLI تفاعلية لتوليد مشاريع Django جاهزة للإنتاج مع واجهة مستخدم طرفية (TUI) ذات طابع Cyberpunk جميل. اختر بنية مشروعك، قاعدة البيانات، والوحدات الإضافية — وسيقوم ajo بالباقي.
</p>

```bash
ajo       # الوضع التفاعلي
ajo --headless --name myproject -p rest-api -d postgresql
```

### ✨ المميزات

<p dir="rtl">

| | الميزة | |
|---|---|---|
| 🗄️ | **دعم متعدد قواعد البيانات** — PostgreSQL, MySQL, SQLite | 🐙 |
| **تكامل GitHub** — إنشاء ورفع repo تلقائي | 🔄 |
| **CI/CD مع Ruff** — خط أنابيب GitHub Actions | 🔒 |
| **أمان .env** — مفاتيح secrets تُولد تلقائيًا | 📦 |
| **تطبيقات متعددة** — أنشئ أي عدد من التطبيقات | 🧪 |
| **اختبارات** — pytest مع تغطية و factory-boy | 🐳 |
| **دعم Docker** — Dockerfile + Compose + Redis + Mailhog | 🎨 |
| **ثيمات Bootstrap 5** — ثيمات UI جاهزة | 🛠️ |
| **Django Shell Plus** — shell محسّن | 🔍 |
| **Debug Toolbar** — أدوات تصحيح للتطوير | 🐙 |

</p>

### 🚀 التثبيت

#### الموصى به (سكريبت بنقرة واحدة)

<p dir="rtl">أسرع طريقة لتثبيت AJO على أي نظام تشغيل.</p>

**macOS / Linux**

```bash
curl -fsSL https://ajo-cli.pages.dev/install | sh
```

**Windows (PowerShell)**

```powershell
iwr -useb https://ajo-cli.pages.dev/install.ps1 | iex
```

#### طرق بديلة

<p dir="rtl">إذا كنت تفضل مدير حزمات محدد:</p>

```bash
# باستخدام uv (معزول، الأسرع)
uv tool install ajo-cli

# باستخدام pipx (معزول)
pipx install ajo-cli

# باستخدام pip (عام)
pip install ajo-cli
```

#### AUR (Arch Linux)

```bash
yay -S ajo-cli
# أو
paru -S ajo-cli
```

#### من المصدر

```bash
git clone https://github.com/zaidejjo/ajo-cli.git
cd ajo-cli
uv sync
ajo --version
```

### 🏗️ قوالب البنية (Presets)

<p dir="rtl">اختر الأساس الذي يناسب مشروعك:</p>

<p dir="rtl">

| القالب | المفتاح | التقنية |
|---|---|---|
| **Monolith قياسي** | `monolith` | Django + Bootstrap 5 + HTMX |
| **REST API جاهز** | `rest-api` | DRF + JWT + CORS + Swagger/OpenAPI |
| **Ninja API** | `ninja-api` | django-ninja + Pydantic + Swagger UI |
| **GraphQL API** | `graphql-api` | Graphene + Relay + GraphiQL IDE |
| **Docker** | `docker` | Dockerfile متعدد المراحل + Compose (PostgreSQL, Redis, Mailhog) |

</p>

<p dir="rtl">
كل قالب يولد مشروع Django كامل يتضمن:
</p>

- `manage.py`, الإعدادات, URLs, WSGI/ASGI
- `.env` مع `SECRET_KEY` تُولد تلقائيًا
- `.gitignore` وفق أفضل ممارسات Django
- `pyproject.toml` مع إدارة التبعيات عبر `uv`

<p dir="rtl">
قوالب REST API, Ninja API, و GraphQL API هي <strong>model-aware</strong> — أي أنها تولد تلقائيًا serializers, viewsets, routers, و endpoints عبر تحليل AST للنماذج.
</p>

### 🧩 الوحدات الإضافية (Add-ons)

<p dir="rtl">أضف ميزات اختيارية فوق أي قالب:</p>

<p dir="rtl">

| الوحدة | المفتاح | ما تضيفه |
|---|---|---|
| **التوثيق والمستخدمين** | `auth` | JWT auth (SimpleJWT), نموذج `User` مخصص مع bio/avatar, تسجيل/دخول, endpoints حسب القالب |
| **التخزين المؤقت والأداء** | `cache` | Redis caching (`django-redis`), DB connection pooling, `django-debug-toolbar` |
| **تقوية الأمان** | `security` | حماية brute-force (`django-axes`), TOTP 2FA (`django-otp`), CSP headers, HSTS/XSS/CSRF |
| **بنية الاختبارات** | `testing` | pytest + pytest-django, coverage (fail-under 80%), factory-boy, اختبارات API تُولد تلقائيًا |

</p>

<p dir="rtl">اختر الوحدات تفاعليًا باستخدام <code>&lt;space&gt;</code> أثناء التثبيت، أو مررها عبر <code>--addons</code>:</p>

```bash
ajo --addons auth cache testing
```

### 🎨 الثيمات

<p dir="rtl">AJO يأتي بثلاث ثيمات بصرية. استخدم <code>--theme</code> للتبديل:</p>

```bash
ajo --theme cyberpunk          # Neon cyan (افتراضي)
ajo --theme dracula            # Dracula purple/pink
ajo --theme monochromatic      # Clean greyscale/blue
ajo --theme mono               # Alias لـ monochromatic
```

### ⚡ البداية السريعة

#### إنشاء مشروع Django جديد (تفاعلي)

```bash
ajo
```

<p dir="rtl">اتبع التعليمات:</p>
<ol dir="rtl">
<li>اختر <strong>اسم المشروع</strong></li>
<li>اختر <strong>قالب البنية</strong> (Monolith, REST API, Ninja API, GraphQL API, Docker)</li>
<li>اختر <strong>قاعدة البيانات</strong> (SQLite, PostgreSQL, MySQL)</li>
<li>فعّل <strong>الوحدات الإضافية</strong> اختياريًا (auth, cache, security, testing)</li>
<li>راجع معاينة المشروع</li>
<li>أكد — سيقوم ajo بإنشاء المشروع، تثبيت التبعيات عبر <code>uv</code>، تهيئة git، وإنشاء repo على GitHub اختياريًا</li>
</ol>

#### الوضع غير التفاعلي (headless)

```bash
ajo --headless --name myproject \
    --preset rest-api \
    --database postgresql \
    --addons auth cache testing \
    --no-github
```

**الأعلام (Flags):**

<p dir="rtl">

| العلم | الافتراضي | الوصف |
|---|---|---|
| `-n, --name` | — | اسم المشروع |
| `-p, --preset` | `monolith` | قالب البنية |
| `-d, --database` | `sqlite` | نوع قاعدة البيانات |
| `-y, --yes` | — | قبول جميع الإعدادات الافتراضية (يضمن `--headless`) |
| `--addons` | — | وحدات إضافية (مفصولة بمسافات) |
| `--no-github` | — | تخطي إنشاء repo على GitHub |
| `--no-cicd` | — | تخطي إعداد CI/CD |
| `--output-dir` | `.` | المجلد الأب للمشروع |
| `--theme` | `cyberpunk` | الثيم البصري |
| `--headless` | — | الوضع غير التفاعلي |

</p>

### 🤖 Smart CLI — إدارة المشاريع الحالية

<p dir="rtl">شغّل <code>ajo</code> داخل مجلد مشروع Django موجود:</p>

```bash
cd myproject
ajo
```

<p dir="rtl">AJO يكتشف مشروعك ويعرض <strong>قائمة سياقية</strong> من الأوامر:</p>

<p dir="rtl">

| الأمر | متى يظهر |
|---|---|
| Run Server | دائمًا |
| Create Superuser | عند عدم وجود superuser (يُبرز كعاجل) |
| Run Tests | دائمًا |
| Create App | دائمًا |
| Django Shell | دائمًا |
| Make Migrations | عند اكتشاف تغييرات في النماذج (يُبرز كعاجل) |
| Apply Migrations | عند وجود migrations غير مطبقة (يُبرز كعاجل) |
| Fix Ruff Issues | عند وجود مشاكل في Ruff (يُبرز كعاجل) |
| Clear Cache | دائمًا |
| Run Diagnostics | دائمًا — فحص misconfigurations مع auto-fix |

</p>

<p dir="rtl">القائمة الذكية تعرض أيضًا <strong>لوحة معلومات حية</strong> تحتوي على بيانات المشروع، الفرع، حالة virtualenv، حالة الخادم، حالة migrations، وحالة Ruff — كلها تُحدَّث في الوقت الفعلي.</p>

### 🩺 التشخيصات (Diagnostics)

<p dir="rtl">AJO يتضمن محرك تشخيصي ذاتي يفحص مشروع Django للمشاكل الشائعة ويقدم <strong>إصلاحات تلقائية بنقرة واحدة</strong>:</p>

<p dir="rtl">

| الفحص | الإصلاح التلقائي |
|---|---|
| تطبيقات contrib مفقودة في `INSTALLED_APPS` | يضيفها |
| `ALLOWED_HOSTS` مفقود | يضيف `["*"]` |
| `DEBUG=True` مكتوب ثابتًا في الإنتاج | يطلب الإصلاح |
| `SECRET_KEY` مفقود أو placeholder | يولد مفتاح آمن من 50 حرفًا |
| مسار admin مفقود في URLconf الجذر | يربط مسار `admin/` |
| بادئات migrations مكررة | يعيد تسميتها بالرقم التالي المتاح |

</p>

<p dir="rtl">شغّل التشخيصات من قائمة Smart CLI أو مباشرة.</p>

### 🐳 Docker

<p dir="rtl">قالب <strong>Docker</strong> يولد إعداد container جاهز للإنتاج:</p>

```bash
ajo --preset docker
```

<p dir="rtl">يُنشئ:</p>

- **Dockerfile** — بناء متعدد المراحل مع uv caching, `python manage.py collectstatic`
- **docker-compose.yml** — خدمة `web` + PostgreSQL/MySQL + Redis + Mailhog
- **.dockerignore** — venv, cache, git

<p dir="rtl">يتكامل اختياريًا مع Celery worker.</p>

### ⚙️ الإعدادات المستمرة

<p dir="rtl">في أول تشغيل تفاعلي، يسألك AJO:</p>

```
? Do you use a Nerd Font in your terminal? (y/N)
```

<p dir="rtl">يُحفظ جوابك في <code>~/.config/ajo/config.json</code>:</p>

```json
{
  "version": 1,
  "nerd_fonts": true,
  "theme": null,
  "updated_at": "2026-06-17T12:00:00+00:00"
}
```

- `nerd_fonts`: يتحكم في استخدام أيقونات Nerd Font أو النصوص البديلة في TUI
- `theme`: محجوز لثيم مستمر في المستقبل

**ترتيب الأولوية للتجاوز:**
1. متغير البيئة `$NERD_FONTS`
2. القيمة المحفوظة في `config.json`
3. الكشف التلقائي (استدلال terminal emulator)
4. الافتراضي: text fallbacks

### 🛠️ التطوير

#### الإعداد

```bash
git clone https://github.com/zaidejjo/ajo-cli.git
cd ajo-cli
uv sync
```

#### تشغيل الاختبارات

```bash
# جميع الاختبارات
uv run pytest

# مع coverage
uv run pytest --cov=ajo

# ملف محدد
uv run pytest tests/test_config.py -v
```

#### هيكل المشروع

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

### 📋 المتطلبات

- **Python 3.10+**
- **uv** — مدير حزمات Python من Astral (التثبيت: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **git** — اختياري، لإدارة الإصدارات
- **GitHub CLI (`gh`)** — اختياري، لإنشاء repo على GitHub

### 📄 الترخيص

MIT — انظر [LICENSE](LICENSE).

---

<p align="center">
  <sub>Built with</sub>
  <br>
  <code>🐍 Python 3.10+</code> &nbsp;
  <code>🦄 Django 5.0+</code> &nbsp;
  <code>⚡ uv</code> &nbsp;
  <code>🦀 Ruff</code>
</p>
