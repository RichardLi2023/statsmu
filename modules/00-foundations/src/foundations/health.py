"""The /health payload shared by every service (contract section 3)."""

from __future__ import annotations

import os

from foundations.env import current_env, release_version


def health() -> dict[str, str]:
    commit = (os.environ.get("APP_COMMIT") or "unknown")[:7]
    return {"status": "ok", "env": current_env(), "version": release_version(), "commit": commit}
