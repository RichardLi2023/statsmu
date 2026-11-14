"""One ingestion run: mirror the registry, then pull every active source that is due."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import psycopg
from foundations.logging import get_logger

from ingestion import store
from ingestion.checks import run_checks
from ingestion.connectors import Connector, Discovery, RawArtefact, get_connector
from ingestion.normalise import content_checksum, diff, normalise, text_checksum
from ingestion.registry import SourceEntry
from ingestion.version import code_version

log = get_logger("ingestion")

DUE_AFTER = {"day": timedelta(hours=20), "week": timedelta(days=6), "month": timedelta(days=27)}


@dataclass
class RunResult:
    pulled: list[store.Outcome] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def is_due(entry: SourceEntry, last: store.LastPull | None, now: datetime) -> bool:
    return last is None or now - last.finished_at >= DUE_AFTER[entry.check_every]


def run(
    conn: psycopg.Connection,
    entries: list[SourceEntry],
    *,
    trigger: str = "manual",
    source: str | None = None,
    connectors: dict[str, Connector] | None = None,
    now: datetime | None = None,
) -> RunResult:
    now = now or datetime.now(UTC)
    store.mirror_sources(conn, entries)
    result = RunResult()
    selected = (
        [e for e in entries if e.id == source] if source else [e for e in entries if e.active]
    )
    if source and not selected:
        raise ValueError(f"No registry entry with id {source!r}")
    for entry in selected:
        last = store.last_ok_pull(conn, entry.id)
        if not source and not is_due(entry, last, now):
            result.skipped.append(entry.id)
            log.info("not due", extra={"dataset": entry.id})
            continue
        connector = (connectors or {}).get(entry.connector) or get_connector(entry.connector)
        outcome = pull_one(conn, entry, connector, trigger=trigger, previous=last)
        if outcome is None:
            result.failed.append(entry.id)
        else:
            result.pulled.append(outcome)
    return result


def pull_one(
    conn: psycopg.Connection,
    entry: SourceEntry,
    connector: Connector,
    *,
    trigger: str,
    previous: store.LastPull | None,
) -> store.Outcome | None:
    pull_id = store.start_pull(conn, entry.id, trigger, code_version())
    ctx = {"dataset": entry.id, "pull_id": pull_id}
    discovery: Discovery | None = None
    artefacts: list[RawArtefact] = []
    try:
        try:
            discovery = connector.discover(entry)
        except Exception as exc:  # the light check is informative only; the fetch decides
            log.warning("discover failed; fetching anyway", extra={**ctx, "reason": str(exc)})
        artefacts = connector.fetch(entry)
        parsed = connector.parse(entry, artefacts)
        rows = [normalise(r) for r in parsed.rows]
        checksum = content_checksum(rows)
        structure = text_checksum(parsed.structure_fingerprint)
        changed = (
            previous is None
            or previous.content_checksum != checksum
            or previous.structure_checksum != structure
        )
        change = checks = None
        if changed:
            old_batch = store.latest_batch_id(conn, entry.id) if previous else None
            old_rows = list(store.staged_rows(conn, old_batch)) if old_batch else []
            conn.commit()
            change = diff(old_rows, rows)
            checks = run_checks(entry.checks, rows)
        outcome = store.complete_pull(
            conn,
            entry=entry,
            pull_id=pull_id,
            discovery=discovery,
            artefacts=artefacts,
            rows=rows,
            labels=parsed.labels,
            content_checksum=checksum,
            structure_checksum=structure,
            previous=previous,
            diff=change,
            checks=checks,
        )
    except Exception as exc:
        store.fail_pull(conn, pull_id, f"{type(exc).__name__}: {exc}", discovery, artefacts)
        log.error("pull failed", exc_info=exc, extra=ctx)
        return None
    if outcome.changed:
        log.info(
            "new data",
            extra={
                **ctx,
                "event_id": outcome.event_id,
                "batch_id": outcome.batch_id,
                "added": change.added,
                "removed": change.removed,
                "revised": change.revised,
                "periods": change.periods_affected,
                "checks_passed": all(c["passed"] for c in checks),
            },
        )
    else:
        log.info("no change", extra={**ctx, "rows": len(rows)})
    return outcome
