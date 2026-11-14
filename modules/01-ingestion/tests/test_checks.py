"""Validation checks (contract section 5)."""

from decimal import Decimal

from ingestion.checks import run_checks
from ingestion.connectors import StandardRow


def r(period, value, sex="_T", age="_T"):
    return StandardRow("ds", {"SEX": sex, "AGE": age}, period, Decimal(value), {})


def by_name(results):
    return {(x["check"]): x for x in results}


def test_df_pop_passes_all_its_checks(pop_entry, recorded):
    c = recorded()
    rows = c.parse(pop_entry, c.fetch(pop_entry)).rows
    results = run_checks(pop_entry.checks, rows)
    assert results and all(x["passed"] for x in results), results


def test_sum_equals():
    rows = [r("2025", "10", "_T"), r("2025", "4", "M"), r("2025", "6", "F")]
    spec = [{"type": "sum_equals", "dimension": "SEX", "total": "_T"}]
    assert run_checks(spec, rows)[0]["passed"]
    rows[1] = r("2025", "5", "M")
    res = run_checks(spec, rows)[0]
    assert not res["passed"] and "total 10, sum 11" in res["detail"]
    assert run_checks([spec[0] | {"tolerance": 1}], rows)[0]["passed"]


def test_sum_equals_ignores_totals_without_parts():
    spec = [{"type": "sum_equals", "dimension": "SEX", "total": "_T"}]
    assert run_checks(spec, [r("2025", "10")])[0]["passed"]


def test_periods_complete():
    spec = [{"type": "periods_complete", "from": "2020"}]
    assert run_checks(spec, [r(str(y), "1") for y in range(2020, 2026)])[0]["passed"]
    res = run_checks(spec, [r(y, "1") for y in ("2020", "2021", "2023")])[0]
    assert not res["passed"] and "first: 2022" in res["detail"]
    q = [{"type": "periods_complete", "from": "2024-Q3"}]
    assert run_checks(q, [r(p, "1") for p in ("2024-Q3", "2024-Q4", "2025-Q1")])[0]["passed"]
    m = [{"type": "periods_complete", "from": "2025-11"}]
    assert not run_checks(m, [r(p, "1") for p in ("2025-11", "2026-01")])[0]["passed"]


def test_min_rows_unique_key_required_dimensions_numeric():
    rows = [r("2025", "1"), r("2025", "2")]
    res = by_name(
        run_checks(
            [
                {"type": "min_rows", "value": 3},
                {"type": "unique_key"},
                {"type": "required_dimensions", "dimensions": ["SEX", "AREA"]},
                {"type": "numeric_values"},
            ],
            rows,
        )
    )
    assert not res["min_rows"]["passed"]
    assert not res["unique_key"]["passed"]
    assert not res["required_dimensions"]["passed"]
    assert res["numeric_values"]["passed"]


def test_unknown_check_fails_safely():
    assert run_checks([{"type": "nope"}], [])[0] == {
        "check": "nope",
        "passed": False,
        "detail": "unknown check type",
    }
