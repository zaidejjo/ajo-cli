"""Validation utilities for project and app names."""

import keyword
import re
from typing import Tuple


class ProjectNameValidator:
    """Validate Django project names."""

    RESERVED_NAMES = {
        "test",
        "django",
        "python",
        "site",
        "config",
        "settings",
        "urls",
        "wsgi",
        "asgi",
        "manage",
        "admin",
        "app",
        "project",
    }

    @classmethod
    def validate(cls, name: str) -> Tuple[bool, str]:
        """
        Validate project name.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name or len(name.strip()) == 0:
            return False, "Project name cannot be empty"

        name = name.strip()

        # Check length
        if len(name) > 50:
            return False, "Project name too long (max 50 characters)"

        # Check first character
        if not name[0].isalpha() and name[0] != "_":
            return False, "Project name must start with a letter or underscore"

        # Check allowed characters
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            return False, "Project name can only contain letters, numbers, and underscores"

        # Check Python keywords
        if keyword.iskeyword(name):
            return False, f"'{name}' is a Python keyword and cannot be used"

        # Check reserved names
        if name.lower() in cls.RESERVED_NAMES:
            return False, f"'{name}' is a reserved name in Django"

        return True, ""

    @classmethod
    def sanitize(cls, desired_name: str) -> str:
        """Convert any string to a valid Django project name."""
        name = desired_name.strip().lower()

        # Replace invalid chars with underscore
        name = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        # Remove multiple underscores
        name = re.sub(r"_+", "_", name)

        # Remove leading/trailing underscores
        name = name.strip("_")

        # Must start with letter
        if name and name[0].isdigit():
            name = f"project_{name}"

        # Handle empty name
        if not name:
            name = "myproject"

        # Handle reserved names
        if name in cls.RESERVED_NAMES:
            name = f"{name}_app"

        # Handle keywords
        if keyword.iskeyword(name):
            name = f"{name}_project"

        return name


class AppNameValidator:
    """Validate Django app names."""

    RESERVED_NAMES = {
        "test",
        "django",
        "python",
        "site",
        "config",
        "settings",
        "urls",
        "wsgi",
        "asgi",
        "manage",
        "admin",
    }

    @classmethod
    def validate(cls, name: str) -> Tuple[bool, str]:
        """Validate app name."""
        if not name or len(name.strip()) == 0:
            return False, "App name cannot be empty"

        name = name.strip()

        if len(name) > 50:
            return False, "App name too long (max 50 characters)"

        if not name[0].isalpha():
            return False, "App name must start with a letter"

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            return False, "App name can only contain letters, numbers, and underscores"

        if keyword.iskeyword(name):
            return False, f"'{name}' is a Python keyword"

        if name.lower() in cls.RESERVED_NAMES:
            return False, f"'{name}' is a reserved name in Django"

        return True, ""
