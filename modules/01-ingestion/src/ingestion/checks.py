"""Validation checks named in the registry (contract section 5)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from decimal import Decimal

from ingestion.connectors import StandardRow
from ingestion.normalise import key


def run_checks(checks: list[dict], rows: list[StandardRow]) -> list[dict]:
    results = []
    for spec in checks:
        kind = spec["type"]
        fn = CHECKS.get(kind)
        if fn is None:
            results.append({"check": kind, "passed": False, "detail": "unknown check type"})
            continue
        passed, detail = fn(spec, rows)
        results.append({"check": kind, "passed": passed, "detail": detail})
    return results


def _min_rows(spec, rows):
    return len(rows) >= spec["value"], f"{len(rows)} rows (minimum {spec['value']})"


def _required_dimensions(spec, rows):
    need = set(spec["dimensions"])
    missing = sum(1 for r in rows if not need <= r.dimensions.keys())
    return missing == 0, f"{missing} rows lack one of {sorted(need)}"


def _unique_key(spec, rows):
    dupes = [k for k, n in Counter(key(r) for r in rows).items() if n > 1]
    return not dupes, f"{len(dupes)} duplicate keys" + (f", e.g. {dupes[0]}" if dupes else "")


def _numeric_values(spec, rows):
    bad = sum(1 for r in rows if r.value is not None and not isinstance(r.value, Decimal))
    return bad == 0, f"{bad} non-numeric values"


_PERIOD = {
    "annual": re.compile(r"^(\d{4})$"),
    "quarterly": re.compile(r"^(\d{4})-Q([1-4])$"),
    "monthly": re.compile(r"^(\d{4})-(\d{2})$"),
}


def _ordinal(period: str) -> tuple[str, int] | None:
    if m := _PERIOD["annual"].match(period):
        return "annual", int(m.group(1))
    if m := _PERIOD["quarterly"].match(period):
        return "quarterly", int(m.group(1)) * 4 + int(m.group(2)) - 1
    if m := _PERIOD["monthly"].match(period):
        return "monthly", int(m.group(1)) * 12 + int(m.group(2)) - 1
    return None


def _periods_complete(spec, rows):
    start = _ordinal(str(spec["from"]))
    if start is None:
        return False, f"cannot read period {spec['from']!r}"
    kind = start[0]
    present = {o[1] for r in rows if (o := _ordinal(r.period)) and o[0] == kind}
    if not present:
        return False, "no periods of that frequency"
    wanted = set(range(start[1], max(present) + 1))
    missing = sorted(wanted - present)
    return not missing, f"{len(missing)} missing periods" + (
        f" (first: {missing[0]})" if missing else ""
    )


def _sum_equals(spec, rows):
    dim, total = spec["dimension"], spec["total"]
    tol = Decimal(str(spec.get("tolerance", 0)))
    totals: dict = {}
    parts: dict = defaultdict(Decimal)
    counts: dict = defaultdict(int)
    for r in rows:
        if dim not in r.dimensions or r.value is None:
            continue
        others = tuple(sorted((k, v) for k, v in r.dimensions.items() if k != dim)), r.period
        if r.dimensions[dim] == total:
            totals[others] = r.value
        else:
            parts[others] += r.value
            counts[others] += 1
    groups = [g for g in totals if counts.get(g)]
    bad = [g for g in groups if abs(totals[g] - parts[g]) > tol]
    detail = f"{len(groups)} groups checked, {len(bad)} differ"
    if bad:
        g = bad[0]
        detail += f"; e.g. {dict(g[0])} {g[1]}: total {totals[g]}, sum {parts[g]}"
    return not bad, detail


CHECKS = {
    "min_rows": _min_rows,
    "required_dimensions": _required_dimensions,
    "unique_key": _unique_key,
    "numeric_values": _numeric_values,
    "periods_complete": _periods_complete,
    "sum_equals": _sum_equals,
}
