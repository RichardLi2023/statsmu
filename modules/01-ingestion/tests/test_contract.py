"""The public Python names of contract section 7, and the commands of section 6."""

import inspect

import pytest


def test_public_names_exist():
    import ingestion
    import ingestion.connectors as c
    import ingestion.registry as r

    for name in ("connect", "read_raw", "staged_rows", "events_since", "Event"):
        assert hasattr(ingestion, name), name
    for name in ("Connector", "Discovery", "RawArtefact", "Parsed", "StandardRow", "get_connector"):
        assert hasattr(c, name), name
    assert callable(r.load) and hasattr(r, "SourceEntry")


def test_signatures():
    import ingestion

    assert list(inspect.signature(ingestion.read_raw).parameters) == ["conn", "pull_id", "kind"]
    assert inspect.signature(ingestion.read_raw).parameters["kind"].default == "data"
    assert inspect.signature(ingestion.events_since).parameters["after_event_id"].default == 0
    assert list(inspect.signature(ingestion.staged_rows).parameters) == ["conn", "batch_id"]


def test_dataclass_fields():
    from ingestion import Event
    from ingestion.connectors import Discovery, Parsed, RawArtefact, StandardRow

    def fields(cls):
        return list(cls.__dataclass_fields__)

    assert fields(StandardRow) == ["dataset", "dimensions", "period", "value", "attributes"]
    assert fields(RawArtefact) == ["kind", "url", "http_status", "media_type", "content"]
    assert fields(Parsed) == ["rows", "labels", "structure_fingerprint"]
    assert fields(Discovery) == ["latest_period", "observation_count", "last_updated", "details"]
    assert fields(Event) == [
        "event_id",
        "event_type",
        "source_id",
        "pull_id",
        "previous_pull_id",
        "batch_id",
        "initial",
        "added",
        "removed",
        "revised",
        "periods_affected",
        "structure_changed",
        "checks_passed",
        "created_at",
    ]


def test_check_registry_command(capsys):
    from ingestion.__main__ import main

    assert main(["check-registry"]) == 0
    assert "sm_df_pop" in capsys.readouterr().out


def test_unknown_command_is_rejected():
    from ingestion.__main__ import main

    with pytest.raises(SystemExit):
        main(["nonsense"])


def test_connect_needs_db_url(monkeypatch):
    import ingestion
    from foundations.secrets import MissingSecretError

    monkeypatch.delenv("DB_URL", raising=False)
    with pytest.raises(MissingSecretError):
        ingestion.connect()
