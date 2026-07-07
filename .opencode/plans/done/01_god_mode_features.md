# خطة: المواصفات الفنية للميزات الخارقة وغير التقليدية (God Mode Features)

**الملف المرجعي:** `.opencode/plans/01_god_mode_features.md`
**النسخة:** 1.0
**تاريخ الإنشاء:** 2026-06-17
**اللغة:** العربية مع المصطلحات التقنية الإنجليزية

---

## جدول المحتويات

1. [Context-Aware Smart Injection (الحقن الذكي السياقي)](#1-context-aware-smart-injection)
2. [Infrastructure-as-Code (IaC) Sync (مزامنة البنية التحتية ككود)](#2-infrastructure-as-code-iac-sync)
3. [Self-Healing Diagnostics (التشخيص الذاتي المُصلِح)](#3-self-healing-diagnostics)
4. [مصفوفة الأولويات والتسليم](#4-مصفوفة-الأولويات-والتسليم)

---

## 1. Context-Aware Smart Injection (الحقن الذكي السياقي)

### 1.1 الهدف العام

تحويل `ajo-cli` من مجرد أداة **Scaffolding** إلى **مهندس Django ذكي** قادر على قراءة مشروع Django قائم، تحليل علاقات `models.py` دون تنفيذ الاستيرادات، وتوليد **Serializers**, **Views**, و **URLs routing** بشكل تلقائي ومترابط.

### 1.2 الملفات المستهدفة

| الملف | الدور الحالي | الدور الجديد |
|-------|--------------|--------------|
| `ajo/detector/project.py` | كشف هيكل المشروع (Fast + Slow scans) | إضافة **AST Parser** لتحليل `models.py` |
| `ajo/detector/__init__.py` | إعادة تصدير الكلاسات | إضافة `ModelRelationshipAnalyzer` |
| `ajo/presets/base.py` | Abstract Preset Base | إضافة دالة `generate_derived_artifacts` |
| `ajo/presets/rest_api.py` | توليد DRF boilerplate | توليد **Serializers** و **ViewSets** تلقائياً |
| `ajo/scaffolding/engine.py` | Pipeline آلي | دمج خطوة **Smart Injection** |

### 1.3 آلية AST Parsing (تحليل شجرة القواعد المجردة)

سنضيف كلاس جديد `ModelRelationshipAnalyzer` داخل المجلد `ajo/detector/`:

```python
# ajo/detector/ast_analyzer.py (ملف جديد)

import ast
from pathlib import Path
from typing import Any

class ModelRelationship:
    """تمثيل علاقة نموذج مُكتشفة."""
    def __init__(self, model_name: str, fields: list[dict[str, Any]], 
                 relations: list[dict[str, str]]) -> None:
        self.model_name = model_name
        self.fields = fields          # [{"name": "title", "type": "CharField", "args": {...}}]
        self.relations = relations    # [{"type": "ForeignKey", "to": "Author", "related_name": "books"}]

class ModelRelationshipAnalyzer:
    """
    محلّل علاقات النماذج باستخدام Python AST.
    
    الميزات:
    - لا ينفّذ أي استيراد (zero-execution parsing).
    - يكتشف ForeignKey, OneToOneField, ManyToManyField.
    - يتتبع `related_name` و `on_delete` و `through`.
    - يتعامل مع `settings.AUTH_USER_MODEL` كمرجع ديناميكي.
    """
    
    KNOWN_FIELDS: frozenset = frozenset({
        "CharField", "IntegerField", "BooleanField", "DateField",
        "DateTimeField", "ForeignKey", "OneToOneField", "ManyToManyField",
        "TextField", "EmailField", "URLField", "FileField", "ImageField",
        "DecimalField", "FloatField", "JSONField", "UUIDField", "SlugField",
    })
    
    RELATION_FIELDS: frozenset = frozenset({
        "ForeignKey", "OneToOneField", "ManyToManyField",
    })
    
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.models: dict[str, ModelRelationship] = {}
        
    def analyze(self) -> dict[str, ModelRelationship]:
        """يجمع كل ملفات models.py ويحلّلها."""
        for app_path in self._discover_app_dirs():
            models_file = app_path / "models.py"
            if models_file.exists():
                self._parse_models_file(models_file)
        return self.models
    
    def _discover_app_dirs(self) -> list[Path]:
        """يكتشف أدلة التطبيقات (الأدلة التي تحتوي على apps.py أو models.py)."""
        return [
            item for item in self.project_path.iterdir()
            if item.is_dir()
            and not item.name.startswith(".")
            and ((item / "apps.py").exists() or (item / "models.py").exists())
        ]
    
    def _parse_models_file(self, path: Path) -> None:
        """يحلل ملف models.py باستخدام ast.parse."""
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._process_class(node)
        except SyntaxError:
            return  # نتجاوز الملفات التالفة بهدوء
    
    def _process_class(self, node: ast.ClassDef) -> None:
        """يعالج كلاس Django Model واحد."""
        # نتحقق إذا كان يرث من models.Model
        if not self._inherits_from_model(node):
            return
        
        model_name = node.name
        fields: list[dict[str, Any]] = []
        relations: list[dict[str, str]] = []
        
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                        field_info = self._extract_field_info(target.id, item.value)
                        if field_info:
                            fields.append(field_info)
                            if field_info["type"] in self.RELATION_FIELDS:
                                relations.append({
                                    "type": field_info["type"],
                                    "to": field_info.get("to", "Unknown"),
                                    "related_name": field_info.get("related_name", ""),
                                })
        
        self.models[model_name] = ModelRelationship(model_name, fields, relations)
    
    @staticmethod
    def _inherits_from_model(node: ast.ClassDef) -> bool:
        """يتحقق من أن الكلاس يرث من models.Model (حتى بشكل غير مباشر)."""
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if base.attr == "Model":
                    return True
            elif isinstance(base, ast.Name):
                if base.id == "Model":
                    return True
        return False
    
    @staticmethod
    def _extract_field_info(name: str, call: ast.Call) -> dict[str, Any] | None:
        """يستخرج معلومات الحقل من استدعاء (مثل ForeignKey(Author, on_delete=...))."""
        if not isinstance(call.func, ast.Attribute):
            return None
        field_type = call.func.attr
        if field_type not in ModelRelationshipAnalyzer.KNOWN_FIELDS:
            return None
        
        info: dict[str, Any] = {"name": name, "type": field_type}
        
        # استخراج الوسائط الموضعية (المعرفات)
        for i, arg in enumerate(call.args):
            if isinstance(arg, ast.Name):
                if i == 0 and field_type in ModelRelationshipAnalyzer.RELATION_FIELDS:
                    info["to"] = arg.id
            elif isinstance(arg, ast.Constant):
                if i == 0:
                    info["to"] = arg.value
        
        # استخراج keyword arguments
        for kw in call.keywords:
            if isinstance(kw.value, ast.Constant):
                info[kw.arg] = kw.value.value
            elif isinstance(kw.value, ast.Name):
                info[kw.arg] = kw.value.id
            elif isinstance(kw.value, ast.Attribute):
                # للتعامل مع settings.AUTH_USER_MODEL
                info[kw.arg] = f"{kw.value.value}.{kw.value.attr}" if hasattr(kw.value, 'value') else kw.value.attr
        
        return info
```

### 1.4 التكامل مع Preset REST API

في `ajo/presets/rest_api.py`، سنضيف دالة `_generate_serializers()` و `_generate_viewsets()` التي تستخدم نتائج `ModelRelationshipAnalyzer`:

**توليد Serializer تلقائي:**

```python
# داخل RestAPIPreset
def _generate_serializer_code(self, model: ModelRelationship) -> str:
    """توليد كود Serializer من تحليل AST."""
    imports = {"from rest_framework import serializers"}
    declared_models = set()
    
    # serializer class
    lines = [
        f"class {model.model_name}Serializer(serializers.ModelSerializer):",
        f"    class Meta:",
        f"        model = {model.model_name}",
        f"        fields = '__all__'",
    ]
    
    # إضافة حقول القراءة فقط للعلاقات
    if model.relations:
        lines.insert(1, f"    # ── علاقات تم اكتشافها تلقائياً ──")
        for rel in model.relations:
            lines.insert(2, f"    {rel.get('related_name', rel['to'].lower())} = serializers.{'PrimaryKeyRelatedField' if rel['type'] != 'ManyToManyField' else 'StringRelatedField'}(many={str(rel['type'] == 'ManyToManyField').lower()}, read_only=True)")
    
    return "\n".join(lines)
```

**توليد ViewSet تلقائي:**

```python
def _generate_viewset_code(self, model: ModelRelationship) -> str:
    """توليد ViewSet كامل مع permissions."""
    imports = {
        "from rest_framework import viewsets, permissions",
        "from rest_framework.decorators import action",
        "from rest_framework.response import Response",
    }
    
    lines = [
        f"class {model.model_name}ViewSet(viewsets.ModelViewSet):",
        f"    \"\"\"",
        f"    ViewSet مُولّد تلقائياً للنموذج {model.model_name}.",
        f"    تم الكشف عن {len(model.relations)} علاقة.",
        f"    \"\"\"",
        f"    queryset = {model.model_name}.objects.all()",
        f"    serializer_class = {model.model_name}Serializer",
        f"    permission_classes = [permissions.IsAuthenticatedOrReadOnly]",
    ]
    
    # إضافة Custom Actions للعلاقات
    if model.relations:
        lines.append("")
        for rel in model.relations:
            rel_name = rel.get('related_name', rel['to'].lower())
            lines.append(f"    @action(detail=True, methods=['get'])")
            lines.append(f"    def {rel_name}(self, request, pk=None):")
            lines.append(f"        instance = self.get_object()")
            lines.append(f"        related = instance.{rel_name}.all()")
            lines.append(f"        serializer = self.get_serializer(related, many=True)")
            lines.append(f"        return Response(serializer.data)")
            lines.append("")
    
    return "\n".join(lines)
```

### 1.5 التوجيه التلقائي في `urls.py` باستخدام Router

سنقوم بتوليد `urls.py` رئيسي يستخدم **DefaultRouter**:

```python
def _generate_urls_code(self, models: dict[str, ModelRelationship]) -> str:
    router_imports = "from rest_framework.routers import DefaultRouter"
    lines = [
        router_imports,
        "",
        "router = DefaultRouter()",
    ]
    
    for model_name, model in models.items():
        # تحويل اسم النموذج إلى مسار (ModelName → model-name)
        route_name = re.sub(r'(?<!^)(?=[A-Z])', '-', model_name).lower()
        lines.append(f"router.register(r'{route_name}', {model_name}ViewSet, basename='{route_name}')")
    
    lines.extend([
        "",
        "urlpatterns = router.urls",
    ])
    
    return "\n".join(lines)
```

### 1.6 معالجة `manage.py startapp` مع Injection فوري

عند إنشاء تطبيق جديد، سنقوم بـ:

1. **قراءة** `models.py` الجديد باستخدام `ModelRelationshipAnalyzer`.
2. **توليد** `serializers.py`، `views.py`، `urls.py` كاملة.
3. **تسجيل** التطبيق تلقائياً في `INSTALLED_APPS` عبر `ajo/utils.py:append_to_installed_apps()`.
4. **ربط** الـ URLs في `main_urls.py` دون تدخل المستخدم.

### 1.7 اختبارات الوحدة المطلوبة

```bash
# اختبار AST Parser
pytest tests/detector/test_ast_analyzer.py -v

# اختبار توليد Serializers
pytest tests/presets/test_rest_api_generation.py -v

# اختبار التوجيه التلقائي
pytest tests/scaffolding/test_urls_generation.py -v
```

---

## 2. Infrastructure-as-Code (IaC) Sync

### 2.1 الهدف العام

مزامنة إعدادات قاعدة البيانات المختارة من `database_manager.py` مباشرة إلى `presets/docker.py` لتوليد `docker-compose.yml` جاهز للإنتاج مع **Health Checks** آلي، **Redis**، و **Celery** اختياري.

### 2.2 الملفات المستهدفة

| الملف | الدور الحالي | الدور الجديد |
|-------|--------------|--------------|
| `ajo/database_manager.py` | قوالب تكوين قاعدة البيانات | إضافة **علامات Docker** لكل DB |
| `ajo/presets/docker.py` | توليد Dockerfile + Compose | توليد **ديناميكي** بناءً على DB |
| `ajo/presets/__init__.py` | تسجيل الـ Presets | إضافة `DockerSyncEngine` |
| `ajo/scaffolding/engine.py` | Pipeline | إضافة خطوة **IaC Sync** |

### 2.3 بنية DockerSyncEngine

سننشئ `DockerSyncEngine` في `ajo/presets/docker_sync.py`:

```python
# ajo/presets/docker_sync.py (ملف جديد)

from dataclasses import dataclass, field
from typing import Any

@dataclass
class DockerServiceConfig:
    """تكوين خدمة Docker واحدة."""
    image: str
    container_name: str
    restart: str = "unless-stopped"
    ports: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    healthcheck: dict[str, Any] | None = None
    depends_on: list[str] = field(default_factory=list)
    command: str | None = None

class DockerSyncEngine:
    """
    محرك المزامنة بين اختيار المستخدم لقاعدة البيانات
    وتوليد docker-compose.yml متكامل مع Health Checks.
    
    نقاط التكامل:
    - database_manager.py → يحدد engine المستخدم
    - presets/docker.py → يستخدم التكوين المُولّد
    """
    
    DB_SERVICE_MAP: dict[str, DockerServiceConfig] = {
        "postgresql": DockerServiceConfig(
            image="postgres:16-alpine",
            container_name="db",
            ports=["5432:5432"],
            volumes=["postgres_data:/var/lib/postgresql/data"],
            healthcheck={
                "test": ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"],
                "interval": "5s",
                "timeout": "3s",
                "retries": 5,
                "start_period": "10s",
            },
        ),
        "mysql": DockerServiceConfig(
            image="mysql:8.0",
            container_name="db",
            ports=["3306:3306"],
            volumes=["mysql_data:/var/lib/mysql"],
            environment={"MYSQL_ROOT_PASSWORD": "${DB_PASSWORD:-root}"},
            healthcheck={
                "test": ["CMD", "mysqladmin", "ping", "-h", "localhost"],
                "interval": "5s",
                "timeout": "3s",
                "retries": 5,
                "start_period": "10s",
            },
        ),
    }
    
    REDIS_SERVICE = DockerServiceConfig(
        image="redis:7-alpine",
        container_name="redis",
        ports=["6379:6379"],
        volumes=["redis_data:/data"],
        healthcheck={
            "test": ["CMD", "redis-cli", "ping"],
            "interval": "5s",
            "timeout": "3s",
            "retries": 5,
        },
    )
    
    @classmethod
    def generate_compose(cls, project_name: str, db_type: str, 
                         include_celery: bool = False) -> str:
        """
        توليد docker-compose.yml كامل.
        
        الخطوات:
        1. اختيار خدمة DB بناءً على db_type من database_manager.py.
        2. إضافة Redis بشكل افتراضي.
        3. إضافة Celery بشكل اختياري.
        4. ربط Health Checks ب depends_on.
        """
        db_service = cls.DB_SERVICE_MAP.get(db_type)
        if not db_service:
            db_service = cls.DB_SERVICE_MAP["postgresql"]
        
        # ... بناء YAML ...
```

### 2.4 Health Check Dependency Graph

يجب أن يكون ترتيب تشغيل الخدمات في `docker-compose.yml` كالتالي:

```
web → depends_on → [db (healthy), redis (healthy)]
                    ↓
             celery (if enabled) → depends_on → [redis (healthy), db (healthy)]
```

يتم ضمان ذلك عن طريق إضافة `condition: service_healthy` في كل `depends_on`.

### 2.5 التزامن مع database_manager.py

سيتم تعديل `ajo/database_manager.py` لإضافة `docker_service_config` إلى كل قاعدة بيانات:

```python
# تعديل داخل DatabaseManager.DATABASE_CONFIGS
"postgresql": {
    "engine": "django.db.backends.postgresql",
    "packages": ["psycopg2-binary"],
    "docker_service": {
        "image": "postgres:16-alpine",
        "healthcheck": "pg_isready",
        "port": "5432",
        "volume": "postgres_data:/var/lib/postgresql/data",
    },
    # ...
}
```

### 2.6 اختبارات التكامل

```bash
# اختبار توليد Compose
pytest tests/presets/test_docker_sync.py -v

# اختبار صحة YAML المُولّد
python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"
```

---

## 3. Self-Healing Diagnostics (التشخيص الذاتي المُصلِح)

### 3.1 الهدف العام

بناء طبقة تشخيص ذكية تتحقق من صحة مشروع Django (تسجيل التطبيقات، تعارض الهجرات، مشاكل الإعدادات) وتقدم خيار **Auto-Fix** آلي.

### 3.2 الملفات المستهدفة

| الملف | الدور الحالي | الدور الجديد |
|-------|--------------|--------------|
| `ajo/validators.py` | التحقق من صحة الأسماء | إضافة **DiagnosticEngine** |
| `ajo/utils.py` | أدوات مساعدة | إضافة `auto_fix_installed_apps()` |
| `ajo/detector/project.py` | كشف المشروع | إضافة **Health Checks** |
| `ajo/cli.py` | الواجهة الرئيسية | إضافة **Diagnostic Dashboard** |

### 3.3 DiagnosticEngine

كلاس جديد `DiagnosticEngine` في `ajo/validators.py`:

```python
# داخل ajo/validators.py (إضافة)

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

@dataclass
class DiagnosticIssue:
    """تمثيل مشكلة تم اكتشافها."""
    severity: str              # "error" | "warning" | "info"
    category: str              # "installed_apps" | "migrations" | "settings"
    message: str               # وصف المشكلة
    file_path: Path | None     # الملف المتأثر
    auto_fix: Callable[[], bool] | None = None  # دالة الإصلاح الآلي
    fix_description: str = ""  # وصف الإصلاح

class DiagnosticEngine:
    """
    محرك التشخيص الذاتي.
    
    يقوم بـ:
    1. فحص INSTALLED_APPS بحثاً عن تطبيقات مفقودة.
    2. اكتشاف تعارض الهجرات (migration conflicts).
    3. التحقق من صحة الإعدادات الأساسية (SECRET_KEY, DEBUG, ALLOWED_HOSTS).
    4. تقديم Auto-Fix لكل مشكلة قابلة للإصلاح.
    """
    
    REQUIRED_APPS: frozenset = frozenset({
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    })
    
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.issues: list[DiagnosticIssue] = []
    
    def run_full_diagnostic(self) -> list[DiagnosticIssue]:
        """يجري كل الفحوصات ويعيد قائمة المشاكل."""
        self.issues.clear()
        self._check_installed_apps()
        self._check_migration_conflicts()
        self._check_settings_integrity()
        self._check_secret_key()
        return self.issues
    
    def _check_installed_apps(self) -> None:
        """يتحقق من أن كل تطبيق موجود في INSTALLED_APPS."""
        settings_path = self._find_settings_file()
        if not settings_path:
            return
        
        content = settings_path.read_text(encoding="utf-8")
        for app in self.REQUIRED_APPS:
            if app not in content:
                self.issues.append(DiagnosticIssue(
                    severity="error",
                    category="installed_apps",
                    message=f"التطبيق '{app}' مفقود من INSTALLED_APPS في {settings_path.name}",
                    file_path=settings_path,
                    auto_fix=lambda a=app: self._auto_add_app(settings_path, content, a),
                    fix_description=f"إضافة '{app}' إلى INSTALLED_APPS",
                ))
    
    def _check_migration_conflicts(self) -> None:
        """يكتشف تعارض الهجرات عن طريق تحليل أسماء ملفات الهجرات."""
        for app_path in self.project_path.iterdir():
            migrations_dir = app_path / "migrations"
            if not migrations_dir.exists():
                continue
            
            migration_files = sorted(migrations_dir.glob("[0-9]*.py"))
            # التحقق من وجود هوات متكررة
            seen_numbers = set()
            for mf in migration_files:
                prefix = mf.stem.split("_")[0]
                if prefix in seen_numbers:
                    self.issues.append(DiagnosticIssue(
                        severity="error",
                        category="migrations",
                        message=f"تعارض في ترقيم الهجرات: {mf.name}",
                        file_path=mf,
                        auto_fix=lambda f=mf: self._auto_rename_migration(f),
                        fix_description=f"إعادة ترقيم {mf.name}",
                    ))
                seen_numbers.add(prefix)
    
    def _check_settings_integrity(self) -> None:
        """يتحقق من صحة الإعدادات الأساسية."""
        settings_path = self._find_settings_file()
        if not settings_path:
            return
        
        content = settings_path.read_text(encoding="utf-8")
        
        # التحقق من ALLOWED_HOSTS
        if "ALLOWED_HOSTS" not in content:
            self.issues.append(DiagnosticIssue(
                severity="warning",
                category="settings",
                message="ALLOWED_HOSTS غير موجود في الإعدادات",
                file_path=settings_path,
                auto_fix=lambda: self._auto_add_allowed_hosts(settings_path, content),
                fix_description="إضافة ALLOWED_HOSTS = ['*'] (للبيئة التطويرية فقط)",
            ))
    
    def _check_secret_key(self) -> None:
        """يتأكد من وجود SECRET_KEY آمن."""
        settings_path = self._find_settings_file()
        if not settings_path:
            return
        content = settings_path.read_text(encoding="utf-8")
        if "SECRET_KEY" not in content:
            self.issues.append(DiagnosticIssue(
                severity="error",
                category="settings",
                message="SECRET_KEY غير موجود في الإعدادات",
                file_path=settings_path,
                auto_fix=lambda: self._auto_generate_secret_key(settings_path, content),
                fix_description="توليد SECRET_KEY آمن عشوائياً",
            ))
```

### 3.4 Auto-Fix Engine

آلية الإصلاح الآلي تتم عبر استدعاء `auto_fix()` المرتبطة بكل مشكلة:

```python
def _auto_add_app(self, settings_path: Path, content: str, app: str) -> bool:
    """يضيف تطبيقاً مفقوداً إلى INSTALLED_APPS."""
    try:
        new_content = content.replace(
            "INSTALLED_APPS = [",
            f"INSTALLED_APPS = [\n    '{app}',",
        )
        settings_path.write_text(new_content, encoding="utf-8")
        return True
    except Exception:
        return False
```

### 3.5 التشخيص عبر CLI Dashboard

في `ajo/cli.py`، سنضيف `show_diagnostics()`:

```python
async def show_diagnostics(detector: DjangoProjectDetector) -> None:
    """عرض لوحة التشخيص التفاعلية."""
    engine = DiagnosticEngine(detector.path)
    issues = engine.run_full_diagnostic()
    
    if not issues:
        show_success("System Healthy", "No issues detected ✓")
        return
    
    for issue in issues:
        icon = NF.ERROR if issue.severity == "error" else NF.WARNING
        color = Theme.ERROR if issue.severity == "error" else Theme.WARNING
        
        console.print(f"  {icon}  [{color}]{issue.message}[/]")
        
        if issue.auto_fix:
            fix = inquirer.confirm(
                message=f"     Auto-fix: {issue.fix_description}?",
                default=True,
                style=INQUIRER_STYLE,
            ).execute()
            if fix:
                if issue.auto_fix():
                    show_success("Fixed", issue.fix_description)
                else:
                    show_error("Fix Failed", f"Could not {issue.fix_description}")
```

### 3.6 اختبارات التشخيص

```bash
# اختبار فحص INSTALLED_APPS
pytest tests/validators/test_diagnostic_engine.py -v

# اختبار Auto-Fix
pytest tests/validators/test_auto_fix.py -v

# اختبار تعارض الهجرات
pytest tests/validators/test_migration_conflicts.py -v
```

---

## 4. مصفوفة الأولويات والتسليم

| الميزة | الأولوية | الجهد التقديري | الملفات المتأثرة | الاختبارات المطلوبة |
|--------|----------|----------------|-------------------|---------------------|
| AST Parser | **P0** | 3 أيام | `detector/ast_analyzer.py` (جديد) | 5 اختبارات |
| توليد Serializers/Views | **P1** | 4 أيام | `presets/rest_api.py` | 8 اختبارات |
| التوجيه التلقائي | **P1** | 2 أيام | `presets/rest_api.py`, `detector/project.py` | 4 اختبارات |
| DockerSyncEngine | **P2** | 2 أيام | `presets/docker_sync.py` (جديد) | 4 اختبارات |
| Health Check Graph | **P2** | 1 يوم | `presets/docker.py` | 2 اختبارات |
| DiagnosticEngine | **P1** | 3 أيام | `validators.py` | 6 اختبارات |
| Auto-Fix | **P2** | 2 أيام | `utils.py`, `cli.py` | 4 اختبارات |

**ملاحظات:**
- **P0**: يجب إنجازها أولاً لأنها تُعدّ حجر الأساس لباقي الميزات.
- **P1**: ميزات أساسية للتكامل المستمر.
- **P2**: ميزات محسّنة (quality of life improvements).

---

> **ملاحظة:** لا يُسمح بتعديل أي ملف تنفيذي حالي (`cli.py`, `scaffolding/engine.py`, إلخ) حتى اعتماد هذه الخطة وبدء مرحلة التنفيذ.
