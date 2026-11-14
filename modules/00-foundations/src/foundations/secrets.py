"""Reading secrets by convention. Secrets live in the environment, never in code."""

from __future__ import annotations

import os
import re

CATEGORIES = ("SOURCE", "DB", "AUTH", "SENTRY", "EMAIL", "VERCEL", "API", "APP")
_NAME = re.compile(r"^(" + "|".join(CATEGORIES) + r")(_[A-Z0-9]+)+$")


class SecretNameError(ValueError):
    """Raised when a secret name breaks the naming convention."""


class MissingSecretError(RuntimeError):
    """Raised when a required secret is not set."""


def validate_name(name: str) -> str:
    """Check a secret name against the convention <CATEGORY>_<NAME>."""
    if not _NAME.match(name):
        raise SecretNameError(
            f"Secret name {name!r} must be <CATEGORY>_<NAME> in upper case, "
            f"with CATEGORY one of {', '.join(CATEGORIES)}"
        )
    return name


def get_secret(name: str, required: bool = True) -> str | None:
    """Return the secret's value from the environment."""
    validate_name(name)
    value = os.environ.get(name)
    if value is None or value == "":
        if required:
            raise MissingSecretError(f"Secret {name} is not set in this environment")
        return None
    return value
