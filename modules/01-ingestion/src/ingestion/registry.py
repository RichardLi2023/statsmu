"""The source registry (contract section 1): one YAML file per dataset in registry/sources/."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

__all__ = ["RegistryError", "SourceEntry", "find_registry", "load", "validate_entry"]


class RegistryError(ValueError):
    """Raised when a registry file is invalid. The message names every problem."""


@dataclass(frozen=True)
class SourceEntry:
    id: str
    title: str
    publisher: str
    connector: str
    address: dict
    frequency: str
    check_every: str
    licence: str
    credit_line: str
    access_rule: str
    themes: list[str]
    checks: list[dict]
    active: bool
    expected_release: dict | None = None
    licence_note: str | None = None
    definition: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: dict) -> SourceEntry:
        names = cls.__dataclass_fields__.keys() - {"definition"}
        return cls(**{k: data.get(k) for k in names}, definition=dict(data))


def find_registry(start: Path | None = None) -> Path:
    """The registry folder: $INGESTION_REGISTRY_DIR, else registry/ in the repository root."""
    env = os.environ.get("INGESTION_REGISTRY_DIR")
    if env:
        return Path(env)
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        if (parent / "registry" / "schema.json").is_file():
            return parent / "registry"
    raise RegistryError("Cannot find registry/schema.json above " + str(here))


def _validator(registry: Path) -> Draft202012Validator:
    schema = json.loads((registry / "schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_entry(data: object, name: str, validator: Draft202012Validator) -> list[str]:
    problems = [
        f"{name}: {'/'.join(map(str, e.absolute_path)) or '(top)'}: {e.message}"
        for e in sorted(validator.iter_errors(data), key=lambda e: list(map(str, e.path)))
    ]
    if isinstance(data, dict) and data.get("id") != Path(name).stem:
        problems.append(
            f"{name}: id {data.get('id')!r} must equal the file name {Path(name).stem!r}"
        )
    return problems


def load(path: Path | str | None = None) -> list[SourceEntry]:
    """Read and validate every registry file. Raises RegistryError listing all problems."""
    registry = Path(path) if path else find_registry()
    validator = _validator(registry)
    entries, problems = [], []
    for file in sorted((registry / "sources").glob("*.y*ml")):
        try:
            data = yaml.safe_load(file.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            problems.append(f"{file.name}: not valid YAML: {exc}")
            continue
        found = validate_entry(data, file.name, validator)
        if found:
            problems.extend(found)
        else:
            entries.append(SourceEntry.from_dict(data))
    if problems:
        raise RegistryError("Invalid registry:\n" + "\n".join(problems))
    return entries
