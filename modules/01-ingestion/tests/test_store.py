"""Raw store, staging, change events and failures on a temporary PostgreSQL (sections 3, 4, 6).

These tests prove the "done when" behaviour with the recorded DF_POP files.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ingestion import Event, events_since, read_raw, runner, staged_rows, store

DATA = (Path(__file__).parent / "fixtures" / "df_pop_data.csv").read_bytes()
EOY_2025 = b"POP_EOY,_T,_T,2025,1241856,"


def changed_figure(data: bytes = DATA) -> bytes:
    assert data.count(EOY_2025) == 1
    return data.replace(EOY_2025, b"POP_EOY,_T,_T,2025,1241999,")


def reordered(data: bytes = DATA) -> bytes:
    head, *lines = data.split(b"\r\n")
    body = [x for x in lines if x]
    return b"\r\n".join([head, *reversed(body)]) + b"\r\n"


def structure_with_new_label() -> bytes:
    import json

    s = json.loads((Path(__file__).parent / "fixtures" / "df_pop_structure.json").read_bytes())
    for cl in s["data"]["codelists"]:
        if cl["id"] == "CL_SEX":
            for code in cl["codes"]:
                if code["id"] == "F":
                    code["name"] = "Women"
                    code["names"] = {"en": "Women"}
    return json.dumps(s).encode()


def pull(conn, entry, connector, now=None, source="sm_df_pop"):
    return runner.run(
        conn, [entry], connectors={"sdmx": connector}, source=source, now=now, trigger="manual"
    )


def count(conn, table):
    return conn.execute(f"select count(*) from ingestion.{table}").fetchone()[0]  # noqa: S608


def test_migrations_create_every_contract_table(conn):
    names = {
        r[0]
        for r in conn.execute(
            "select table_name from information_schema.tables where table_schema = 'ingestion'"
        )
    }
    assert names >= {
        "sources",
        "raw_pulls",
        "raw_pull_files",
        "raw_blobs",
        "staging_batches",
        "staged_rows",
        "code_labels",
        "events",
        "schema_migrations",
    }
    assert store.migrate(conn) == []  # idempotent
    rls = conn.execute(
        "select bool_and(relrowsecurity) from pg_class c"
        " join pg_namespace n on n.oid = c.relnamespace"
        " where n.nspname = 'ingestion' and c.relkind = 'r'"
    ).fetchone()[0]
    assert rls is True


def test_first_pull_stores_raw_stages_rows_and_raises_initial_event(conn, pop_entry, recorded):
    result = pull(conn, pop_entry, recorded())
    assert not result.failed and len(result.pulled) == 1
    out = result.pulled[0]
    assert out.changed and out.event_id and out.batch_id
    assert read_raw(conn, out.pull_id) == DATA
    assert read_raw(conn, out.pull_id, "structure").startswith(b"{")
    pull_row = conn.execute(
        "select status, row_count, changed, code_version, content_checksum,"
        " discovery->>'observation_count'"
        " from ingestion.raw_pulls where pull_id = %s",
        (out.pull_id,),
    ).fetchone()
    assert pull_row[:3] == ("ok", 1159, True) and pull_row[3] and len(pull_row[4]) == 64
    assert pull_row[5] == "1159"
    rows = list(staged_rows(conn, out.batch_id))
    assert len(rows) == 1159 and rows[0].dataset == "sm_df_pop"
    assert isinstance(rows[0].value, Decimal)
    [event] = events_since(conn)
    assert isinstance(event, Event)
    assert event.initial and event.event_type == "new_data" and event.added == 1159
    assert event.previous_pull_id is None and event.checks_passed
    labels = dict(
        conn.execute(
            "select code, label from ingestion.code_labels"
            " where source_id = 'sm_df_pop' and concept = 'AGE'"
        ).fetchall()
    )
    assert labels["Y_GE85"] == "85 years old and over"
    batch = conn.execute("select status, checks from ingestion.staging_batches").fetchone()
    assert batch[0] == "checks_passed" and len(batch[1]) == len(pop_entry.checks)
    src = conn.execute("select licence, access_rule, credit_line from ingestion.sources").fetchone()
    assert src == ("free_with_credit", "by_tier", "Source: Statistics Mauritius")


def test_unchanged_or_reordered_pull_raises_no_event(conn, pop_entry, recorded):
    pull(conn, pop_entry, recorded())
    again = pull(conn, pop_entry, recorded()).pulled[0]
    shuffled = pull(conn, pop_entry, recorded(data=reordered())).pulled[0]
    assert not again.changed and not shuffled.changed
    assert len(events_since(conn)) == 1
    assert count(conn, "staging_batches") == 1
    assert count(conn, "raw_pulls") == 3
    # identical files are stored once; the reordered file is new bytes, kept as received
    assert count(conn, "raw_blobs") == 3
    assert read_raw(conn, shuffled.pull_id) == reordered()


def test_a_changed_figure_raises_exactly_one_event_naming_it(conn, pop_entry, recorded):
    first = pull(conn, pop_entry, recorded()).pulled[0]
    changed = pull(conn, pop_entry, recorded(data=changed_figure())).pulled[0]
    assert changed.changed
    events = events_since(conn, after_event_id=first.event_id)
    assert len(events) == 1
    e = events[0]
    assert (e.added, e.removed, e.revised) == (0, 0, 1)
    assert e.periods_affected == ["2025"] and not e.initial and not e.structure_changed
    assert e.previous_pull_id == first.pull_id and e.batch_id == changed.batch_id
    new = {
        (tuple(sorted(r.dimensions.items())), r.period): r.value
        for r in staged_rows(conn, e.batch_id)
    }
    key = (
        tuple(
            sorted(
                {
                    "FREQ": "A",
                    "REF_AREA": "MU",
                    "INDIC_POP": "POP_EOY",
                    "SEX": "_T",
                    "AGE": "_T",
                }.items()
            )
        ),
        "2025",
    )
    assert new[key] == Decimal("1241999")
    # the next identical pull is quiet again
    assert not pull(conn, pop_entry, recorded(data=changed_figure())).pulled[0].changed
    assert events_since(conn, after_event_id=e.event_id) == []


def test_structure_change_is_flagged(conn, pop_entry, recorded):
    pull(conn, pop_entry, recorded())
    out = pull(conn, pop_entry, recorded(structure=structure_with_new_label())).pulled[0]
    e = events_since(conn)[-1]
    assert out.changed and e.structure_changed and (e.added, e.removed, e.revised) == (0, 0, 0)
    label = conn.execute(
        "select label from ingestion.code_labels where concept = 'SEX' and code = 'F'"
    ).fetchone()[0]
    assert label == "Women"


def test_failed_checks_still_raise_the_event(conn, pop_entry, recorded):
    broken = DATA.replace(b"POP_MIDY,_T,_T,2025,", b"POP_MIDY,_T,_T,2025,9")
    assert broken != DATA
    out = pull(conn, pop_entry, recorded(data=broken)).pulled[0]
    e = events_since(conn)[-1]
    assert out.changed and not e.checks_passed
    status = conn.execute("select status from ingestion.staging_batches").fetchone()[0]
    assert status == "checks_failed"


def test_failed_pull_is_recorded_and_others_continue(conn, pop_entry, recorded):
    other = pop_entry.__class__.from_dict(pop_entry.definition | {"id": "sm_df_other"})
    result = runner.run(
        conn, [pop_entry, other], connectors={"sdmx": recorded(fail=True)}, trigger="schedule"
    )
    assert sorted(result.failed) == ["sm_df_other", "sm_df_pop"]
    rows = conn.execute("select status, error, trigger from ingestion.raw_pulls").fetchall()
    assert all(r[0] == "failed" and "unreachable" in r[1] and r[2] == "schedule" for r in rows)
    assert events_since(conn) == []


def test_parse_failure_keeps_the_raw_file(conn, pop_entry, recorded):
    result = pull(conn, pop_entry, recorded(data=b"not,an,sdmx,file\n1,2,3,4\n"))
    assert result.failed == ["sm_df_pop"]
    pull_id = conn.execute("select pull_id from ingestion.raw_pulls").fetchone()[0]
    assert read_raw(conn, pull_id) == b"not,an,sdmx,file\n1,2,3,4\n"


def test_due_rules_and_inactive_sources(conn, pop_entry, recorded):
    now = datetime.now(UTC)
    runner.run(conn, [pop_entry], connectors={"sdmx": recorded()}, now=now)
    soon = runner.run(
        conn, [pop_entry], connectors={"sdmx": recorded()}, now=now + timedelta(hours=2)
    )
    assert soon.skipped == ["sm_df_pop"] and not soon.pulled
    later = runner.run(
        conn, [pop_entry], connectors={"sdmx": recorded()}, now=now + timedelta(hours=21)
    )
    assert len(later.pulled) == 1
    inactive = pop_entry.__class__.from_dict(pop_entry.definition | {"active": False})
    res = runner.run(conn, [inactive], connectors={"sdmx": recorded()}, now=now + timedelta(days=5))
    assert not res.pulled and not res.skipped
    assert conn.execute("select active from ingestion.sources").fetchone()[0] is False


def test_a_second_dataset_needs_only_a_registry_entry(conn, pop_entry, recorded):
    other = pop_entry.__class__.from_dict(
        pop_entry.definition | {"id": "sm_df_second", "title": "Second dataset"}
    )
    result = runner.run(conn, [pop_entry, other], connectors={"sdmx": recorded()})
    assert len(result.pulled) == 2 and all(o.changed for o in result.pulled)
    assert {e.source_id for e in events_since(conn)} == {"sm_df_pop", "sm_df_second"}
