"""The SDMX connector (contract section 2): SDMX-CSV 1.0 for data, SDMX-JSON for structure."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

import httpx

from ingestion import http
from ingestion.connectors import Discovery, Parsed, RawArtefact, StandardRow

if TYPE_CHECKING:
    from ingestion.registry import SourceEntry

STRUCTURE_JSON = "application/vnd.sdmx.structure+json;version=1.0"
DATA_CSV = "application/vnd.sdmx.data+csv;version=1.0.0"
_CODELIST_URN = re.compile(r"Codelist=([^:]+):([^(]+)\(")


class SdmxFormatError(ValueError):
    """Raised when a response does not have the expected SDMX shape."""


def _flow(entry: SourceEntry) -> tuple[str, str, str, str, str]:
    a = entry.address
    return a["base_url"], a["agency"], a["dataflow"], a["version"], a.get("key", "all")


def urls(entry: SourceEntry) -> dict[str, str]:
    base, agency, flow, version, key = _flow(entry)
    return {
        "availability": f"{base}availableconstraint/{agency},{flow},{version}/all/all/all",
        "dataflow": f"{base}dataflow/{agency}/{flow}/{version}",
        "data": f"{base}data/{agency},{flow},{version}/{key}/ALL/"
        "?dimensionAtObservation=AllDimensions",
        "structure": f"{base}dataflow/{agency}/{flow}/{version}/"
        "?detail=Full&references=Descendants",
    }


class SdmxConnector:
    type = "sdmx"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client

    # discover ---------------------------------------------------------------------------
    def discover(self, entry: SourceEntry) -> Discovery:
        u = urls(entry)
        availability = http.get(u["availability"], STRUCTURE_JSON, self.client).json()
        dataflow = http.get(u["dataflow"], STRUCTURE_JSON, self.client).json()
        return discovery_from(availability, dataflow)

    # fetch ------------------------------------------------------------------------------
    def fetch(self, entry: SourceEntry) -> list[RawArtefact]:
        u = urls(entry)
        out = []
        for kind, accept in (("data", DATA_CSV), ("structure", STRUCTURE_JSON)):
            r = http.get(u[kind], accept, self.client)
            media = r.headers.get("content-type", accept).split(";")[0].strip()
            out.append(RawArtefact(kind, u[kind], r.status_code, media, r.content))
        return out

    # parse ------------------------------------------------------------------------------
    def parse(self, entry: SourceEntry, artefacts: list[RawArtefact]) -> Parsed:
        by_kind = {a.kind: a for a in artefacts}
        if "data" not in by_kind:
            raise SdmxFormatError("No data file to parse")
        rows, used = parse_csv(entry.id, by_kind["data"].content)
        labels: dict[str, dict[str, str]] = {}
        fingerprint = None
        if "structure" in by_kind:
            structure = json.loads(by_kind["structure"].content)
            components, all_labels = read_structure(structure)
            labels = {
                concept: {
                    c: all_labels[concept][c]
                    for c in sorted(codes)
                    if c in all_labels.get(concept, {})
                }
                for concept, codes in sorted(used.items())
            }
            labels = {k: v for k, v in labels.items() if v}
            fingerprint = json.dumps(
                {"components": components, "labels": labels}, sort_keys=True, ensure_ascii=False
            )
        return Parsed(rows=rows, labels=labels, structure_fingerprint=fingerprint)


def discovery_from(availability: dict, dataflow: dict) -> Discovery:
    count = None
    latest = None
    details: dict = {}
    try:
        constraint = availability["data"]["contentConstraints"][0]
        for ann in constraint.get("annotations", []):
            if ann.get("id") == "obs_count":
                count = int(ann["title"])
        for region in constraint.get("cubeRegions", []):
            for kv in region.get("keyValues", []):
                if "timeRange" in kv:
                    tr = kv["timeRange"]
                    details["time_range"] = {
                        "start": tr.get("startPeriod", {}).get("period"),
                        "end": tr.get("endPeriod", {}).get("period"),
                    }
                    end = details["time_range"]["end"]
                    latest = end[:10] if end else None
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise SdmxFormatError(f"Unexpected availability response: {exc}") from exc
    last_updated = None
    try:
        flows = dataflow["data"]["dataflows"]
        for ann in flows[0].get("annotations", []):
            if ann.get("id") == "LAST_UPDATE" or ann.get("type") == "LAST_UPDATE":
                last_updated = datetime.fromisoformat(ann["title"].replace("Z", "+00:00"))
        details["dataflow_version"] = flows[0].get("version")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise SdmxFormatError(f"Unexpected dataflow response: {exc}") from exc
    return Discovery(latest, count, last_updated, details)


def parse_csv(dataset: str, content: bytes) -> tuple[list[StandardRow], dict[str, set[str]]]:
    """Read SDMX-CSV 1.0. Returns rows and, per concept, the codes used."""
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = [h.strip() for h in next(reader)]
    except StopIteration as exc:
        raise SdmxFormatError("Empty data file") from exc
    for required in ("DATAFLOW", "TIME_PERIOD", "OBS_VALUE"):
        if required not in header:
            raise SdmxFormatError(f"Data file has no {required} column")
    i_flow, i_time, i_value = (header.index(c) for c in ("DATAFLOW", "TIME_PERIOD", "OBS_VALUE"))
    dims = [(i, header[i]) for i in range(i_flow + 1, i_time)]
    attrs = [(i, header[i]) for i in range(len(header)) if i not in (i_flow, i_time, i_value)]
    attrs = [(i, n) for i, n in attrs if (i, n) not in dims]
    used: dict[str, set[str]] = {}
    rows = []
    for line_no, rec in enumerate(reader, start=2):
        if not rec or all(not c.strip() for c in rec):
            continue
        if len(rec) != len(header):
            raise SdmxFormatError(f"Line {line_no} has {len(rec)} fields, expected {len(header)}")
        d = {n: rec[i].strip() for i, n in dims}
        a = {n: rec[i].strip() for i, n in attrs if rec[i].strip()}
        raw = rec[i_value].strip()
        try:
            value = Decimal(raw) if raw else None
        except InvalidOperation as exc:
            raise SdmxFormatError(f"Line {line_no}: value {raw!r} is not a number") from exc
        for k, v in (*d.items(), *a.items()):
            used.setdefault(k, set()).add(v)
        rows.append(StandardRow(dataset, d, rec[i_time].strip(), value, a))
    return rows, used


def read_structure(structure: dict) -> tuple[dict, dict[str, dict[str, str]]]:
    """Return the data structure's components and, per component, code -> label."""
    try:
        data = structure["data"]
        codelists = {
            (cl.get("agencyID"), cl["id"]): {c["id"]: _name(c) for c in cl.get("codes", [])}
            for cl in data.get("codelists", [])
        }
        dsd = data["dataStructures"][0]["dataStructureComponents"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SdmxFormatError(f"Unexpected structure response: {exc}") from exc
    dims = dsd.get("dimensionList", {}).get("dimensions", [])
    time_dims = dsd.get("dimensionList", {}).get("timeDimensions", [])
    attrs = dsd.get("attributeList", {}).get("attributes", [])
    components = {
        "dimensions": [d["id"] for d in dims],
        "time": [t["id"] for t in time_dims],
        "attributes": [a["id"] for a in attrs],
    }
    labels: dict[str, dict[str, str]] = {}
    for comp in (*dims, *attrs):
        urn = comp.get("localRepresentation", {}).get("enumeration", "")
        m = _CODELIST_URN.search(urn or "")
        if m and (m.group(1), m.group(2)) in codelists:
            labels[comp["id"]] = codelists[(m.group(1), m.group(2))]
        else:
            match = [v for (_, cid), v in codelists.items() if cid == f"CL_{comp['id']}"]
            if match:
                labels[comp["id"]] = match[0]
    return components, labels


def _name(code: dict) -> str:
    name = code.get("name")
    if isinstance(name, str) and name:
        return name.strip()
    names = code.get("names") or {}
    return (names.get("en") or next(iter(names.values()), "") or code["id"]).strip()
