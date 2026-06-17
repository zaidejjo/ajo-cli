"""Security Hardening add-on.

Adds django-axes (brute-force protection), django-otp (TOTP two-factor),
content security policy headers via django-csp, and general security
middleware.  Composable on top of any preset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ajo.presets.addons import AbstractAddon, register_addon


@register_addon
class SecurityAddon(AbstractAddon):
    """Add brute-force protection, 2FA, CSP headers, and security checks."""

    name = "Security Hardening"
    description = "Axes + TOTP 2FA + CSP + security middleware"
    dependencies = [
        "django-axes",
        "django-otp",
        "django-csp",
    ]
    compatible_presets: list[str] | None = None
    conflicts_with: list[str] = []

    installed_apps = [
        "axes",
        "django_otp",
        "django_otp.plugins.otp_totp",
        "csp",
    ]

    middleware = [
        ("axes.middleware.AxesMiddleware", "last"),
        ("django_otp.middleware.OTPMiddleware", "last"),
        ("csp.middleware.CSPMiddleware", "last"),
    ]

    env_vars = {
        "AXES_ENABLED": "True",
        "AXES_FAILURE_LIMIT": "5",
        "AXES_COOLOFF_TIME": "1",
        "CSP_DEFAULT_SRC": "'self'",
    }

    settings_blocks = [
        """
# ---------------------------------------------------------------------------
# Security Hardening — Axes (Brute-force Protection)
# ---------------------------------------------------------------------------
AXES_ENABLED = os.getenv("AXES_ENABLED", "True").lower() == "true"
AXES_FAILURE_LIMIT = int(os.getenv("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = int(os.getenv("AXES_COOLOFF_TIME", "1"))  # hours
AXES_RESET_ON_SUCCESS = True
AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
]
""",
        """
# ---------------------------------------------------------------------------
# Security Hardening — Content Security Policy
# ---------------------------------------------------------------------------
CSP_DEFAULT_SRC = (os.getenv("CSP_DEFAULT_SRC", "'self'"),)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_SCRIPT_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:")
""",
        """
# ---------------------------------------------------------------------------
# Security Hardening — General Security Settings
# ---------------------------------------------------------------------------
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG  # type: ignore[has-type]
CSRF_COOKIE_SECURE = not DEBUG  # type: ignore[has-type]
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
""",
    ]

    async def apply(
        self,
        project_path: Path,
        project_name: str,
        env_config: dict[str, Any],
    ) -> None:
        """Inject security settings."""
        await self._inject_settings(project_path)
        await self._update_env(project_path)
