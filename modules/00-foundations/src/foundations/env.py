"""Which environment the code is running in."""

from __future__ import annotations

import os

ENVIRONMENTS = ("dev", "staging", "live")


class InvalidEnvironmentError(RuntimeError):
    """Raised when APP_ENV holds a value outside the contract."""


def current_env() -> str:
    """Return the current environment from APP_ENV, defaulting to 'dev' when unset."""
    value = os.environ.get("APP_ENV", "dev").strip().lower()
    if value not in ENVIRONMENTS:
        raise InvalidEnvironmentError(
            f"APP_ENV must be one of {', '.join(ENVIRONMENTS)}; got {value!r}"
        )
    return value


def release_version() -> str:
    """Return the release tag deployed, or 'unreleased'."""
    return os.environ.get("APP_VERSION", "").strip() or "unreleased"
