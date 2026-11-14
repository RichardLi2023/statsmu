"""Normalisation, content checksums and the diff (contract section 4)."""

import random
from decimal import Decimal

from ingestion.connectors import StandardRow
from ingestion.normalise import canonical_line, content_checksum, diff, normalise, value_text


def row(period="2025", value="100", sex="_T", **attrs):
    v = Decimal(value) if value is not None else None
    return StandardRow("ds", {"SEX": sex, "AGE": "_T"}, period, v, attrs or {"OBS_STATUS": "E"})


def test_value_text_is_plain_and_trimmed():
    assert value_text(Decimal("1242165")) == "1242165"
    assert value_text(Decimal("1242165.00")) == "1242165"
    assert value_text(Decimal("1.2E+3")) == "1200"
    assert value_text(Decimal("0.50")) == "0.5"
    assert value_text(Decimal("-0.0")) == "0"
    assert value_text(None) is None


def test_normalise_trims_and_drops_empty_attributes():
    r = normalise(
        StandardRow("ds", {" SEX ": " M "}, " 2025 ", Decimal("5.0"), {"A": " ", "B": "x"})
    )
    assert r.dimensions == {"SEX": "M"} and r.period == "2025"
    assert r.value == Decimal("5") and r.attributes == {"B": "x"}


def test_same_content_same_checksum_whatever_the_order():
    rows = [row(str(y), str(y * 10), sex) for y in range(2007, 2026) for sex in ("_T", "M", "F")]
    shuffled = rows[:]
    random.Random(1).shuffle(shuffled)
    assert content_checksum(rows) == content_checksum(shuffled)
    assert content_checksum(rows) == content_checksum(
        [row(r.period, f"{r.value}.00", r.dimensions["SEX"]) for r in rows]
    )


def test_any_change_changes_the_checksum():
    base = [row("2024", "100"), row("2025", "200")]
    c = content_checksum(base)
    assert content_checksum([row("2024", "100"), row("2025", "201")]) != c
    assert content_checksum([row("2024", "100"), row("2025", "200", OBS_STATUS="P")]) != c
    assert content_checksum(base[:1]) != c
    assert content_checksum([*base, row("2026", "300")]) != c


def test_diff_counts():
    old = [row("2023", "1"), row("2024", "2"), row("2025", "3")]
    new = [row("2024", "2"), row("2025", "4"), row("2026", "5")]
    d = diff(old, new)
    assert (d.added, d.removed, d.revised) == (1, 1, 1)
    assert d.periods_affected == ["2023", "2025", "2026"]


def test_diff_attribute_change_is_a_revision_and_identical_is_empty():
    old = [row("2025", "3")]
    assert diff(old, [row("2025", "3", OBS_STATUS="P")]).revised == 1
    same = diff(old, [row("2025", "3.0")])
    assert (same.added, same.removed, same.revised, same.periods_affected) == (0, 0, 0, [])


def test_canonical_line_is_stable():
    assert (
        canonical_line(row())
        == '{"a":{"OBS_STATUS":"E"},"d":{"AGE":"_T","SEX":"_T"},"p":"2025","v":"100"}'
    )
