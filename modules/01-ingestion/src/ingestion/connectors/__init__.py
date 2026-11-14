"""The connector contract (contract section 2) and the registry of connector types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ingestion.registry import SourceEntry

__all__ = [
    "Connector",
    "Discovery",
    "Parsed",
    "RawArtefact",
    "StandardRow",
    "get_connector",
]


@dataclass(frozen=True)
class Discovery:
    latest_period: str | None = None
    observation_count: int | None = None
    last_updated: datetime | None = None
    details: dict = field(default_factory=dict)

    def as_json(self) -> dict:
        return {
            "latest_period": self.latest_period,
            "observation_count": self.observation_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "details": self.details,
        }


@dataclass(frozen=True)
class RawArtefact:
    kind: str
    url: str
    http_status: int
    media_type: str
    content: bytes


@dataclass(frozen=True)
class StandardRow:
    dataset: str
    dimensions: dict[str, str]
    period: str
    value: Decimal | None
    attributes: dict[str, str]


@dataclass(frozen=True)
class Parsed:
    rows: list[StandardRow]
    labels: dict[str, dict[str, str]] = field(default_factory=dict)
    structure_fingerprint: str | None = None


@runtime_checkable
class Connector(Protocol):
    type: str

    def discover(self, entry: SourceEntry) -> Discovery: ...
    def fetch(self, entry: SourceEntry) -> list[RawArtefact]: ...
    def parse(self, entry: SourceEntry, artefacts: list[RawArtefact]) -> Parsed: ...


class UnknownConnectorError(ValueError):
    """Raised for a registry `connector` value with no connector."""


def get_connector(type: str) -> Connector:  # noqa: A002 - contract name
    """Return the connector for a registry `connector` value."""
    if type == "sdmx":
        from ingestion.connectors.sdmx import SdmxConnector

        return SdmxConnector()
    raise UnknownConnectorError(f"No connector for type {type!r}")
