"""The `ingestion` schema: migrations, raw store, staging and events (contract section 3)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from importlib import resources

import psycopg
from psycopg.types.json import Jsonb

from ingestion.connectors import Discovery, RawArtefact, StandardRow
from ingestion.normalise import Diff
from ingestion.registry import SourceEntry

_LOCK_ID = 7_001_001  # advisory lock held while migrating


# migrations ---------------------------------------------------------------------------------
def migration_files() -> list[tuple[str, str]]:
    folder = resources.files("ingestion") / "migrations"
    files = sorted(f for f in folder.iterdir() if f.name.endswith(".sql"))
    return [(f.name.removesuffix(".sql"), f.read_text(encoding="utf-8")) for f in files]


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations, in order, each in its own transaction. Returns those applied."""
    applied: list[str] = []
    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(%s)", (_LOCK_ID,))
        conn.execute("create schema if not exists ingestion")
        conn.execute(
            "create table if not exists ingestion.schema_migrations ("
            " version text primary key, applied_at timestamptz not null default now())"
        )
        conn.execute("alter table ingestion.schema_migrations enable row level security")
        done = {r[0] for r in conn.execute("select version from ingestion.schema_migrations")}
        for version, sql in migration_files():
            if version in done:
                continue
            conn.execute(sql)
            conn.execute(
                "insert into ingestion.schema_migrations (version) values (%s)", (version,)
            )
            applied.append(version)
    return applied


# registry mirror ----------------------------------------------------------------------------
def mirror_sources(conn: psycopg.Connection, entries: list[SourceEntry]) -> None:
    with conn.transaction():
        for e in entries:
            conn.execute(
                """insert into ingestion.sources
                   (source_id, connector, active, licence, access_rule, credit_line, themes,
                    definition, updated_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, now())
                   on conflict (source_id) do update set
                     connector = excluded.connector, active = excluded.active,
                     licence = excluded.licence, access_rule = excluded.access_rule,
                     credit_line = excluded.credit_line, themes = excluded.themes,
                     definition = excluded.definition, updated_at = now()
                   where ingestion.sources.definition is distinct from excluded.definition""",
                (
                    e.id,
                    e.connector,
                    e.active,
                    e.licence,
                    e.access_rule,
                    e.credit_line,
                    e.themes,
                    Jsonb(e.definition),
                ),
            )
        # A registry file that was removed keeps its history but is never pulled again.
        conn.execute(
            "update ingestion.sources set active = false, updated_at = now()"
            " where active and not (source_id = any(%s))",
            ([e.id for e in entries],),
        )


# pulls --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LastPull:
    pull_id: int
    content_checksum: str | None
    structure_checksum: str | None
    finished_at: datetime


def last_ok_pull(conn: psycopg.Connection, source_id: str) -> LastPull | None:
    row = conn.execute(
        """select pull_id, content_checksum, structure_checksum, finished_at
           from ingestion.raw_pulls where source_id = %s and status = 'ok'
           order by pull_id desc limit 1""",
        (source_id,),
    ).fetchone()
    conn.commit()
    return LastPull(*row) if row else None


def latest_batch_id(conn: psycopg.Connection, source_id: str) -> int | None:
    row = conn.execute(
        "select max(batch_id) from ingestion.staging_batches where source_id = %s", (source_id,)
    ).fetchone()
    conn.commit()
    return row[0] if row else None


def start_pull(conn: psycopg.Connection, source_id: str, trigger: str, code_version: str) -> int:
    with conn.transaction():
        row = conn.execute(
            """insert into ingestion.raw_pulls (source_id, status, trigger, code_version)
               values (%s, 'running', %s, %s) returning pull_id""",
            (source_id, trigger, code_version),
        ).fetchone()
    return row[0]


def _save_files(conn: psycopg.Connection, pull_id: int, artefacts: list[RawArtefact]) -> None:
    for a in artefacts:
        sha = hashlib.sha256(a.content).hexdigest()
        conn.execute(
            """insert into ingestion.raw_blobs (sha256, media_type, size_bytes, content)
               values (%s, %s, %s, %s) on conflict (sha256) do nothing""",
            (sha, a.media_type, len(a.content), a.content),
        )
        conn.execute(
            """insert into ingestion.raw_pull_files
               (pull_id, kind, url, http_status, media_type, size_bytes, sha256)
               values (%s, %s, %s, %s, %s, %s, %s)""",
            (pull_id, a.kind, a.url, a.http_status, a.media_type, len(a.content), sha),
        )


def fail_pull(
    conn: psycopg.Connection,
    pull_id: int,
    error: str,
    discovery: Discovery | None = None,
    artefacts: list[RawArtefact] | None = None,
) -> None:
    conn.rollback()
    with conn.transaction():
        if artefacts:
            _save_files(conn, pull_id, artefacts)
        conn.execute(
            """update ingestion.raw_pulls set status = 'failed', error = %s, finished_at = now(),
               discovery = %s where pull_id = %s""",
            (error[:4000], Jsonb(discovery.as_json()) if discovery else None, pull_id),
        )


@dataclass(frozen=True)
class Outcome:
    pull_id: int
    changed: bool
    batch_id: int | None = None
    event_id: int | None = None


def complete_pull(
    conn: psycopg.Connection,
    *,
    entry: SourceEntry,
    pull_id: int,
    discovery: Discovery | None,
    artefacts: list[RawArtefact],
    rows: list[StandardRow],
    labels: dict[str, dict[str, str]],
    content_checksum: str,
    structure_checksum: str | None,
    previous: LastPull | None,
    diff: Diff | None,
    checks: list[dict] | None,
) -> Outcome:
    """Write the pull's files and status and, when it changed, its batch, rows, labels and
    event, all in one transaction."""
    changed = diff is not None
    with conn.transaction():
        _save_files(conn, pull_id, artefacts)
        conn.execute(
            """update ingestion.raw_pulls set status = 'ok', finished_at = now(), discovery = %s,
               content_checksum = %s, structure_checksum = %s, row_count = %s, changed = %s
               where pull_id = %s""",
            (
                Jsonb(discovery.as_json()) if discovery else None,
                content_checksum,
                structure_checksum,
                len(rows),
                changed,
                pull_id,
            ),
        )
        if not changed:
            return Outcome(pull_id, False)
        checks = checks or []
        passed = all(c["passed"] for c in checks)
        batch_id = conn.execute(
            """insert into ingestion.staging_batches (pull_id, source_id, row_count, checks, status)
               values (%s, %s, %s, %s, %s) returning batch_id""",
            (
                pull_id,
                entry.id,
                len(rows),
                Jsonb(checks),
                "checks_passed" if passed else "checks_failed",
            ),
        ).fetchone()[0]
        with conn.cursor().copy(
            "copy ingestion.staged_rows (batch_id, row_no, dimensions, period, value, attributes)"
            " from stdin"
        ) as copy:
            for n, r in enumerate(rows, start=1):
                copy.write_row(
                    (batch_id, n, Jsonb(r.dimensions), r.period, r.value, Jsonb(r.attributes))
                )
        structure_changed = (
            previous is not None and previous.structure_checksum != structure_checksum
        )
        if previous is None or structure_changed:
            conn.execute("delete from ingestion.code_labels where source_id = %s", (entry.id,))
            with conn.cursor().copy(
                "copy ingestion.code_labels (source_id, concept, code, label, pull_id) from stdin"
            ) as copy:
                for concept, codes in labels.items():
                    for code, label in codes.items():
                        copy.write_row((entry.id, concept, code, label, pull_id))
        event_id = conn.execute(
            """insert into ingestion.events
               (event_type, source_id, pull_id, previous_pull_id, batch_id, initial, added,
                removed, revised, periods_affected, structure_changed, checks_passed)
               values ('new_data', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               returning event_id""",
            (
                entry.id,
                pull_id,
                previous.pull_id if previous else None,
                batch_id,
                previous is None,
                diff.added,
                diff.removed,
                diff.revised,
                diff.periods_affected,
                structure_changed,
                passed,
            ),
        ).fetchone()[0]
    return Outcome(pull_id, True, batch_id, event_id)


# public readers (contract section 7) --------------------------------------------------------
@dataclass(frozen=True)
class Event:
    event_id: int
    event_type: str
    source_id: str
    pull_id: int
    previous_pull_id: int | None
    batch_id: int
    initial: bool
    added: int
    removed: int
    revised: int
    periods_affected: list[str]
    structure_changed: bool
    checks_passed: bool
    created_at: datetime


_EVENT_COLUMNS = ", ".join(Event.__dataclass_fields__)


def events_since(conn: psycopg.Connection, after_event_id: int = 0) -> list[Event]:
    rows = conn.execute(
        f"select {_EVENT_COLUMNS} from ingestion.events where event_id > %s order by event_id",  # noqa: S608
        (after_event_id,),
    ).fetchall()
    return [Event(*r) for r in rows]


class RawNotFoundError(LookupError):
    """Raised when a pull has no raw file of the requested kind."""


def read_raw(conn: psycopg.Connection, pull_id: int, kind: str = "data") -> bytes:
    row = conn.execute(
        """select b.content from ingestion.raw_pull_files f
           join ingestion.raw_blobs b using (sha256) where f.pull_id = %s and f.kind = %s""",
        (pull_id, kind),
    ).fetchone()
    if row is None:
        raise RawNotFoundError(f"Pull {pull_id} has no {kind!r} file")
    return bytes(row[0])


def staged_rows(conn: psycopg.Connection, batch_id: int) -> Iterator[StandardRow]:
    source = conn.execute(
        "select source_id from ingestion.staging_batches where batch_id = %s", (batch_id,)
    ).fetchone()
    if source is None:
        return
    cur = conn.execute(
        """select dimensions, period, value, attributes from ingestion.staged_rows
           where batch_id = %s order by row_no""",
        (batch_id,),
    )
    for dims, period, value, attrs in cur:
        yield StandardRow(
            source[0], dims, period, Decimal(value) if value is not None else None, attrs
        )
