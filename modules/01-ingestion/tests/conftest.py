"""Shared fixtures: recorded DF_POP files, a fake connector and a temporary PostgreSQL."""

from __future__ import annotations

import glob
import os
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from ingestion.connectors import RawArtefact
from ingestion.connectors.sdmx import SdmxConnector, urls
from ingestion.registry import SourceEntry, load

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture(scope="session")
def registry_entries() -> list[SourceEntry]:
    return load()


@pytest.fixture
def pop_entry(registry_entries) -> SourceEntry:
    return next(e for e in registry_entries if e.id == "sm_df_pop")


class RecordedConnector(SdmxConnector):
    """The real SDMX parser over recorded files; `data` can be swapped to simulate changes."""

    def __init__(
        self, data: bytes | None = None, structure: bytes | None = None, fail: bool = False
    ):
        super().__init__()
        self.data = data if data is not None else fixture_bytes("df_pop_data.csv")
        self.structure = (
            structure if structure is not None else fixture_bytes("df_pop_structure.json")
        )
        self.fail = fail

    def discover(self, entry):
        import json

        from ingestion.connectors.sdmx import discovery_from

        return discovery_from(
            json.loads(fixture_bytes("df_pop_availability.json")),
            json.loads(fixture_bytes("df_pop_dataflow.json")),
        )

    def fetch(self, entry):
        if self.fail:
            raise RuntimeError("simulated: publisher unreachable")
        u = urls(entry)
        return [
            RawArtefact("data", u["data"], 200, "application/vnd.sdmx.data+csv", self.data),
            RawArtefact(
                "structure",
                u["structure"],
                200,
                "application/vnd.sdmx.structure+json",
                self.structure,
            ),
        ]


@pytest.fixture
def recorded():
    return RecordedConnector


# --- temporary PostgreSQL ---------------------------------------------------------------------
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pg_bin() -> Path | None:
    found = shutil.which("initdb")
    if found:
        return Path(found).parent
    candidates = sorted(glob.glob("/usr/lib/postgresql/*/bin/initdb"))
    return Path(candidates[-1]).parent if candidates else None


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    bindir = _pg_bin()
    reason = None
    if bindir is None:
        reason = "PostgreSQL is not installed (set TEST_DATABASE_URL to use another server)"
    elif hasattr(os, "geteuid") and os.geteuid() == 0:
        reason = "initdb cannot run as root (set TEST_DATABASE_URL to use another server)"
    if reason:
        if os.environ.get("CI"):
            pytest.fail(reason)
        pytest.skip(reason)
    tmp = Path(tempfile.mkdtemp(prefix="ingestion-pg-"))
    data, sock, port = tmp / "data", tmp / "sock", _free_port()
    sock.mkdir()
    subprocess.run(
        [bindir / "initdb", "-D", data, "-U", "postgres", "-A", "trust", "--no-sync"],
        check=True,
        capture_output=True,
    )
    opts = f"-p {port} -k {sock} -c listen_addresses='' -c fsync=off"
    subprocess.run(
        [bindir / "pg_ctl", "-D", data, "-o", opts, "-w", "-l", tmp / "log", "start"],
        check=True,
        capture_output=True,
    )
    try:
        yield f"postgresql://postgres@/postgres?host={sock}&port={port}"
    finally:
        subprocess.run(
            [bindir / "pg_ctl", "-D", data, "-m", "immediate", "stop"], capture_output=True
        )
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def conn(database_url):
    import psycopg
    from ingestion import store

    with psycopg.connect(database_url, prepare_threshold=None) as c:
        c.execute("drop schema if exists ingestion cascade")
        c.commit()
        store.migrate(c)
        yield c
