"""Registry schema and rules (contract section 1)."""

from pathlib import Path

import pytest
import yaml
from ingestion.registry import RegistryError, find_registry, load

REGISTRY = find_registry()


def _write(tmp: Path, entries: dict[str, dict]) -> Path:
    (tmp / "sources").mkdir(parents=True)
    (tmp / "schema.json").write_text((REGISTRY / "schema.json").read_text(encoding="utf-8"))
    for name, data in entries.items():
        (tmp / "sources" / f"{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp


def _pop() -> dict:
    return yaml.safe_load((REGISTRY / "sources" / "sm_df_pop.yaml").read_text(encoding="utf-8"))


def test_every_registry_file_is_valid():
    entries = load()
    assert entries, "the registry must not be empty"
    assert len({e.id for e in entries}) == len(entries)


def test_df_pop_entry_matches_the_approved_spec(pop_entry):
    assert pop_entry.connector == "sdmx"
    assert pop_entry.address["base_url"] == "https://databrowser.govmu.org/ws/NSI_WS/rest/"
    assert (pop_entry.address["agency"], pop_entry.address["dataflow"]) == ("MU1", "DF_POP")
    assert pop_entry.licence == "free_with_credit"
    assert pop_entry.credit_line == "Source: Statistics Mauritius"
    assert pop_entry.access_rule == "by_tier"
    assert pop_entry.themes == ["people.population"]
    assert pop_entry.expected_release["months"] == [8]
    assert pop_entry.active is True


@pytest.mark.parametrize("field", ["licence", "credit_line", "access_rule", "themes", "checks"])
def test_a_required_field_missing_fails(tmp_path, field):
    data = _pop()
    del data[field]
    with pytest.raises(RegistryError, match=field):
        load(_write(tmp_path, {"sm_df_pop": data}))


def test_all_rights_reserved_must_be_free_to_all(tmp_path):
    data = _pop() | {"licence": "all_rights_reserved", "access_rule": "by_tier"}
    with pytest.raises(RegistryError, match="free_to_all"):
        load(_write(tmp_path, {"sm_df_pop": data}))
    data["access_rule"] = "free_to_all"
    assert load(_write(tmp_path / "ok", {"sm_df_pop": data}))[0].access_rule == "free_to_all"


def test_file_name_must_equal_id(tmp_path):
    with pytest.raises(RegistryError, match="file name"):
        load(_write(tmp_path, {"other_name": _pop()}))


def test_unknown_check_type_and_bad_address_fail(tmp_path):
    data = _pop()
    data["checks"] = [{"type": "made_up"}]
    data["address"] = {"base_url": "http://insecure.example/", "agency": "MU1"}
    with pytest.raises(RegistryError) as err:
        load(_write(tmp_path, {"sm_df_pop": data}))
    text = str(err.value)
    assert "checks" in text and "address" in text


def test_a_new_dataset_needs_only_a_registry_file(tmp_path):
    other = _pop() | {"id": "sm_df_other", "title": "Another dataflow"}
    other["address"] = other["address"] | {"dataflow": "DF_OTHER"}
    ids = {e.id for e in load(_write(tmp_path, {"sm_df_pop": _pop(), "sm_df_other": other}))}
    assert ids == {"sm_df_pop", "sm_df_other"}
