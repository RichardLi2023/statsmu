"""Module 1 — source registry and ingestion.

Public contract (see ../../contract/contract.md, section 7):
    ingestion.connect, ingestion.read_raw, ingestion.staged_rows, ingestion.events_since,
    ingestion.Event, ingestion.registry.load, ingestion.registry.SourceEntry,
    ingestion.connectors.{Connector, Discovery, RawArtefact, Parsed, StandardRow, get_connector}
"""

from ingestion.db import connect
from ingestion.store import Event, events_since, read_raw, staged_rows

__all__ = ["Event", "connect", "events_since", "read_raw", "staged_rows"]
