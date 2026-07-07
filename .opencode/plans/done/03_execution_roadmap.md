# خطة: خارطة طريق التنفيذ المرحلي (Phased Implementation Roadmap)

**الملف المرجعي:** `.opencode/plans/03_execution_roadmap.md`
**النسخة:** 1.0
**تاريخ الإنشاء:** 2026-06-17
**اللغة:** العربية مع المصطلحات التقنية الإنجليزية

---

## جدول المحتويات

1. [نظرة عامة على الجدول الزمني](#1-نظرة-عامة-على-الجدول-الزمني)
2. [المرحلة الأولى: الأساس المُحسّن (الأسبوع 1)](#2-المرحلة-الأولى-الأساس-المحسّن-الأسبوع-1)
3. [المرحلة الثانية: الواجهة الذكية والسمات (الأسبوع 2)](#3-المرحلة-الثانية-الواجهة-الذكية-والسمات-الأسبوع-2)
4. [المرحلة الثالثة: التشخيص والـ IaC (الأسبوع 3)](#4-المرحلة-الثالثة-التشخيص-والـ-iac-الأسبوع-3)
5. [المرحلة الرابعة: الصقل والاختبارات والأداء (الأسبوع 4)](#5-المرحلة-الرابعة-الصقل-والاختبارات-والأداء-الأسبوع-4)
6. [معايير الأداء الإجبارية (Hard Performance Budgets)](#6-معايير-الأداء-الإجبارية-hard-performance-budgets)
7. [مصفوفة المخاطر والتخفيف](#7-مصفوفة-المخاطر-والتخفيف)

---

## 1. نظرة عامة على الجدول الزمني

| المرحلة | المدة | البداية | النهاية | التركيز |
|---------|-------|---------|---------|---------|
| **Phase 1** | 7 أيام | Day 1 | Day 7 | تحسين الـ TUI + الـ Theme Engine + Lazy Loading |
| **Phase 2** | 7 أيام | Day 8 | Day 14 | AST Parsing + Smart Injection + Fuzzy Finding |
| **Phase 3** | 7 أيام | Day 15 | Day 21 | Self-Healing Diagnostics + IaC Sync |
| **Phase 4** | 7 أيام | Day 22 | Day 28 | اختبارات شاملة + Benchmarking + التنظيف |

```
الأسبوع 1    ████████████████  Phase 1: TUI & Theme Engine
الأسبوع 2    ████████████████  Phase 2: AST & Smart Injection
الأسبوع 3    ████████████████  Phase 3: Diagnostics & IaC
الأسبوع 4    ████████████████  Phase 4: Testing & Performance
```

> **ملاحظة هامة:** لا يُسمح بالانتقال إلى المرحلة التالية إلا بعد اجتياز جميع اختبارات المرحلة الحالية و **Profilers Performance Gate**.

---

## 2. المرحلة الأولى: الأساس المُحسّن (الأسبوع 1)

### الهدف
تحسين سرعة بدء التشغيل (Startup Time) إلى < 50ms وإرساء بنية الـ TUI الجديدة مع الـ Theme Engine.

### 2.1 المهام التفصيلية

#### اليوم 1-2: Lazy Loading Architecture

| المهمة | الملف | التفاصيل |
|--------|-------|----------|
| إنشاء `LazyImportTracker` | `ajo/core/lazy_imports.py` (جديد) | كلاس يتتبع زمن الاستيراد ويُبلغ عن الوحدات البطيئة |
| تعديل `cli.py` لاستخدام Lazy Imports | `ajo/cli.py` | تحويل `from ajo.detector import ...` إلى استيرادات داخل الدوال |
| إنشاء `import_profile.py` (أداة) | `scripts/import_profile.py` (جديد) | سكريبت يحلل زمن الاستيراد باستخدام `-X importtime` |

**مثال الكود المُتوقع:**

```python
# داخل ajo/cli.py - هيكل الاستيرادات الجديد

# الاستيرادات السريعة (أقل من 5ms) - تظل في الأعلى
import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# الاستيرادات البطيئة - تتحول إلى Lazy
# ❌ قبل:
# from ajo.detector import DjangoProjectDetector
# from ajo.ui.theme import INQUIRER_STYLE

# ✅ بعد:
def _get_detector() -> "DjangoProjectDetector":
    from ajo.detector.project import DjangoProjectDetector
    return DjangoProjectDetector()

def _get_theme() -> "ThemeEngine":
    from ajo.ui.theme import ThemeEngine
    return ThemeEngine.get_instance()

def _get_inquirer_style() -> dict:
    return _get_theme().get_inquirer_style()
```

**اختبار القبول (Acceptance Test):**

```bash
# قياس زمن بدء التشغيل - يجب أن يكون < 50ms
hyperfine --warmup 5 --min-runs 20 'ajo --version'

# تحليل الاستيرادات
python -X importtime -c "from ajo.cli import main" 2> /tmp/import_timing.txt
python scripts/check_import_budget.py /tmp/import_timing.txt --max-total 50
```

#### اليوم 3-4: Terminal Capability Detection

| المهمة | الملف | التفاصيل |
|--------|-------|----------|
| إعادة هيكلة `capabilities.py` | `ajo/ui/capabilities.py` | إضافة `TerminalDetector` مع `ColorDepth`, `TerminalType`, `TerminalCapabilities` |
| إضافة كشف TrueColor | `ajo/ui/capabilities.py` | `_detect_color_depth()` باستخدام `COLORTERM` و fallbacks |
| إضافة كشف الحجم | `ajo/ui/capabilities.py` | `_get_terminal_size()` باستخدام `ioctl` |
| إضافة كشف Sixel/Sync | `ajo/ui/capabilities.py` | `_detect_sixel()`, `_detect_sync_output()` |
| إضافة `ColorDepth.adapt_to_depth()` | `ajo/ui/theme.py` | تحويل الألوان حسب عمق الطرفية |

**اختبار القبول:**

```bash
pytest tests/ui/test_capabilities_detection.py -v --coverage
# يجب أن يمر > 90% من حالات الاختبار
```

#### اليوم 5-7: Theme Engine متعدد السمات

| المهمة | الملف | التفاصيل |
|--------|-------|----------|
| إنشاء `ThemePalette` | `ajo/ui/theme.py` | `@dataclass` بلوحة ألوان كاملة (11+ لون) |
| إنشاء `ThemeEngine` | `ajo/ui/theme.py` | Singleton مع `get_instance()` |
| إضافة Cyberpunk Palette | `ajo/ui/theme.py` | الألوان الحالية من `Theme` |
| إضافة Dracula Palette | `ajo/ui/theme.py` | ألوان Dracula Theme |
| إضافة Monochromatic Palette | `ajo/ui/theme.py` | تدرجات الرمادي |
| إضافة `ThemeVariant` Enum | `ajo/core/constants.py` | `CYBERPUNK`, `DRACULA`, `MONOCHROMATIC` |
| تعديل INQUIRER_STYLE | `ajo/ui/theme.py` | جعله ديناميكياً من `ThemeEngine` |
| إضافة `--theme` CLI arg | `ajo/cli.py` | تعديل `build_parser()` |

**اختبار القبول:**

```bash
# اختبار التبديل بين السمات
ajo --theme cyberpunk --version
ajo --theme dracula --version
ajo --theme mono --version

# اختبار InquirerPy style لكل ثيم
pytest tests/ui/test_theme_engine.py -v
```

### 2.2 معايير النجاح للمرحلة الأولى

- [ ] Startup Time < 50ms (مقاسة بـ `hyperfine`).
- [ ] `LazyImportTracker` يكتشف أي استيراد > 5ms.
- [ ] `TerminalDetector` يعمل في < 5ms.
- [ ] التبديل بين 3 سمات يعمل بدون أخطاء.
- [ ] `INQUIRER_STYLE` يتغير ديناميكياً حسب الثيم.
- [ ] جميع اختبارات `tests/ui/` تمر بنسبة 100%.

---

## 3. المرحلة الثانية: الواجهة الذكية والسمات (الأسبوع 2)

### الهدف
بناء AST Parser لتحليل `models.py`، وتوليد Serializers و Views تلقائياً، وإضافة Fuzzy Finder.

### 3.1 المهام التفصيلية

#### اليوم 8-9: AST Parser Core

| المهمة | الملف | التفاصيل |
|--------|-------|----------|
| إنشاء `ModelRelationshipAnalyzer` | `ajo/detector/ast_analyzer.py` (جديد) | AST parser لملفات `models.py` |
| تنفيذ `_parse_models_file()` | `ajo/detector/ast_analyzer.py` | استخدام `ast.parse()` و `ast.walk()` |
| تنفيذ `_extract_field_info()` | `ajo/detector/ast_analyzer.py` | كشف ForeignKey, OneToOne, ManyToMany |
| تنفيذ `_inherits_from_model()` | `ajo/detector/ast_analyzer.py` | تتبع الوراثة حتى Abstract models |
| إضافة `ModelRelationship` dataclass | `ajo/detector/ast_analyzer.py` | لتخزين معلومات النموذج والحقول والعلاقات |

**اختبارات الوحدة:**

```python
# tests/detector/test_ast_analyzer.py

def test_parse_foreign_key():
    code = """
from django.db import models

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey('Author', on_delete=models.CASCADE, related_name='books')
"""
    analyzer = ModelRelationshipAnalyzer(Path("/tmp"))
    tree = ast.parse(code)
    analyzer._process_class(tree.body[1])  # ClassDef
    assert "Book" in analyzer.models
    assert len(analyzer.models["Book"].relations) == 1
    assert analyzer.models["Book"].relations[0]["type"] == "ForeignKey"
    assert analyzer.models["Book"].relations[0]["to"] == "Author"

def test_parse_many_to_many():
    code = """
from django.db import models

class Student(models.Model):
    name = models.CharField(max_length=100)
    courses = models.ManyToManyField('Course', through='Enrollment')
"""
    analyzer = ModelRelationshipAnalyzer(Path("/tmp"))
    tree = ast.parse(code)
    analyzer._process_class(tree.body[1])
    rel = analyzer.models["Student"].relations[0]
    assert rel["type"] == "ManyToManyField"
    assert rel.get("through") == "Enrollment"
```

#### اليوم 10-11: Smart Serializer/View Generator

| المهمة | الملف | التفاصيل |
|--------|-------|----------|
| إضافة `_generate_serializer_code()` | `ajo/presets/rest_api.py` | توليد Serializer من `ModelRelationship` |
| إضافة `_generate_viewset_code()` | `ajo/presets/rest_api.py` | توليد ModelViewSet مع Custom Actions للعلاقات |
| إضافة `_generate_urls_code()` | `ajo/presets/rest_api.py` | توليد DefaultRouter URLConf |
| إضافة `_detect_and_generate()` | `ajo/presets/rest_api.py` | دمج AST Parser + Generator |
| تعديل `scaffold()` في RestAPIPreset | `ajo/presets/rest_api.py` | استدعاء الـ Generator بعد الإنشاء |

**اختبارات التوليد:**

```python
# tests/presets/test_rest_api_generation.py

def test_serializer_generation():
    model = ModelRelationship("Book", [
        {"name": "title", "type": "CharField", "args": {"max_length": 200}},
    ], [
        {"type": "ForeignKey", "to": "Author", "related_name": "books"},
    ])
    
    preset = RestAPIPreset()
    code = preset._generate_serializer_code(model)
    
    assert "class BookSerializer(serializers.ModelSerializer):" in code
    assert "model = Book" in code
    assert "fields = '__all__'" in code

def test_viewset_with_relations():
    model = ModelRelationship("Author", [], [
        {"type": "OneToOneField", "to": "User", "related_name": "profile"},
    ])
    
    preset = RestAPIPreset()
    code = preset._generate_viewset_code(model)
    
    assert "class AuthorViewSet(viewsets.ModelViewSet):" in code
    assert "@action(detail=True, methods=['get'])" in code
    assert "def profile(self, request, pk=None):" in code
```

#### اليوم 12-14: Fuzzy Finder + Keyboard Manager + Sidebar

| المهمة | الملف | التفاصيل |
|--------|-------|----------|
| إنشاء `KeyboardManager` | `ajo/ui/keyboard.py` (جديد) | `KeyBinding` + `register()` + `handle()` |
| إنشاء `ZoneManager` | `ajo/ui/keyboard.py` (جديد) | تقسيم الشاشة إلى 6 Zones |
| إنشاء `FuzzyFinder` | `ajo/ui/fuzzy.py` (جديد) | `select_apps()` + `filter_commands()` |
| إنشاء `FileTreePreview` | `ajo/ui/theme.py` | `render()` باستخدام Rich Tree |
| تعديل `cli.py` للملاحة بالكيبورد | `ajo/cli.py` | إضافة `KeyboardManager` إلى الحدث الرئيسي |
| تعديل `cli.py` لإضافة Sidebar | `ajo/cli.py` | دمج `FileTreePreview` في تيار الإنشاء |

**اختبارات القبول:**

```bash
pytest tests/ui/test_keyboard_manager.py -v
pytest tests/ui/test_fuzzy_finder.py -v
pytest tests/ui/test_file_tree_preview.py -v
```

### 3.2 معايير النجاح للمرحلة الثانية

- [ ] `ModelRelationshipAnalyzer` يحلل `models.py` بنجاح في < 50ms.
- [ ] `RestAPIPreset.scaffold()` يولد Serializers + Views + URLs.
- [ ] العلاقات (FK, O2O, M2M) تُكتشف جميعها.
- [ ] `KeyboardManager` يستجيب لـ 6 Key Events على الأقل.
- [ ] `FileTreePreview` يعرض الشجرة الصحيحة لكل Preset.
- [ ] `FuzzyFinder` يفلتر قائمة من 50 عنصراً في < 10ms.

---

## 4. المرحلة الثالثة: التشخيص والـ IaC (الأسبوع 3)

### الهدف
بناء `DiagnosticEngine` مع Auto-Fix، و `DockerSyncEngine` لمزامنة إعدادات قاعدة البيانات مع Docker Compose.

### 4.1 المهام التفصيلية

#### اليوم 15-17: Self-Healing Diagnostics

| المهمة | الملف | التفاصيل |
|--------|-------|----------|
| إنشاء `DiagnosticIssue` | `ajo/validators.py` | `@dataclass` مع `severity`, `category`, `auto_fix` |
| إنشاء `DiagnosticEngine` | `ajo/validators.py` | `run_full_diagnostic()`, `_check_installed_apps()` |
| تنفيذ `_check_migration_conflicts()` | `ajo/validators.py` | تحليل أسماء ملفات الهجرات |
| تنفيذ `_check_settings_integrity()` | `ajo/validators.py` | التحقق من ALLOWED_HOSTS, SECRET_KEY, DEBUG |
| تنفيذ `_auto_add_app()` | `ajo/validators.py` | إضافة تطبيق إلى INSTALLED_APPS |
| تنفيذ `_auto_generate_secret_key()` | `ajo/validators.py` | توليد مفتاح آمن |
| إضافة `show_diagnostics()` | `ajo/cli.py` | واجهة تشخيص تفاعلية مع Auto-Fix |

**مخطط التدفق (Flow Diagram):**

```
User runs `ajo` in Django project
        │
        ▼
DiagnosticEngine.run_full_diagnostic()
        │
        ├── _check_installed_apps()
        │       └── يبحث في settings.py عن تطبيقات مفقودة
        │
        ├── _check_migration_conflicts()
        │       └── يفحص مجلدات migrations/
        │
        └── _check_settings_integrity()
                ├── ALLOWED_HOSTS
                ├── SECRET_KEY
                └── DEBUG
        │
        ▼
قائمة المشاكل (List[DiagnosticIssue])
        │
        ▼
لكل مشكلة: هل تريد Auto-Fix؟
        │
        ├── نعم → auto_fix() → show_success() أو show_error()
        └── لا → تخطي
```

**اختبارات التشخيص:**

```python
# tests/validators/test_diagnostic_engine.py

def test_detect_missing_app(tmp_path):
    """اختبار اكتشاف تطبيق مفقود من INSTALLED_APPS."""
    settings_py = tmp_path / "settings.py"
    settings_py.write_text("""
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
]
""")
    engine = DiagnosticEngine(tmp_path)
    issues = engine.run_full_diagnostic()
    
    # يجب أن يكتشف أن contenttypes و sessions و messages و staticfiles مفقودة
    app_issues = [i for i in issues if i.category == "installed_apps"]
    assert len(app_issues) >= 4

def test_auto_fix_adds_app(tmp_path):
    """اختبار أن Auto-Fix يضيف التطبيق فعلاً."""
    settings_py = tmp_path / "settings.py"
    settings_py.write_text("INSTALLED_APPS = [\n    'django.contrib.admin',\n]\n")
    content = settings_py.read_text()
    
    engine = DiagnosticEngine(tmp_path)
    assert engine._auto_add_app(settings_py, content, "django.contrib.auth")
    
    new_content = settings_py.read_text()
    assert "django.contrib.auth" in new_content

def test_migration_conflict(tmp_path):
    """اختبار اكتشاف تعارض في ترقيم الهجرات."""
    migrations = tmp_path / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "0001_initial.py").write_text("#")
    (migrations / "0001_duplicate.py").write_text("#")  # نفس الرقم
    
    engine = DiagnosticEngine(tmp_path)
    issues = engine.run_full_diagnostic()
    
    mig_issues = [i for i in issues if i.category == "migrations"]
    assert len(mig_issues) >= 1
```

#### اليوم 18-20: DockerSyncEngine

| المهمة | الملف | التفاصيل |
|--------|-------|----------|
| إنشاء `DockerServiceConfig` | `ajo/presets/docker_sync.py` (جديد) | `@dataclass` لتكوين خدمة Docker |
| إنشاء `DockerSyncEngine` | `ajo/presets/docker_sync.py` (جديد) | `generate_compose()` + `DB_SERVICE_MAP` |
| إضافة Health Check لكل DB | `ajo/presets/docker_sync.py` | PostgreSQL: `pg_isready`، MySQL: `mysqladmin ping` |
| إضافة Redis Health Check | `ajo/presets/docker_sync.py` | `redis-cli ping` |
| إضافة Celery اختياري | `ajo/presets/docker_sync.py` | `include_celery: bool = False` |
| تعديل `docker.py` لاستخدام `DockerSyncEngine` | `ajo/presets/docker.py` | ربط `_build_compose()` مع `DockerSyncEngine.generate_compose()` |
| إضافة `docker_service` إلى `database_manager.py` | `ajo/database_manager.py` | إضافة معلومات Docker لكل DB |

**اختبارات DockerSync:**

```bash
pytest tests/presets/test_docker_sync.py -v
# اختبار صحة YAML
python -c "
import yaml
compose = yaml.safe_load(open('test_docker_compose.yml'))
assert 'services' in compose
assert 'healthcheck' in compose['services']['db']
assert 'condition: service_healthy' in str(compose['services']['web']['depends_on'])
print('✓ Docker Compose is valid')
"
```

#### اليوم 21: التكامل والربط

| المهمة | التفاصيل |
|--------|----------|
| ربط `DiagnosticEngine` مع `DjangoProjectDetector` | `detect_slow_async()` يستدعي التشخيص |
| ربط `DockerSyncEngine` مع `ScaffoldEngine` | خطوة `_step_docker_sync` في الـ Pipeline |
| ربط AST Parser مع `SmartDjangoCLI` | إضافة أوامر ذكية (توليد Serializer، فحص العلاقات) |

### 4.2 معايير النجاح للمرحلة الثالثة

- [ ] `DiagnosticEngine` يكتشف 5+ أنواع من المشاكل.
- [ ] Auto-Fix يصلح 3+ أنواع مشاكل بنجاح.
- [ ] `DockerSyncEngine` يولد `docker-compose.yml` صالحاً.
- [ ] Health Checks تعمل لـ PostgreSQL و MySQL و Redis.
- [ ] `database_manager.py` يحتوي على معلومات Docker لكل DB.
- [ ] جميع الاختبارات تمر بنسبة 100%.

---

## 5. المرحلة الرابعة: الصقل والاختبارات والأداء (الأسبوع 4)

### الهدف
اختبارات شاملة، Benchmarking، تحسين الأداء، وتنظيف الكود.

### 5.1 المهام التفصيلية

#### اليوم 22-23: اختبارات شاملة (Integration Tests)

| المهمة | التفاصيل |
|--------|----------|
| اختبار تكامل AST + REST Preset | توليد مشروع Django وهمي، تحليله باستخدام AST، توليد Serializers |
| اختبار تكامل DockerSync + ScaffoldEngine | تشغيل `ScaffoldEngine.execute()` مع DockerPreset، التحقق من Compose |
| اختبار تكامل Diagnostics + CLI | محاكاة مشروع Django مع أخطاء، تشغيل `show_diagnostics()` |
| اختبار End-to-End Headless | تشغيل `ajo --headless -n test_project -d postgresql --preset rest-api` |

#### اليوم 24-25: Benchmarking و Profiling

```bash
# 1. Startup Time Benchmark
hyperfine --warmup 5 --min-runs 30 \
  --export-json /tmp/startup_benchmark.json \
  'ajo --version'

# 2. AST Parsing Benchmark
python -m pytest tests/detector/test_ast_benchmark.py --benchmark-only

# 3. Theme Switch Benchmark
python -m pytest tests/ui/test_theme_benchmark.py --benchmark-only

# 4. Docker Compose Generation Benchmark
python -m pytest tests/presets/test_docker_benchmark.py --benchmark-only

# 5. Diagnostic Engine Benchmark
python -m pytest tests/validators/test_diagnostic_benchmark.py --benchmark-only
```

**أداة الـ Performance Gate:**

```python
# scripts/performance_gate.py (ملف جديد)

import json
import sys
from pathlib import Path

class PerformanceGate:
    """
    بوابة الأداء - تمنع تمرير المرحلة إذا تجاوز الأداء الحدود.
    
    الأهداف الإجبارية (Hard Budgets):
    - Startup Time: < 50ms
    - AST Parse: < 100ms (لمشروع بـ 20 نموذج)
    - Docker Compose Gen: < 10ms
    - Theme Switch: < 5ms
    - Fuzzy Filter (50 items): < 10ms
    - Render Dashboard: < 10ms
    """
    
    BUDGETS: dict[str, float] = {
        "startup_time_ms": 50.0,
        "ast_parse_20_models_ms": 100.0,
        "docker_compose_generation_ms": 10.0,
        "theme_switch_ms": 5.0,
        "fuzzy_filter_50_ms": 10.0,
        "dashboard_render_ms": 10.0,
    }
    
    @classmethod
    def check(cls, benchmark_file: Path) -> bool:
        """يتحقق من أن كل المقاييس ضمن الحدود."""
        data = json.loads(benchmark_file.read_text())
        all_pass = True
        
        for metric, budget in cls.BUDGETS.items():
            actual = data.get(metric, float("inf"))
            status = "✓" if actual <= budget else "✗"
            all_pass = all_pass and (actual <= budget)
            print(f"  {status} {metric}: {actual:.1f}ms / {budget}ms budget")
        
        return all_pass
```

#### اليوم 26-27: تحسين الأداء النهائي

| التقنية | الملف | التوفير المتوقع |
|---------|-------|-----------------|
| إزالة الاستيرادات الحلقية | جميع الملفات | 10-20ms |
| استخدام `__slots__` في الـ Dataclasses | `ajo/detector/ast_analyzer.py` | 2-5ms |
| تحسين Regex في `_count_app_models()` | `ajo/detector/project.py` | 1-3ms |
| إضافة `functools.lru_cache` للدوال المتكررة | `ajo/detector/project.py` | 5-10ms |
| استخدام `pathlib.Path.read_text()` بدل `open()` | جميع الملفات | 1-2ms |
| تقليل استدعاءات Rich theme | `ajo/ui/theme.py` | 3-5ms |

#### اليوم 28: التنظيف النهائي والتوثيق

| المهمة | التفاصيل |
|--------|----------|
| إزالة `DjangoProjectScaffolder` القديم | `ajo/templates/django_app.py` - تحويل الـ Interactive TUI لاستخدام `ScaffoldEngine` |
| تحديث `pyproject.toml` | إضافة `[tool.benchmark]` و `[tool.performance]` |
| إضافة Docstrings لكل الكلاسات الجديدة | جميع الملفات |
| تحديث `__init__.py` | إعادة التصدير للكلاسات الجديدة |
| تشغيل `ruff check --fix` | تنظيف الكود |

### 5.2 معايير النجاح للمرحلة الرابعة

- [ ] `scripts/performance_gate.py` يمر بجميع الـ Budgets.
- [ ] تغطية الاختبارات > 85% (مقاسة بـ `pytest --cov`).
- [ ] `ruff check .` يمر بدون أخطاء.
- [ ] `mypy ajo/ --strict` يمر بدون أخطاء.
- [ ] `hyperfine` يؤكد Startup Time < 50ms.

---

## 6. معايير الأداء الإجبارية (Hard Performance Budgets)

### 6.1 Startup Time (< 50ms)

هذا هو **الشرط الأهم** في الخطة بأكملها. لا يمكن تخطيه أو التنازل عنه.

```python
# آلية الفحص في CI/CD
# .github/workflows/performance.yml

name: Performance Gate
on: [push, pull_request]

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: pip install hyperfine
      - run: |
          hyperfine --warmup 5 --min-runs 30 \
            --export-json /tmp/bench.json \
            'uv run ajo --version'
      - run: python scripts/performance_gate.py /tmp/bench.json
```

### 6.2 Performance Budget Table

| المقياس | الحد الأقصى | المقاس بـ | العقوبة عند التجاوز |
|---------|-------------|-----------|---------------------|
| **Startup Time** | 50ms | `hyperfine` (30 runs) | ✗ فشل CI commit |
| **AST Parse (20 models)** | 100ms | `pytest-benchmark` | ⚠ تحذير + فشل PR |
| **Docker Compose Gen** | 10ms | `timeit` | ⚠ تحذير |
| **Theme Switch** | 5ms | `timeit` | ⚠ تحذير |
| **Fuzzy Filter (50 items)** | 10ms | `timeit` | ⚠ تحذير |
| **Dashboard Render** | 10ms | Rich internal | ⚠ تحذير |
| **Diagnostic Full Scan** | 200ms | `timeit` | ⚠ تحذير |

### 6.3 استراتيجيات تحسين الـ Startup Time

1. **Zero top-level import of rich/InquirerPy**: استيرادها داخل الدوال فقط.
2. **Lazy module-level singletons**: استخدام `__init_subclass__` بدل الاستيراد المباشر.
3. **استخدام `importlib.metadata` لاستخراج الإصدار بدل `__version__`**:
   ```python
   # بدل: from ajo import __version__
   def _get_version() -> str:
       from importlib.metadata import version
       return version("ajo")
   ```
4. **تجنب `from ... import *`** حتى في `__init__.py`.
5. **تجميد الـ Regex patterns** باستخدام `re.compile()` في module scope.

### 6.4 أدوات القياس

```bash
# 1. Hyperfine (قياس دقيق لوقت التشغيل)
hyperfine --warmup 10 --min-runs 50 'ajo --version'

# 2. Python import time (تحليل الاستيرادات)
python -X importtime -c "from ajo.cli import main" 2> >(tuna -)

# 3. pytest-benchmark (قياس داخل الاختبارات)
pytest tests/ --benchmark-only --benchmark-json output.json

# 4. cProfile (تحليل أعمق)
python -m cProfile -s cumulative -o profile.prof -m ajo --version
snakeviz profile.prof
```

---

## 7. مصفوفة المخاطر والتخفيف

| المخاطرة | الاحتمال | الأثر | خطة التخفيف |
|-----------|----------|-------|-------------|
| Startup Time > 50ms | متوسط | عالي | Lazy imports + profiling + استراتيجية التحميل بالطلب |
| AST Parser لا يعالج جميع حالات models.py | عالي | متوسط | تغطية اختبارات موسعة للحالات الشاذة (abstract models, mixins, Meta classes) |
| InquirerPy لا يدعم Fuzzy | منخفض | عالي | استخدام `prompt_toolkit` مباشرة للـ Fuzzy، أو `fzf` CLI |
| Rich Live متوافق مع Keyboard | متوسط | متوسط | استخدام `XTerm.input_hook` أو fallback إلى `input()` التقليدي |
| Docker Compose غير صحيح YAML | منخفض | متوسط | التحقق من الصحة باستخدام `yaml.safe_load()` في الاختبارات |
| Lazy import يسبب Circular Import | متوسط | عالي | إعادة هيكلة الاستيرادات، استخدام `TYPE_CHECKING` |
| Nerd Fonts لا تعمل في Terminal X | منخفض | منخفض | `ICON_FALLBACK_MAP` موجود بالفعل، توسيعه ليشمل كل الأيقونات |
| Python < 3.10 لا يدعم `from __future__ import annotations` | منخفض | منخفض | المشروع يتطلب Python 3.10+ (موجود في `pyproject.toml`) |

---

## الملحق: قائمة جميع الملفات الجديدة والمعدّلة

### ملفات جديدة (New Files)

| المسار | الغرض | المرحلة |
|--------|-------|---------|
| `ajo/core/lazy_imports.py` | `LazyImportTracker` لتتبع زمن الاستيراد | Phase 1 |
| `ajo/detector/ast_analyzer.py` | `ModelRelationshipAnalyzer` و `ModelRelationship` | Phase 2 |
| `ajo/ui/keyboard.py` | `KeyboardManager`، `KeyBinding`، `ZoneManager` | Phase 2 |
| `ajo/ui/fuzzy.py` | `FuzzyFinder` للبحث الذكي | Phase 2 |
| `ajo/ui/progress.py` | `AsyncProgressManager` للمهام غير المحجوبة | Phase 2 |
| `ajo/presets/docker_sync.py` | `DockerSyncEngine`، `DockerServiceConfig` | Phase 3 |
| `scripts/performance_gate.py` | أداة فحص حدود الأداء | Phase 4 |
| `scripts/import_profile.py` | تحليل زمن الاستيراد | Phase 1 |

### ملفات معدّلة (Modified Files)

| المسار | التغيير الرئيسي | المرحلة |
|--------|-----------------|---------|
| `ajo/ui/capabilities.py` | إعادة هيكلة كاملة مع `TerminalDetector` | Phase 1 |
| `ajo/ui/theme.py` | إضافة `ThemeEngine`، `ThemePalette`، 3 سمات | Phase 1 |
| `ajo/core/constants.py` | إضافة `ThemeVariant` Enum | Phase 1 |
| `ajo/presets/rest_api.py` | إضافة `_generate_serializer_code()`، `_generate_viewset_code()` | Phase 2 |
| `ajo/validators.py` | إضافة `DiagnosticEngine`، `DiagnosticIssue` | Phase 3 |
| `ajo/cli.py` | Lazy imports، Keyboard shortcuts، Theme selector، Diagnostics | Phase 1-4 |
| `ajo/database_manager.py` | إضافة معلومات Docker لكل DB | Phase 3 |
| `ajo/presets/docker.py` | ربط `_build_compose()` مع `DockerSyncEngine` | Phase 3 |
| `ajo/gateway/utils.py` | إضافة `_run_command_streaming()` مع callbacks | Phase 2 |
| `ajo/gateway/gh.py` | إضافة `gh_repo_create_with_progress()` | Phase 2 |

### ملفات مُحذوفة (Planned Removal - Phase 4)

| المسار | السبب |
|--------|-------|
| `ajo/templates/django_app.py` | مستبدل بالكامل بـ `ScaffoldEngine` + `AbstractPreset` |

---

> **قاعدة صارمة:** لا يمكن الانتقال من مرحلة إلى أخرى إلا بعد اجتياز **Performance Gate** و **اختبارات القبول** بنسبة 100%. Startup Time < 50ms هو شرط إجباري غير قابل للتفاوض.
