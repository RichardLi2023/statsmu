"""SDMX connector on the recorded DF_POP files (contract section 2)."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from ingestion.connectors import Connector, Discovery, Parsed, StandardRow, get_connector
from ingestion.connectors.sdmx import SdmxConnector, SdmxFormatError, parse_csv, urls

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_get_connector_returns_the_sdmx_connector():
    c = get_connector("sdmx")
    assert isinstance(c, Connector) and c.type == "sdmx"
    with pytest.raises(ValueError):
        get_connector("ftp")


def test_urls_follow_the_contract(pop_entry):
    u = urls(pop_entry)
    base = "https://databrowser.govmu.org/ws/NSI_WS/rest/"
    assert u["availability"] == base + "availableconstraint/MU1,DF_POP,1.0/all/all/all"
    assert u["dataflow"] == base + "dataflow/MU1/DF_POP/1.0"
    assert u["data"] == base + "data/MU1,DF_POP,1.0/all/ALL/?dimensionAtObservation=AllDimensions"
    assert u["structure"] == base + "dataflow/MU1/DF_POP/1.0/?detail=Full&references=Descendants"


def test_parse_df_pop(pop_entry, recorded):
    c = recorded()
    parsed = c.parse(pop_entry, c.fetch(pop_entry))
    assert isinstance(parsed, Parsed)
    rows = parsed.rows
    assert len(rows) == 1159
    assert all(isinstance(r, StandardRow) for r in rows)
    first = next(r for r in rows if r.dimensions["INDIC_POP"] == "POP_EOY" and r.period == "2007")
    assert first.dataset == "sm_df_pop"
    assert first.dimensions == {
        "FREQ": "A",
        "REF_AREA": "MU",
        "INDIC_POP": "POP_EOY",
        "SEX": "_T",
        "AGE": "_T",
    }
    assert first.value == Decimal("1242165")
    assert first.attributes["OBS_STATUS"] == "E"
    assert "NOTE_REF_AREA" not in first.attributes  # empty values are left out
    assert {r.dimensions["REF_AREA"] for r in rows} == {"MU"}
    assert sorted({r.period for r in rows}) == [str(y) for y in range(2007, 2026)]
    ages = {r.dimensions["AGE"] for r in rows}
    assert len(ages) == 20 and {"Y0", "Y1T4", "Y80T84", "Y_GE85", "_T"} <= ages


def test_labels_and_structure_fingerprint(pop_entry, recorded):
    c = recorded()
    parsed = c.parse(pop_entry, c.fetch(pop_entry))
    assert parsed.labels["AGE"]["Y_GE85"] == "85 years old and over"
    assert parsed.labels["SEX"] == {"F": "Female", "M": "Male", "_T": "Both Sexes"}
    assert "IOR" not in parsed.labels["REF_AREA"]  # only codes the data uses
    assert parsed.structure_fingerprint and "LAST_UPDATE" not in parsed.structure_fingerprint


def test_structure_header_changes_do_not_change_the_fingerprint(pop_entry, recorded):
    s = fixture_bytes("df_pop_structure.json").replace(b'"prepared":"', b'"prepared":"1999')
    a = recorded().parse(pop_entry, recorded().fetch(pop_entry)).structure_fingerprint
    b = recorded(structure=s).parse(pop_entry, recorded(structure=s).fetch(pop_entry))
    assert a == b.structure_fingerprint


def test_discovery_from_recorded_files(pop_entry, recorded):
    d = recorded().discover(pop_entry)
    assert isinstance(d, Discovery)
    assert d.observation_count == 1159
    assert d.latest_period.startswith("2025")
    assert d.last_updated == datetime(2026, 8, 7, 9, 11, 7, 763000, tzinfo=UTC)


def test_bad_csv_is_rejected():
    with pytest.raises(SdmxFormatError):
        parse_csv("x", b"")
    with pytest.raises(SdmxFormatError, match="OBS_VALUE"):
        parse_csv("x", b"DATAFLOW,FREQ,TIME_PERIOD\nA:B(1.0),A,2020\n")
    with pytest.raises(SdmxFormatError, match="not a number"):
        parse_csv("x", b"DATAFLOW,FREQ,TIME_PERIOD,OBS_VALUE\nA:B(1.0),A,2020,abc\n")


def test_fetch_and_discover_over_http(pop_entry):
    files = {
        "availableconstraint": ("df_pop_availability.json", "application/vnd.sdmx.structure+json"),
        "detail=Full": ("df_pop_structure.json", "application/vnd.sdmx.structure+json"),
        "/data/": ("df_pop_data.csv", "application/vnd.sdmx.data+csv; charset=utf-8"),
        "/dataflow/": ("df_pop_dataflow.json", "application/vnd.sdmx.structure+json"),
    }
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        for marker, (name, media) in files.items():
            if marker in str(request.url):
                return httpx.Response(
                    200, content=fixture_bytes(name), headers={"content-type": media}
                )
        return httpx.Response(404)

    c = SdmxConnector(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert c.discover(pop_entry).observation_count == 1159
    artefacts = c.fetch(pop_entry)
    assert [a.kind for a in artefacts] == ["data", "structure"]
    assert artefacts[0].media_type == "application/vnd.sdmx.data+csv"
    assert artefacts[0].content == fixture_bytes("df_pop_data.csv")
    assert all(r.headers["user-agent"].startswith("statsmu-ingestion/") for r in seen)
    assert "csv" in seen[2].headers["accept"]


def test_http_retries_then_fails(pop_entry, monkeypatch):
    from ingestion import http

    monkeypatch.setattr(http, "BACKOFF_SECONDS", (0, 0))
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(http.FetchError, match="3 attempts"):
        http.get("https://example.test/x", "text/csv", client)
    assert len(calls) == 3
    with pytest.raises(http.FetchError, match="404"):
        http.get(
            "https://example.test/y",
            "text/csv",
            httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))),
        )
