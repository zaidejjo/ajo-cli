"""Auth & Users add-on.

Provides JWT authentication, user registration, profile API, and
password reset flows.  Generates DRF endpoints, Ninja endpoints, or
server-rendered views depending on the architecture preset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ajo.presets.addons import AbstractAddon, register_addon
from ajo.presets.addons._settings import SettingsInjector


@register_addon
class AuthAddon(AbstractAddon):
    """Add JWT auth, user registration, and profile management."""

    name = "Auth & Users"
    description = "JWT + registration + profile API"
    dependencies = [
        "djangorestframework-simplejwt",
        "django-cors-headers",
    ]
    compatible_presets: list[str] | None = None
    conflicts_with: list[str] = []

    installed_apps = [
        "accounts",
        "rest_framework_simplejwt",
        "rest_framework_simplejwt.token_blacklist",
    ]

    middleware = [
        ("corsheaders.middleware.CorsMiddleware", "first"),
    ]

    url_patterns: list[tuple[str, str]] = []

    env_vars = {
        "ACCESS_TOKEN_LIFETIME": "5",
        "REFRESH_TOKEN_LIFETIME": "1",
    }

    settings_blocks = [
        """
# ---------------------------------------------------------------------------
# Auth & Users — Custom User Model & JWT Configuration
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=int(os.getenv("ACCESS_TOKEN_LIFETIME", "5"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_TOKEN_LIFETIME", "1"))),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000",
).split(",")
""",
    ]

    preview_files: list[tuple[str, int]] = [
        ("accounts/", 0),
        ("accounts/__init__.py", 0),
        ("accounts/models.py", 1024),
        ("accounts/admin.py", 512),
        ("accounts/forms.py", 1024),
        ("accounts/apps.py", 256),
        ("accounts/urls.py", 512),
        ("accounts/views.py", 1024),
        ("accounts/serializers.py", 1024),
        ("accounts/tests.py", 256),
        ("templates/", 0),
        ("templates/registration/login.html", 2048),
        ("templates/registration/signup.html", 2048),
        ("templates/registration/password_reset_form.html", 1024),
        ("templates/registration/password_reset_done.html", 512),
        ("templates/registration/password_reset_confirm.html", 1024),
        ("templates/registration/password_reset_complete.html", 512),
    ]

    async def apply(
        self,
        project_path: Path,
        project_name: str,
        env_config: dict[str, Any],
    ) -> None:
        """Scaffold the ``accounts`` app with preset-aware endpoints."""
        preset_key = env_config.get("preset_key", "monolith")
        accounts_dir = project_path / "accounts"
        templates_dir = project_path / "templates" / "registration"

        # ── Core accounts package files ────────────────────────────────
        self._write_file(accounts_dir / "__init__.py", "")

        self._write_file(
            accounts_dir / "apps.py",
            f"""from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
""",
        )

        self._write_file(
            accounts_dir / "models.py",
            '''from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model with additional profile fields."""

    bio = models.TextField(blank=True)
    avatar = models.URLField(blank=True)

    def __str__(self) -> str:
        return self.username
''',
        )

        self._write_file(
            accounts_dir / "admin.py",
            '''from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for the custom User model."""

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("bio", "avatar")}),
    )
''',
        )

        self._write_file(
            accounts_dir / "forms.py",
            '''from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class CustomUserCreationForm(UserCreationForm):
    """Form for creating new users. Includes all required fields."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class CustomUserChangeForm(UserChangeForm):
    """Form for updating users. Includes profile fields."""

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ("username", "email", "bio", "avatar")
''',
        )

        # ── Preset-aware API endpoints ─────────────────────────────────
        if preset_key in ("rest-api", "rest"):
            await self._generate_drf_endpoints(accounts_dir, project_path)
        elif preset_key in ("ninja-api", "ninja"):
            await self._generate_ninja_endpoints(accounts_dir, project_path)
        else:
            await self._generate_standard_views(accounts_dir, project_path)

        # ── Bootstrap 5 templates ──────────────────────────────────────
        templates_dir.mkdir(parents=True, exist_ok=True)
        self._write_file(
            templates_dir / "login.html",
            """{% extends "base.html" %}
{% load static %}

{% block title %}Sign In{% endblock %}

{% block content %}
<div class="container mt-5">
  <div class="row justify-content-center">
    <div class="col-md-5">
      <div class="card shadow">
        <div class="card-body p-4">
          <h3 class="card-title text-center mb-4">Sign In</h3>
          <form method="post">
            {% csrf_token %}
            {% for field in form %}
            <div class="mb-3">
              <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
              {{ field }}
              {% if field.errors %}
              <div class="invalid-feedback d-block">{{ field.errors|striptags }}</div>
              {% endif %}
            </div>
            {% endfor %}
            <button type="submit" class="btn btn-primary w-100">Sign In</button>
          </form>
          <div class="mt-3 text-center">
            <a href="{% url 'signup' %}" class="text-decoration-none">Don't have an account? Sign up</a>
          </div>
          <div class="text-center">
            <a href="{% url 'password_reset' %}" class="text-decoration-none small">Forgot password?</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
        )
        self._write_file(
            templates_dir / "signup.html",
            """{% extends "base.html" %}
{% load static %}

{% block title %}Create Account{% endblock %}

{% block content %}
<div class="container mt-5">
  <div class="row justify-content-center">
    <div class="col-md-6">
      <div class="card shadow">
        <div class="card-body p-4">
          <h3 class="card-title text-center mb-4">Create Account</h3>
          <form method="post">
            {% csrf_token %}
            {% for field in form %}
            <div class="mb-3">
              <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
              {{ field }}
              {% if field.errors %}
              <div class="invalid-feedback d-block">{{ field.errors|striptags }}</div>
              {% endif %}
              {% if field.help_text %}
              <div class="form-text">{{ field.help_text }}</div>
              {% endif %}
            </div>
            {% endfor %}
            <button type="submit" class="btn btn-success w-100">Create Account</button>
          </form>
          <div class="mt-3 text-center">
            <a href="{% url 'login' %}" class="text-decoration-none">Already have an account? Sign in</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
        )
        self._write_file(
            templates_dir / "password_reset_form.html",
            """{% extends "base.html" %}
{% load static %}

{% block title %}Reset Password{% endblock %}

{% block content %}
<div class="container mt-5">
  <div class="row justify-content-center">
    <div class="col-md-5">
      <div class="card shadow">
        <div class="card-body p-4">
          <h3 class="card-title text-center mb-4">Reset Password</h3>
          <p class="text-muted text-center">Enter your email and we'll send you a reset link.</p>
          <form method="post">
            {% csrf_token %}
            {% for field in form %}
            <div class="mb-3">
              <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
              {{ field }}
            </div>
            {% endfor %}
            <button type="submit" class="btn btn-primary w-100">Send Reset Link</button>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
        )
        self._write_file(
            templates_dir / "password_reset_done.html",
            """{% extends "base.html" %}
{% load static %}

{% block title %}Email Sent{% endblock %}

{% block content %}
<div class="container mt-5">
  <div class="row justify-content-center">
    <div class="col-md-5">
      <div class="card shadow text-center">
        <div class="card-body p-5">
          <div class="mb-3">&#9989;</div>
          <h3 class="card-title mb-3">Check Your Email</h3>
          <p class="text-muted">We've emailed instructions for resetting your password.</p>
          <a href="{% url 'login' %}" class="btn btn-primary">Return to Sign In</a>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
        )
        self._write_file(
            templates_dir / "password_reset_confirm.html",
            """{% extends "base.html" %}
{% load static %}

{% block title %}Set New Password{% endblock %}

{% block content %}
<div class="container mt-5">
  <div class="row justify-content-center">
    <div class="col-md-5">
      <div class="card shadow">
        <div class="card-body p-4">
          <h3 class="card-title text-center mb-4">Set New Password</h3>
          {% if validlink %}
          <form method="post">
            {% csrf_token %}
            {% for field in form %}
            <div class="mb-3">
              <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
              {{ field }}
              {% if field.errors %}
              <div class="invalid-feedback d-block">{{ field.errors|striptags }}</div>
              {% endif %}
            </div>
            {% endfor %}
            <button type="submit" class="btn btn-primary w-100">Change Password</button>
          </form>
          {% else %}
          <p class="text-danger">The reset link is invalid or has expired.</p>
          <a href="{% url 'password_reset' %}" class="btn btn-primary">Request New Link</a>
          {% endif %}
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
        )
        self._write_file(
            templates_dir / "password_reset_complete.html",
            """{% extends "base.html" %}
{% load static %}

{% block title %}Password Reset Complete{% endblock %}

{% block content %}
<div class="container mt-5">
  <div class="row justify-content-center">
    <div class="col-md-5">
      <div class="card shadow text-center">
        <div class="card-body p-5">
          <div class="mb-3">&#9989;</div>
          <h3 class="card-title mb-3">Password Changed</h3>
          <p class="text-muted">Your password has been set successfully.</p>
          <a href="{% url 'login' %}" class="btn btn-primary">Sign In</a>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
        )

        # ── Inject settings and wire URLs ─────────────────────────────
        await self._inject_settings(project_path)
        await self._update_env(project_path)

    # ── Preset-specific generators ─────────────────────────────────────

    async def _generate_drf_endpoints(
        self,
        accounts_dir: Path,
        project_path: Path,
    ) -> None:
        """Generate DRF serializers, views, and URLs for REST API presets."""
        api_dir = accounts_dir / "api"
        api_dir.mkdir(parents=True, exist_ok=True)
        self._write_file(api_dir / "__init__.py", "")

        self._write_file(
            api_dir / "serializers.py",
            """from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "bio",
            "avatar",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
""",
        )

        self._write_file(
            api_dir / "views.py",
            """from django.contrib.auth import get_user_model
from rest_framework import generics, permissions

from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
""",
        )

        self._write_file(
            api_dir / "urls.py",
            """from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
]
""",
        )

        self._write_file(
            accounts_dir / "urls.py",
            """from django.urls import include, path

urlpatterns = [
    path("api/auth/", include("accounts.api.urls")),
]
""",
        )

        # Wire root urlconf
        text = (
            project_path / project_path.name / "urls.py"
            if (project_path / project_path.name / "urls.py").exists()
            else project_path / "config" / "urls.py"
        )
        if text.exists():
            content = text.read_text(encoding="utf-8")
            content = SettingsInjector.inject_urls(content, [("", "accounts.urls")])
            text.write_text(content)

    async def _generate_ninja_endpoints(
        self,
        accounts_dir: Path,
        project_path: Path,
    ) -> None:
        """Generate Ninja schemas and routers for Ninja API presets."""
        api_dir = accounts_dir / "api"
        api_dir.mkdir(parents=True, exist_ok=True)
        self._write_file(api_dir / "__init__.py", "")

        self._write_file(
            api_dir / "schemas.py",
            """from ninja import ModelSchema, Schema

from accounts.models import User


class UserOut(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "username", "email", "bio", "avatar", "date_joined"]


class RegisterIn(Schema):
    username: str
    email: str
    password: str


class LoginIn(Schema):
    username: str
    password: str


class TokenOut(Schema):
    access: str
    refresh: str
""",
        )

        self._write_file(
            api_dir / "endpoints.py",
            """from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import aget_object_or_404
from ninja import Router
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken

from accounts.models import User
from .schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = Router()

UserModel = get_user_model()


@router.post("/register/", response=UserOut, auth=None)
def register(request, payload: RegisterIn):
    user = UserModel.objects.create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    return user


@router.post("/login/", response=TokenOut, auth=None)
def login(request, payload: LoginIn):
    user = authenticate(
        request,
        username=payload.username,
        password=payload.password,
    )
    if user is None:
        from ninja.errors import HttpError
        raise HttpError(401, "Invalid credentials")
    refresh = RefreshToken.for_user(user)
    return TokenOut(
        access=str(refresh.access_token),
        refresh=str(refresh),
    )


@router.get("/profile/", response=UserOut, auth=JWTAuth())
def profile(request):
    return request.user


@router.get("/users/", response=list[UserOut], auth=JWTAuth())
def list_users(request):
    return UserModel.objects.all()
""",
        )

        self._write_file(
            accounts_dir / "urls.py",
            """from django.urls import path

urlpatterns = []
""",
        )

        # Wire Ninja router into root api.py or urls.py
        project_pkg = project_path / project_path.name
        if not project_pkg.exists():
            project_pkg = project_path / "config"

        api_py = project_pkg / "api.py"
        if api_py.exists():
            # Inject into existing Ninja api.py
            content = api_py.read_text(encoding="utf-8")
            content = content.rstrip()
            content += (
                "\n\n# Accounts endpoints\n"
                "from accounts.api.endpoints import router as accounts_router\n"
                'api.add_router("/auth", accounts_router, tags=["Auth"])\n'
            )
            api_py.write_text(content)

    async def _generate_standard_views(
        self,
        accounts_dir: Path,
        project_path: Path,
    ) -> None:
        """Generate server-rendered views for monolith presets."""
        self._write_file(
            accounts_dir / "views.py",
            """from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import (
    LoginView as BaseLoginView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import User


class LoginView(BaseLoginView):
    template_name = "registration/login.html"


class SignupView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class ProfileDetailView(DetailView):
    model = User
    template_name = "registration/profile_detail.html"

    def get_object(self):
        return self.request.user


class ProfileUpdateView(UpdateView):
    form_class = CustomUserChangeForm
    template_name = "registration/profile_form.html"

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        return reverse_lazy("profile_detail")
""",
        )

        self._write_file(
            accounts_dir / "urls.py",
            """from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.SignupView.as_view(), name="signup"),
    path(
        "profile/",
        views.ProfileDetailView.as_view(),
        name="profile_detail",
    ),
    path(
        "profile/edit/",
        views.ProfileUpdateView.as_view(),
        name="profile_update",
    ),
    # Password reset
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
""",
        )

        # Add profile templates
        profile_dir = project_path / "templates" / "registration"
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._write_file(
            profile_dir / "profile_detail.html",
            """{% extends "base.html" %}
{% load static %}

{% block title %}My Profile{% endblock %}

{% block content %}
<div class="container mt-4">
  <div class="row justify-content-center">
    <div class="col-md-6">
      <div class="card shadow">
        <div class="card-body p-4">
          <h3 class="card-title mb-4">My Profile</h3>
          <dl class="row">
            <dt class="col-sm-4">Username</dt>
            <dd class="col-sm-8">{{ user.username }}</dd>
            <dt class="col-sm-4">Email</dt>
            <dd class="col-sm-8">{{ user.email }}</dd>
            <dt class="col-sm-4">Bio</dt>
            <dd class="col-sm-8">{{ user.bio|default:"—" }}</dd>
            <dt class="col-sm-4">Joined</dt>
            <dd class="col-sm-8">{{ user.date_joined|date }}</dd>
          </dl>
          <a href="{% url 'profile_update' %}" class="btn btn-primary">Edit Profile</a>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
        )
        self._write_file(
            profile_dir / "profile_form.html",
            """{% extends "base.html" %}
{% load static %}

{% block title %}Edit Profile{% endblock %}

{% block content %}
<div class="container mt-4">
  <div class="row justify-content-center">
    <div class="col-md-6">
      <div class="card shadow">
        <div class="card-body p-4">
          <h3 class="card-title mb-4">Edit Profile</h3>
          <form method="post">
            {% csrf_token %}
            {% for field in form %}
            <div class="mb-3">
              <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
              {{ field }}
              {% if field.errors %}
              <div class="invalid-feedback d-block">{{ field.errors|striptags }}</div>
              {% endif %}
            </div>
            {% endfor %}
            <button type="submit" class="btn btn-primary">Save Changes</button>
            <a href="{% url 'profile_detail' %}" class="btn btn-outline-secondary">Cancel</a>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
        )

        # Wire root urlconf for monolith
        text = (
            project_path / project_path.name / "urls.py"
            if (project_path / project_path.name / "urls.py").exists()
            else project_path / "config" / "urls.py"
        )
        if text.exists():
            content = text.read_text(encoding="utf-8")
            content = SettingsInjector.inject_urls(
                content, [("accounts/", "accounts.urls")]
            )
            text.write_text(content)
