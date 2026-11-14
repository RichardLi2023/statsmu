"""Command line: python -m ingestion {migrate,check-registry,run,smoke} (contract section 6)."""

from __future__ import annotations

import argparse
import sys

from foundations.errors import init_error_tracking
from foundations.logging import get_logger

from ingestion import registry

log = get_logger("ingestion")


def _migrate(args: argparse.Namespace) -> int:
    from ingestion import store
    from ingestion.db import connect

    with connect() as conn:
        applied = store.migrate(conn)
    log.info("migrations applied" if applied else "schema up to date", extra={"applied": applied})
    return 0


def _check_registry(args: argparse.Namespace) -> int:
    entries = registry.load()
    for e in entries:
        print(f"ok  {e.id:<24} {e.connector:<6} {'active' if e.active else 'inactive'}")
    return 0


def _run(args: argparse.Namespace) -> int:
    from ingestion import runner, store
    from ingestion.db import connect

    entries = registry.load()
    with connect() as conn:
        store.migrate(conn)
        result = runner.run(conn, entries, trigger=args.trigger, source=args.source)
    log.info(
        "run finished",
        extra={
            "pulled": len(result.pulled),
            "changed": sum(o.changed for o in result.pulled),
            "skipped": result.skipped,
            "failed": result.failed,
        },
    )
    return 1 if result.failed else 0


def _smoke(args: argparse.Namespace) -> int:
    from ingestion.checks import run_checks
    from ingestion.connectors import get_connector

    entries = [e for e in registry.load() if (e.id == args.source if args.source else e.active)]
    failed = 0
    for e in entries:
        try:
            c = get_connector(e.connector)
            d = c.discover(e)
            parsed = c.parse(e, c.fetch(e))
            results = run_checks(e.checks, parsed.rows)
            bad = [r for r in results if not r["passed"]]
            print(
                f"ok  {e.id}: {len(parsed.rows)} rows, feed reports {d.observation_count}, "
                f"latest {d.latest_period}, updated {d.last_updated}; "
                f"checks {'passed' if not bad else 'FAILED: ' + str(bad)}"
            )
        except Exception as exc:
            failed += 1
            log.error("smoke test failed", exc_info=exc, extra={"dataset": e.id})
    return 1 if failed or not entries else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ingestion")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate").set_defaults(fn=_migrate)
    sub.add_parser("check-registry").set_defaults(fn=_check_registry)
    p = sub.add_parser("run")
    p.add_argument("--source")
    p.add_argument("--trigger", choices=["schedule", "manual"], default="manual")
    p.set_defaults(fn=_run)
    p = sub.add_parser("smoke")
    p.add_argument("--source")
    p.set_defaults(fn=_smoke)
    args = parser.parse_args(argv)
    init_error_tracking("ingestion")
    try:
        return args.fn(args)
    except Exception as exc:
        log.error("command failed", exc_info=exc, extra={"command": args.command})
        return 1
    finally:
        try:
            import sentry_sdk

            sentry_sdk.flush(timeout=5)
        except Exception:  # noqa: S110 - flushing is best effort
            pass


if __name__ == "__main__":
    sys.exit(main())
