"""Database connection using the DB_URL secret (Supabase session pooler)."""

from __future__ import annotations

import psycopg
from foundations.secrets import get_secret


def connect(url: str | None = None) -> psycopg.Connection:
    """A psycopg 3 connection. Prepared statements are off so any Supabase pooler mode works."""
    return psycopg.connect(
        url or get_secret("DB_URL"),
        prepare_threshold=None,
        connect_timeout=30,
        application_name="statsmu-ingestion",
    )
