# خطة: الجيل التالي لواجهة المستخدم الطرفية وتحسين الأداء إلى سرعة الميكروثانية (Next-Gen TUI & Microsecond Speed)

**الملف المرجعي:** `.opencode/plans/02_next_gen_tui.md`
**النسخة:** 1.0
**تاريخ الإنشاء:** 2026-06-17
**اللغة:** العربية مع المصطلحات التقنية الإنجليزية

---

## جدول المحتويات

1. [Zero-Latency Dynamic Rendering Engine](#1-zero-latency-dynamic-rendering-engine)
2. [Keyboard-Driven Layout مع Sidebar Live Preview](#2-keyboard-driven-layout-مع-sidebar-live-preview)
3. [Async Architecture مع Non-Blocking UI](#3-async-architecture-مع-non-blocking-ui)
4. [Fuzzy Finding للفلترة الآنية](#4-fuzzy-finding-للفلترة-الآنية)
5. [معايير الأداء (Performance Budget)](#5-معايير-الأداء-performance-budget)

---

## 1. Zero-Latency Dynamic Rendering Engine

### 1.1 الهدف العام

بناء محرك عرض ديناميكي يكتشف إمكانيات الطرفية (Terminal Capabilities) بشكل كامل - من **TrueColor 24-bit** إلى **Nerd Fonts** و **Ligatures** - ويُغذّيها إلى نظام السمات (Theme System) لدعم سمات متميزة مثل **Cyberpunk**, **Dracula**, **Monochromatic**. يجب أن يكون زمن العرض (Render Time) أقل من **1ms** لكل إطار.

### 1.2 الملفات المستهدفة

| الملف | الدور الحالي | الدور الجديد |
|-------|--------------|--------------|
| `ajo/ui/capabilities.py` | كشف Nerd Font support فقط | كشف شامل: TrueColor, Sixel, Bracketed Paste, Cursor Shape |
| `ajo/ui/theme.py` | ثيم Cyberpunk واحد + InquirerPy style | نظام سمات متعدد (Cyberpunk, Dracula, Monochromatic) |
| `ajo/core/constants.py` | ثوابت NF و Theme | إضافة ColorSpace, ThemeVariant, GammaCorrection |

### 1.3 Terminal Capability Detection (الموسّع)

سنقوم بإعادة هيكلة `ajo/ui/capabilities.py` بالكامل ليشمل:

```python
# ajo/ui/capabilities.py (إعادة هيكلة)

from __future__ import annotations

import os
import struct
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Final

class ColorDepth(Enum):
    """مستويات عمق الألوان في الطرفية."""
    MONOCHROME = auto()      # لون واحد (1-bit)
    ANSI_16 = auto()         # 16 لون (4-bit)
    ANSI_256 = auto()        # 256 لون (8-bit)
    TRUECOLOR = auto()       # 16.7 مليون لون (24-bit / TrueColor)

class TerminalType(Enum):
    """أنواع الطرفيات المدعومة."""
    UNKNOWN = auto()
    XTERM = auto()
    KITTY = auto()
    ALACRITTY = auto()
    ITERM2 = auto()
    WEZTERM = auto()
    HYPER = auto()
    TABBY = auto()
    WARP = auto()
    VSCODE = auto()
    FOOT = auto()
    GHOSTTY = auto()

@dataclass
class TerminalCapabilities:
    """ملف كامل بإمكانيات الطرفية."""
    color_depth: ColorDepth = ColorDepth.ANSI_256
    terminal_type: TerminalType = TerminalType.UNKNOWN
    nerd_font_support: bool = False
    sixel_support: bool = False          # Sixel graphics
    bracketed_paste: bool = False        # Bracketed paste mode
    cursor_shape: bool = False           # تغيير شكل المؤشر
    mouse_support: bool = False          # SGR mouse protocol
    clipboard_access: bool = False       # OSC 52 clipboard
    sync_output: bool = False            # Synchronized output (DCS = 1 q)
    columns: int = 80                    # عدد الأعمدة
    rows: int = 24                       # عدد الصفوف
    pixel_width: int = 0                 # العرض بالبكسل (Kitty protocol)
    pixel_height: int = 0                # الارتفاع بالبكسل (Kitty protocol)
    is_tty: bool = False

class TerminalDetector:
    """
    كاشف إمكانيات الطرفية المتقدم.
    
    يستخدم عدة طرق للكشف:
    - متغيرات البيئة (TERM, COLORTERM, TERM_PROGRAM)
    - استعلامات ANSI escape sequences (DA1, DA2, DA3)
    - اختبار TrueColor عبر OSC 10
    - اختبار Sixel عبر قرارات DEC
    """
    
    # إشارات استعلام ANSI
    _CSI: Final[str] = "\x1b["
    _OSC: Final[str] = "\x1b]"
    _ST: Final[str] = "\x1b\\"
    _QUERY_COLOR_DEPTH: Final[str] = f"{_OSC}10;?{_ST}"
    
    @classmethod
    def detect(cls) -> TerminalCapabilities:
        """اكتشاف جميع إمكانيات الطرفية بشكل متزامن."""
        caps = TerminalCapabilities()
        caps.is_tty = sys.stdout.isatty()
        
        if not caps.is_tty:
            return caps  # إرجاع إعدادات افتراضية في غير TTY
        
        caps.columns, caps.rows = cls._get_terminal_size()
        caps.terminal_type = cls._detect_terminal_type()
        caps.color_depth = cls._detect_color_depth()
        caps.nerd_font_support = cls._detect_nerd_fonts()
        
        # كشف متقدم (اختياري)
        caps.bracketed_paste = cls._detect_bracketed_paste()
        caps.sixel_support = cls._detect_sixel()
        caps.sync_output = cls._detect_sync_output()
        
        return caps
    
    @classmethod
    def _detect_color_depth(cls) -> ColorDepth:
        """
        يكتشف عمق الألوان بالترتيب:
        1. COLORTERM=truecolor → TrueColor
        2. TERM=xterm-256color → 256 لون
        3. استعلام OSC 10 مباشرة للطرفية
        """
        colorterm = os.environ.get("COLORTERM", "").lower()
        if colorterm in ("truecolor", "24bit"):
            return ColorDepth.TRUECOLOR
        
        term = os.environ.get("TERM", "").lower()
        if "256color" in term or "truecolor" in term:
            return ColorDepth.ANSI_256
        
        # إذا كانت iTerm2 أو Kitty أو Alacritty → TrueColor
        tp = os.environ.get("TERM_PROGRAM", "")
        if tp in ("iTerm.app", "WezTerm", "Tabby", "WarpTerminal"):
            return ColorDepth.TRUECOLOR
        if os.environ.get("KITTY_WINDOW_ID"):
            return ColorDepth.TRUECOLOR
        if os.environ.get("ALACRITTY_LOG"):
            return ColorDepth.TRUECOLOR
        
        return ColorDepth.ANSI_16  # fallback آمن
    
    @classmethod
    def _detect_terminal_type(cls) -> TerminalType:
        """يكتشف نوع الطرفية بدقة."""
        tp = os.environ.get("TERM_PROGRAM", "")
        mapping = {
            "iTerm.app": TerminalType.ITERM2,
            "WezTerm": TerminalType.WEZTERM,
            "Hyper": TerminalType.HYPER,
            "Tabby": TerminalType.TABBY,
            "WarpTerminal": TerminalType.WARP,
            "vscode": TerminalType.VSCODE,
        }
        if tp in mapping:
            return mapping[tp]
        
        if os.environ.get("KITTY_WINDOW_ID"):
            return TerminalType.KITTY
        if os.environ.get("ALACRITTY_LOG"):
            return TerminalType.ALACRITTY
        if os.environ.get("GHOSTTY_RESOURCES_DIR"):
            return TerminalType.GHOSTTY
        
        term = os.environ.get("TERM", "").lower()
        if "foot" in term:
            return TerminalType.FOOT
        if "xterm" in term:
            return TerminalType.XTERM
        
        return TerminalType.UNKNOWN
    
    @classmethod
    def _detect_nerd_fonts(cls) -> bool:
        """يكتشف دعم Nerd Fonts (المنطق الحالي)."""
        from ajo.ui.capabilities import detect_nerd_font_support
        return detect_nerd_font_support()  # يستخدم المنطق الموجود
    
    @staticmethod
    def _get_terminal_size() -> tuple[int, int]:
        """يحصل على حجم الطرفية باستخدام ioctl أو fallback."""
        try:
            import fcntl, termios
            packed = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
            rows, cols = struct.unpack("HHHH", packed)[:2]
            return (cols or 80, rows or 24)
        except Exception:
            return (80, 24)
    
    @classmethod
    def _detect_sixel(cls) -> bool:
        """اختبار Sixel عبر متغيرات البيئة أو WT."""
        return bool(os.environ.get("WT_SESSION"))  # Windows Terminal
```

### 1.4 Theme Engine متعدد السمات

سنقوم بإعادة هيكلة `ajo/ui/theme.py` لدعم سمات متعددة مع **Theme Variant**:

```python
# ajo/ui/theme.py (إضافة)

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

from rich.style import Style as RichStyle
from rich.color import Color as RichColor

from ajo.ui.capabilities import ColorDepth, TerminalCapabilities

class ThemeVariant(Enum):
    """أنواع السمات المدعومة."""
    CYBERPUNK = auto()
    DRACULA = auto()
    MONOCHROMATIC = auto()

@dataclass(frozen=True)
class ThemePalette:
    """لوحة ألوان كاملة لثيم واحد."""
    # الألوان الأساسية
    primary: str
    secondary: str
    accent: str
    success: str
    warning: str
    error: str
    info: str
    muted: str
    text: str
    border: str
    bg_dark: str
    bg_light: str
    
    # ألوان إضافية (للمحترفين)
    surface: str          # لون السطح
    overlay: str          # لون التراكب
    highlight: str        # تمييز
    dim: str              # تعتيم
    
    @property
    def rich_primary(self) -> RichStyle:
        return RichStyle(color=RichColor(self.primary, "auto"))
    
    # دالة تحويل حسب Color Depth
    def adapt_to_depth(self, depth: ColorDepth) -> "ThemePalette":
        """يحول الألوان حسب عمق اللون المدعوم في الطرفية."""
        if depth == ColorDepth.TRUECOLOR:
            return self  # استخدام القيم كاملة (24-bit)
        elif depth == ColorDepth.ANSI_256:
            return self._to_ansi_256()
        else:
            return self._to_ansi_16()

# =============================================================================
# السمات الثابتة (مستوحاة من Theme الحالي + سمات جديدة)
# =============================================================================

CYBERPUNK_PALETTE = ThemePalette(
    primary="#00f2fe",    # Neon Cyan
    secondary="#4facfe",  # Electric Blue
    accent="#f355da",     # Neon Pink
    success="#00ffcc",    # Mint Green
    warning="#ffb86c",    # Soft Orange
    error="#ff5555",      # Coral Red
    info="#8be9fd",       # Soft Cyan
    muted="#6272a4",      # Muted Grey
    text="#f8f8f2",       # Off-white
    border="#3a3f5e",     # Border
    bg_dark="#0a0e27",    # Dark background
    bg_light="#1a1e3f",   # Light background
    surface="#141832",    # سطح
    overlay="#1e2240",    # تراكب
    highlight="#00f2fe",  # تمييز
    dim="#3a3f5e",        # تعتيم
)

DRACULA_PALETTE = ThemePalette(
    primary="#bd93f9",    # Purple
    secondary="#6272a4",  # Comment
    accent="#ff79c6",     # Pink
    success="#50fa7b",    # Green
    warning="#f1fa8c",    # Yellow
    error="#ff5555",      # Red
    info="#8be9fd",       # Cyan
    muted="#6272a4",      # Comment
    text="#f8f8f2",       # Foreground
    border="#44475a",     # Selection
    bg_dark="#282a36",    # Background
    bg_light="#44475a",   # Current line
    surface="#2d2f3e",    # سطح
    overlay="#3b3d4d",    # تراكب
    highlight="#50fa7b",  # تمييز
    dim="#6272a4",        # تعتيم
)

MONOCHROMATIC_PALETTE = ThemePalette(
    primary="#ffffff",    # White
    secondary="#cccccc",  # Light grey
    accent="#999999",     # Medium grey
    success="#ffffff",    # White
    warning="#bbbbbb",    # Light grey
    error="#666666",      # Dark grey
    info="#cccccc",       # Light grey
    muted="#777777",      # Grey
    text="#ffffff",       # White
    border="#555555",     # Dark grey
    bg_dark="#000000",    # Black
    bg_light="#1a1a1a",  # Near black
    surface="#111111",    # سطح
    overlay="#222222",    # تراكب
    highlight="#ffffff",  # تمييز
    dim="#444444",        # تعتيم
)

class ThemeEngine:
    """
    محرك السمات الذكي.
    
    - يختار الثيم بناءً على تفضيل المستخدم أو إعدادات النظام.
    - يحول الألوان تلقائياً حسب Color Depth المتاح.
    - يوفر InquirerPy style ديناميكي.
    """
    
    _instance: "ThemeEngine | None" = None
    _PALETTES: Final[dict[ThemeVariant, ThemePalette]] = {
        ThemeVariant.CYBERPUNK: CYBERPUNK_PALETTE,
        ThemeVariant.DRACULA: DRACULA_PALETTE,
        ThemeVariant.MONOCHROMATIC: MONOCHROMATIC_PALETTE,
    }
    
    def __init__(self, variant: ThemeVariant = ThemeVariant.CYBERPUNK) -> None:
        self.variant = variant
        self.capabilities = TerminalDetector.detect()
        self.palette = self._PALETTES[variant].adapt_to_depth(self.capabilities.color_depth)
    
    @classmethod
    def get_instance(cls, variant: ThemeVariant | None = None) -> "ThemeEngine":
        """نمط Singleton للحصول على نسخة Theme واحدة."""
        if cls._instance is None or variant is not None:
            cls._instance = cls(variant or ThemeVariant.CYBERPUNK)
        return cls._instance
    
    def get_inquirer_style(self) -> dict:
        """توليد InquirerPy style ديناميكي حسب الثيم الحالي."""
        p = self.palette
        return {
            "questionmark": f"bold {p.accent}",
            "answer": f"bold {p.primary}",
            "input": p.muted,
            "question": f"bold {p.primary}",
            "answered_question": f"bold {p.secondary}",
            "instruction": f"italic {p.muted}",
            "pointer": f"bold {p.primary}",
            "checkbox": p.secondary,
            "separator": f"dim {p.muted}",
            "validator": f"bold {p.error}",
            "selection": f"bold {p.accent}",
        }
```

### 1.5 Premium Theme Selection UI

في `ajo/cli.py`، سنضيف خيار اختيار الثيم مع **Live Preview**:

```python
# في دالة build_parser:
parser.add_argument("--theme", type=str, choices=["cyberpunk", "dracula", "mono"], 
                    default="cyberpunk", help="Theme variant")

# في show_features:
async def show_theme_selector() -> ThemeVariant:
    """واجهة اختيار الثيم مع معاينة حية."""
    console.print()
    print_rule("Theme Selection")
    console.print()
    
    # معاينة الألوان
    theme_preview = Table(box=box.ROUNDED, border_style=Theme.BORDER)
    theme_preview.add_column("Theme", style=f"bold {Theme.ACCENT}")
    theme_preview.add_column("Preview", width=40)
    
    for name, palette in [("Cyberpunk", CYBERPUNK_PALETTE), 
                          ("Dracula", DRACULA_PALETTE), 
                          ("Mono", MONOCHROMATIC_PALETTE)]:
        # عرض أشرطة الألوان
        bar = "│".join([
            f"[{c} on {c}]  [/]" for c in [
                palette.primary, palette.secondary, palette.accent,
                palette.success, palette.warning, palette.error
            ]
        ])
        theme_preview.add_row(name, bar)
    
    console.print(Panel(theme_preview, border_style=Theme.PRIMARY))
    
    choice = inquirer.select(
        message="Choose your theme:",
        choices=[
            Choice("cyberpunk", "Cyberpunk Neon"),
            Choice("dracula", "Dracula"),
            Choice("mono", "Monochromatic"),
        ],
        style=INQUIRER_STYLE,
    ).execute()
    
    return ThemeVariant[choice.upper()]
```

---

## 2. Keyboard-Driven Layout مع Sidebar Live Preview

### 2.1 الهدف العام

تحويل واجهة `ajo-cli` إلى **واجهة لوحة مفاتيح كاملة** (Keyboard-Driven Interface) مقسمة إلى **Zones**، مع **Sidebar** يعرض **Live Preview** لهيكل الملفات المتوقع قبل تأكيد الإنشاء.

### 2.2 هيكل الشاشة (Screen Layout)

```
┌─────────────────────────────────────────────────────────────────┐
│ [Header]  AJO CLI v3.0 - Cyberpunk Edition                      │
├──────────────────────┬──────────────────────────────────────────┤
│ [Sidebar: Navigation]│ [Main: Content Area]                    │
│                      │                                          │
│  ▶ Project Settings  │  Project: my_django_app                 │
│    Architecture      │  Database: PostgreSQL                   │
│    Database          │  Preset: REST API + Docker              │
│    GitHub            │  Theme: Cyberpunk                       │
│    CI/CD             │                                          │
│    Review & Create   │  ┌──────────────────────────────────────┐│
│                      │  │ File Tree Preview:                   ││
│                      │  │ 📁 my_django_app/                   ││
│                      │  │  ├── 📄 manage.py                   ││
│                      │  │  ├── 📁 my_django_app/              ││
│                      │  │  │  ├── 📄 settings.py              ││
│                      │  │  │  ├── 📄 urls.py                  ││
│                      │  │  │  └── 📄 wsgi.py                  ││
│                      │  │  ├── 📁 apps/                       ││
│                      │  │  └── 📄 requirements.txt            ││
│                      │  └──────────────────────────────────────┘│
│                      │                                          │
│ [Status Bar]         │ [Action Bar]                             │
│ Branch: main │ DB:   │ [Ctrl+N] New  [Ctrl+G] GitHub           │
│ postgresql          │ [Ctrl+D] Done  [Ctrl+Q] Quit             │
├──────────────────────┴──────────────────────────────────────────┤
│ [Footer]  ? Help  ↑↓ Navigate  Tab Switch  Enter Select         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Sidebar Live Preview

سنضيف `FileTreePreview` في `ajo/ui/theme.py`:

```python
class FileTreePreview:
    """
    يعرض هيكل الملفات المتوقع إنشاؤه.
    يتم تحديثه آنياً عند تغيير الإعدادات.
    """
    
    def __init__(self, project_name: str, preset_key: str, db_type: str):
        self.project_name = project_name
        self.preset_key = preset_key
        self.db_type = db_type
    
    def render(self) -> Panel:
        """يعرض الشجرة باستخدام Rich Tree."""
        from rich.tree import Tree
        from rich.style import Style as RichStyle
        
        tree = Tree(
            f"[bold {Theme.PRIMARY}]📁 {self.project_name}/[/]",
            style=RichStyle(color=Theme.MUTED),
            guide_style=RichStyle(color=Theme.BORDER),
        )
        
        # جذر المشروع
        root = tree.add("📁 project_root/")
        root.add("📄 manage.py")
        root.add("📄 .env")
        root.add("📄 .gitignore")
        
        # حزمة الإعدادات
        settings_pkg = root.add(f"📁 {self.project_name}/")
        settings_pkg.add("📄 __init__.py")
        settings_pkg.add("📄 settings.py")
        settings_pkg.add("📄 urls.py")
        settings_pkg.add("📄 wsgi.py")
        settings_pkg.add("📄 asgi.py")
        
        # التطبيقات (حسب الـ Preset)
        if self.preset_key == "rest-api":
            apis = root.add("📁 api/")
            apis.add("📄 serializers.py")
            apis.add("📄 views.py")
            apis.add("📄 urls.py")
        
        # Docker
        docker = root.add("🐳 docker/")
        docker.add("📄 Dockerfile")
        docker.add("📄 docker-compose.yml")
        docker.add("📄 .dockerignore")
        
        # القوالب
        templates = root.add("📁 templates/")
        templates.add("📁 base.html")
        templates.add("📁 components/")
        
        return Panel(
            tree,
            title=f"  {NF.SEARCH}  Project Preview  ",
            border_style=Theme.PRIMARY,
            padding=(1, 2),
        )
```

### 2.4 Keyboard Shortcuts System

سنضيف `KeyboardManager` في `ajo/ui/keyboard.py` (ملف جديد):

```python
# ajo/ui/keyboard.py (ملف جديد)

from dataclasses import dataclass, field
from typing import Callable
from enum import Enum, auto

class KeyEvent(Enum):
    """أحداث لوحة المفاتيح المدعومة."""
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    ENTER = auto()
    TAB = auto()
    CTRL_N = auto()
    CTRL_G = auto()
    CTRL_D = auto()
    CTRL_Q = auto()
    CTRL_S = auto()
    ESC = auto()
    F1 = auto()
    F2 = auto()
    DELETE = auto()

@dataclass
class KeyBinding:
    """ربطة مفتاح واحدة."""
    key: KeyEvent
    description: str
    action: Callable[[], None]
    category: str = "general"  # "navigation", "action", "special"

class KeyboardManager:
    """
    مدير لوحة المفاتيح المركزي.
    
    - يسجل كل الـ Key Bindings.
    - يعرض شاشة المساعدة (Ctrl+H).
    - يقوم بتوجيه الأحداث إلى Zone المناسب.
    """
    
    def __init__(self):
        self._bindings: dict[KeyEvent, KeyBinding] = {}
        self._zones: dict[str, list[KeyBinding]] = {}
    
    def register(self, binding: KeyBinding, zone: str = "global") -> None:
        """يسجل ربط مفتاح جديد."""
        self._bindings[binding.key] = binding
        self._zones.setdefault(zone, []).append(binding)
    
    def handle(self, event: KeyEvent) -> bool:
        """يعالج حدث لوحة مفاتيح. يعيد True إذا تم التعامل معه."""
        binding = self._bindings.get(event)
        if binding:
            binding.action()
            return True
        return False
    
    def show_help(self) -> Panel:
        """يعرض شاشة المساعدة لكل الـ Shortcuts."""
        table = Table(box=box.ROUNDED, border_style=Theme.BORDER)
        table.add_column("Key", style=f"bold {Theme.ACCENT}")
        table.add_column("Action", style=Theme.PRIMARY)
        table.add_column("Category", style=Theme.MUTED)
        
        for binding in self._bindings.values():
            key_name = binding.key.name.replace("_", " ")
            table.add_row(f"  {key_name}", binding.description, binding.category)
        
        return Panel(
            table,
            title=f"  {NF.INFO}  Keyboard Shortcuts  ",
            border_style=Theme.PRIMARY,
        )
```

### 2.5 Zone Manager

```python
class ZoneManager:
    """
    يدير تقسيم الشاشة إلى Zones.
    
    Zones:
    - header: الشريط العلوي
    - sidebar: قائمة التنقل اليسرى
    - main: المحتوى الرئيسي
    - status_bar: شريط الحالة السفلي
    - action_bar: شريط الإجراءات
    - footer: التذييل
    """
    
    ZONES = ["header", "sidebar", "main", "status_bar", "action_bar", "footer"]
    
    def __init__(self):
        self.current_zone: str = "sidebar"
        self.zone_contents: dict[str, Any] = {z: "" for z in self.ZONES}
    
    def focus_next(self) -> str:
        """ينتقل إلى المنطقة التالية (TAB)."""
        idx = self.ZONES.index(self.current_zone)
        self.current_zone = self.ZONES[(idx + 1) % len(self.ZONES)]
        return self.current_zone
    
    def compose(self) -> Layout:
        """يبني Layout كامل من الـ Zones."""
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=1),
        )
        layout["body"].split_row(
            Layout(name="sidebar", size=30),
            Layout(name="main"),
        )
        layout["body"].split_column(
            Layout(name="status_bar", size=1),
        )
        return layout
```

---

## 3. Async Architecture مع Non-Blocking UI

### 3.1 الهدف العام

تحويل `gateway/gh.py` و `gateway/uv.py` إلى **Async First** بشكل كامل باستخدام `asyncio` الأصلي، مع إضافة **Progress Spinners** غير محجوبة و **Progress Bars** سلسة أثناء المهام الثقيلة.

### 3.2 الملفات المستهدفة

| الملف | الدور الحالي | الدور الجديد |
|-------|--------------|--------------|
| `ajo/gateway/uv.py` | Async wrappers موجودة | إضافة **Progress Callbacks** + **Streaming Output** |
| `ajo/gateway/gh.py` | Async موجود | إضافة **Streaming stderr** لعرض التقدم |
| `ajo/gateway/utils.py` | `_run_command` أساسي | إضافة **Live Streaming** مع Rich Live |
| `ajo/core/app.py` | `@async_entry` | إضافة **TaskGroup** + **Cancellation Scope** |

### 3.3 Streaming Process Runner

سنضيف `_run_command_streaming()` في `ajo/gateway/utils.py`:

```python
async def _run_command_streaming(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    description: str = "",
    on_stdout: Callable[[str], None] | None = None,
    on_stderr: Callable[[str], None] | None = None,
) -> str:
    """
    ينفذ أمراً مع دفق الإخراج المباشر.
    
    يستخدم لـ:
    - uv sync (إظهار التقدم)
    - gh repo create (إظهار stderr)
    - Docker build (إظهار الخطوات)
    """
    safe_command = _sanitize_command(command)
    
    process = await asyncio.create_subprocess_exec(
        *safe_command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    stdout_lines: list[str] = []
    
    async def _read_stream(stream: asyncio.StreamReader, 
                           callback: Callable[[str], None] | None) -> None:
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace").rstrip()
            if callback:
                callback(decoded)
            stdout_lines.append(decoded)
    
    await asyncio.gather(
        _read_stream(process.stdout, on_stdout),
        _read_stream(process.stderr, on_stderr),
        return_exceptions=True,
    )
    
    await process.wait()
    return "\n".join(stdout_lines)
```

### 3.4 Non-Blocking Progress Bar

سنضيف `AsyncProgress` في `ajo/ui/progress.py` (ملف جديد):

```python
# ajo/ui/progress.py (ملف جديد)

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from rich.progress import (
    Progress as RichProgress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.console import Console

from ajo.core.constants import Theme
from ajo.ui.theme import ThemeEngine

@dataclass
class TaskProgress:
    """معلومات تقدم مهمة واحدة."""
    description: str = ""
    completed: int = 0
    total: int = 100
    status: str = "pending"  # pending, running, completed, failed

class AsyncProgressManager:
    """
    مدير التقدم غير المحجوب.
    
    - يستخدم Rich Progress مع Live.
    - يمكن تشغيله في background task.
    - يوفر update() آمن للخيوط.
    """
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.progress = RichProgress(
            SpinnerColumn("dots12", style=f"bold {Theme.PRIMARY}"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40, style=Theme.PRIMARY, complete_style=Theme.SUCCESS),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True,
        )
        self.tasks: dict[str, int] = {}
    
    def add_task(self, description: str, total: int = 100) -> str:
        """يضيف مهمة جديدة ويعيد ID."""
        task_id = self.progress.add_task(description, total=total)
        self.tasks[description] = task_id
        return description
    
    def update(self, task_desc: str, completed: int, 
               description: str | None = None) -> None:
        """يحدّث تقدم مهمة."""
        task_id = self.tasks.get(task_desc)
        if task_id is not None:
            self.progress.update(task_id, completed=completed, 
                                 description=description)
    
    @asynccontextmanager
    async def __aenter__(self) -> "AsyncProgressManager":
        self._live = Live(self.progress, refresh_per_second=10, console=self.console)
        self._live.__enter__()
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        self._live.__exit__(*args)
```

### 3.5 تكامل مع Gateway

```python
# مثال استخدام مع uv sync:

async def uv_sync_with_progress(path: Path) -> bool:
    """تشغيل uv sync مع Progress Bar حي."""
    progress_manager = AsyncProgressManager()
    
    async with progress_manager:
        task = progress_manager.add_task(f"{NF.UV} Running uv sync...", total=100)
        
        def on_stdout(line: str) -> None:
            # تحديث التقدم بناءً على مخرجات uv
            if "Resolved" in line:
                progress_manager.update(task, 30, "Resolving dependencies...")
            elif "Prepared" in line:
                progress_manager.update(task, 60, "Preparing packages...")
            elif "Installed" in line:
                progress_manager.update(task, 90, "Installing packages...")
        
        try:
            await _run_command_streaming(
                ["uv", "sync"],
                cwd=path,
                description="uv sync",
                on_stdout=on_stdout,
            )
            progress_manager.update(task, 100, f"{NF.CHECK} uv sync complete!")
            await asyncio.sleep(0.5)  # إظهار الإكمال
            return True
        except Exception:
            progress_manager.update(task, 100, f"{NF.ERROR} uv sync failed!")
            return False
```

### 3.6 Async First Gateway Refactoring

```python
# تعديل ajo/gateway/gh.py - إضافة Progress Callbacks:

async def gh_repo_create_with_progress(
    name: str, path: Path, *, private: bool = False
) -> str:
    """إنشاء repo مع عرض stderr مباشر."""
    visibility = "--private" if private else "--public"
    
    progress = AsyncProgressManager()
    async with progress:
        task = progress.add_task(f"{NF.GITHUB} Creating GitHub repository...")
        
        try:
            result = await _run_command_streaming(
                ["gh", "repo", "create", name, "--source=.", 
                 "--remote=origin", visibility, "--push", "--yes"],
                cwd=path,
                on_stderr=lambda line: progress.update(
                    task, 50, f"{NF.GITHUB} {line[:60]}"
                ),
            )
            progress.update(task, 100, f"{NF.CHECK} Repository created!")
            return result
        except Exception:
            progress.update(task, 100, f"{NF.ERROR} Repository creation failed")
            raise
```

---

## 4. Fuzzy Finding للفلترة الآنية

### 4.1 الهدف العام

دمج **Fuzzy Finder** (مثل `fzf`) داخل الـ UI للبحث والفلترة الآنية للخيارات، التطبيقات، والأوامر.

### 4.2 التنفيذ باستخدام InquirerPy Fuzzy

سنقوم بتعديل `ajo/cli.py` لاستخدام `FuzzyInquirer`:

```python
# ajo/ui/fuzzy.py (ملف جديد)

from typing import Any, Callable
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import ValidationError, Validator

from ajo.ui.theme import ThemeEngine
from ajo.core.constants import NF

class FuzzyFinder:
    """
    واجهة Fuzzy Finder لاختيار الخيارات.
    
    تستخدم InquirerPy's Fuzzy الخصائص:
    - كتابة لفلترة الخيارات.
    - تمييز الأحرف المتطابقة.
    - فرز حسب النتيجة (score).
    """
    
    @staticmethod
    def select_apps(app_names: list[str]) -> list[str]:
        """اختيار تطبيقات Django متعددة مع Fuzzy."""
        choices = [Choice(value=name, name=f"{NF.APP} {name}") 
                   for name in app_names]
        choices.insert(0, Choice(value="__all__", 
                                 name=f"{NF.STAR} Select All"))
        
        selected = inquirer.checkbox(
            message="Select Django apps (type to filter):",
            choices=choices,
            style=ThemeEngine.get_instance().get_inquirer_style(),
            instruction="(type to search, space to select, enter to confirm)",
            validate=lambda result: len(result) > 0 or "Select at least one app",
        ).execute()
        
        if "__all__" in selected:
            return app_names
        return selected
    
    @staticmethod
    def filter_commands(commands: list[dict[str, Any]]) -> str:
        """بحث Fuzzy عن أمر Django."""
        choices = [
            Choice(value=cmd["action"], 
                   name=f"  {cmd.get('icon', NF.TERMINAL)}  {cmd['name']}  "
                        f"[dim]{cmd.get('description', '')}[/]")
            for cmd in commands
        ]
        
        return inquirer.fuzzy(
            message="Search for a Django command:",
            choices=choices,
            style=ThemeEngine.get_instance().get_inquirer_style(),
            max_rec=10,  # أقصى 10 نتائج
            match_exact=True,
        ).execute()
```

---

## 5. معايير الأداء (Performance Budget)

### 5.1 Startup Time تحت 50ms

**الهدف الحالي:** < 50ms من لحظة تشغيل `ajo` حتى ظهور أول إطار في الـ TUI.

| المكون | الحد الأقصى | الاستراتيجية |
|--------|-------------|--------------|
| استيراد Python | 15ms | Lazy imports (استيراد داخل الدوال) |
| كشف الطرفية | 5ms | ملفات البيئة فقط (بدون Subprocess) |
| إنشاء `DjangoProjectDetector` | 10ms | Fast scan فقط (بدون Subprocess) |
| عرض الشاشة الأولى | 20ms | استخدام Cache + Render buffer |

### 5.2 Lazy Loading Optimizations

```python
# داخل ajo/cli.py - تعديل الاستيرادات

# ❌ الطريقة الحالية: استيراد مباشر (بطيء)
from ajo.detector import DjangoProjectDetector  # هذا يستورد detector كاملاً

# ✅ الطريقة الجديدة: Lazy Imports داخل الدوال
def _get_project_detector() -> "DjangoProjectDetector":
    """يسترجع الكاشف مع Lazy Import لضمان سرعة البدء."""
    from ajo.detector.project import DjangoProjectDetector  # استيراد داخل الدالة
    return DjangoProjectDetector()

# استخدام متغير كاش
_detector_cache: dict[str, Any] = {}

def _lazy_import(module_path: str) -> Any:
    """استيراد كسول مع تخزين مؤقت."""
    if module_path not in _detector_cache:
        import importlib
        _detector_cache[module_path] = importlib.import_module(module_path)
    return _detector_cache[module_path]
```

### 5.3 Import Map البطيء (Slow Import Registry)

سننشئ `ajo/core/lazy_imports.py` لتتبع وتحليل زمن الاستيراد:

```python
# ajo/core/lazy_imports.py (ملف جديد)

import importlib
import time
from typing import Any

class LazyImportTracker:
    """يتتبع زمن الاستيراد ويبلغ عن أي تأخير."""
    
    _imports: dict[str, float] = {}  # module → time_taken
    _THRESHOLD_MS: float = 5.0       # حد الإنذار
    
    @classmethod
    def import_module(cls, module_path: str) -> Any:
        """يسترجع وحدة مع تتبع الوقت."""
        if module_path in cls._imports:
            return importlib.import_module(module_path)
        
        start = time.perf_counter()
        module = importlib.import_module(module_path)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        cls._imports[module_path] = elapsed
        
        if elapsed > cls._THRESHOLD_MS:
            import logging
            logging.getLogger(__name__).warning(
                f"Slow import: {module_path} took {elapsed:.1f}ms "
                f"(threshold: {cls._THRESHOLD_MS}ms)"
            )
        
        return module
```

### 5.4 Render Performance Targets

| العملية | الزمن المستهدف | آلية القياس |
|---------|----------------|-------------|
| Dashboard render | < 5ms | `time.perf_counter()` |
| InquirerPy transition | < 10ms | إطار واحد (60fps ≈ 16ms) |
| File tree generation | < 2ms | توليد الشجرة مباشرة |
| Async command start | < 1ms | Subprocess exec |
| Theme switch | < 3ms | تبديل Reference فقط |

### 5.5 اختبارات الأداء

```bash
# قياس زمن بدء التشغيل
hyperfine --warmup 3 "ajo --version"

# قياس Dashboard render
pytest tests/ui/test_render_performance.py -v --benchmark

# تحليل الاستيرادات
python -X importtime -c "from ajo.cli import main" 2> import_profile.txt
tuna import_profile.txt  # أداة تحليل import time
```

---

## ملخص التغييرات في الملفات

| الملف | التغيير |
|-------|---------|
| `ajo/ui/capabilities.py` | إعادة هيكلة كاملة: إضافة `TerminalDetector`, `ColorDepth`, `TerminalCapabilities` |
| `ajo/ui/theme.py` | إضافة `ThemeEngine`, `ThemePalette`, 3 سمات (Cyberpunk/Dracula/Mono) |
| `ajo/core/constants.py` | إضافة `ThemeVariant` Enum |
| `ajo/ui/keyboard.py` **(جديد)** | `KeyboardManager`, `KeyBinding`, `ZoneManager` |
| `ajo/ui/progress.py` **(جديد)** | `AsyncProgressManager`, `TaskProgress` |
| `ajo/ui/fuzzy.py` **(جديد)** | `FuzzyFinder` للفلترة الذكية |
| `ajo/gateway/utils.py` | إضافة `_run_command_streaming()` مع callbacks |
| `ajo/gateway/gh.py` | إضافة `gh_repo_create_with_progress()` |
| `ajo/core/lazy_imports.py` **(جديد)** | `LazyImportTracker` |
| `ajo/cli.py` | Lazy imports, Keyboard shortcuts, Theme selector, Sidebar |

---

> **ملاحظة:** جميع التعديلات المذكورة في هذه الخطة لن تُنفّذ على الملفات الحالية إلا بعد اعتماد الخطة رسمياً.
