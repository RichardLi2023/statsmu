"""The code version recorded with every pull: release tag, else short commit, else 'dev'."""

from __future__ import annotations

import os


def code_version() -> str:
    tag = os.environ.get("APP_VERSION", "").strip()
    if tag and tag != "unreleased":
        return tag
    commit = os.environ.get("APP_COMMIT") or os.environ.get("GITHUB_SHA") or ""
    return commit[:7] or "dev"
