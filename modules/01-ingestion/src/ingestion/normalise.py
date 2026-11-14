"""Normalisation, content checksums and the diff between two pulls (contract section 4)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from ingestion.connectors import StandardRow


def value_text(value: Decimal | None) -> str | None:
    """A plain decimal with no exponent and no trailing zeros, or None."""
    if value is None:
        return None
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def normalise(row: StandardRow) -> StandardRow:
    dims = {k.strip(): v.strip() for k, v in row.dimensions.items()}
    attrs = {k.strip(): v.strip() for k, v in row.attributes.items() if v is not None and v.strip()}
    value = Decimal(value_text(row.value)) if row.value is not None else None
    return StandardRow(row.dataset, dims, row.period.strip(), value, attrs)


RowKey = tuple[tuple[tuple[str, str], ...], str]


def key(row: StandardRow) -> RowKey:
    return tuple(sorted(row.dimensions.items())), row.period


def canonical_line(row: StandardRow) -> str:
    r = normalise(row)
    return json.dumps(
        {"d": r.dimensions, "p": r.period, "v": value_text(r.value), "a": r.attributes},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def content_checksum(rows: Iterable[StandardRow]) -> str:
    lines = sorted(canonical_line(r) for r in rows)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def text_checksum(text: str | None) -> str | None:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None


@dataclass(frozen=True)
class Diff:
    added: int
    removed: int
    revised: int
    periods_affected: list[str]


def diff(old: Iterable[StandardRow], new: Iterable[StandardRow]) -> Diff:
    before = {key(r): canonical_line(r) for r in old}
    after = {key(r): canonical_line(r) for r in new}
    added = after.keys() - before.keys()
    removed = before.keys() - after.keys()
    revised = {k for k in after.keys() & before.keys() if after[k] != before[k]}
    periods = sorted({k[1] for k in added | removed | revised})
    return Diff(len(added), len(removed), len(revised), periods)
