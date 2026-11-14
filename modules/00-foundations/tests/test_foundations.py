import io
import json
import logging

import pytest
from foundations import env, secrets
from foundations import logging as flog
from foundations.health import health


def test_env_defaults_to_dev(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert env.current_env() == "dev"


@pytest.mark.parametrize("value", ["dev", "staging", "live", " LIVE "])
def test_env_accepts_contract_names(monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)
    assert env.current_env() == value.strip().lower()


def test_env_rejects_other_names(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(env.InvalidEnvironmentError):
        env.current_env()


@pytest.mark.parametrize("name", ["SOURCE_BOM_TOKEN", "DB_URL", "SENTRY_DSN", "VERCEL_PROJECT_ID"])
def test_secret_names_valid(name):
    assert secrets.validate_name(name) == name


@pytest.mark.parametrize("name", ["bom_token", "TOKEN", "OTHER_KEY", "DB_", "DB-URL", "SOURCE_bom"])
def test_secret_names_invalid(name):
    with pytest.raises(secrets.SecretNameError):
        secrets.validate_name(name)


def test_get_secret(monkeypatch):
    monkeypatch.setenv("SOURCE_TEST_TOKEN", "abc")
    assert secrets.get_secret("SOURCE_TEST_TOKEN") == "abc"
    monkeypatch.delenv("SOURCE_TEST_TOKEN")
    assert secrets.get_secret("SOURCE_TEST_TOKEN", required=False) is None
    with pytest.raises(secrets.MissingSecretError):
        secrets.get_secret("SOURCE_TEST_TOKEN")


def _capture(module, monkeypatch, envname="staging"):
    monkeypatch.setenv("APP_ENV", envname)
    logger = logging.getLogger(f"statsmu.{module}")
    logger.handlers.clear()
    if hasattr(logger, "_statsmu_configured"):
        del logger._statsmu_configured
    log = flog.get_logger(module)
    buf = io.StringIO()
    log.handlers[0].stream = buf
    return log, buf


def test_log_line_matches_contract(monkeypatch):
    log, buf = _capture("ingestion", monkeypatch)
    log.info("pulled", extra={"dataset": "DF_POP", "rows": 1159})
    line = json.loads(buf.getvalue())
    assert line["level"] == "info"
    assert line["module"] == "ingestion"
    assert line["env"] == "staging"
    assert line["msg"] == "pulled"
    assert line["dataset"] == "DF_POP" and line["rows"] == 1159
    assert line["ts"].endswith("Z") and len(line["ts"]) == 24


def test_log_line_includes_error(monkeypatch):
    log, buf = _capture("ingestion2", monkeypatch)
    try:
        raise ValueError("bad value")
    except ValueError:
        log.exception("failed")
    line = json.loads(buf.getvalue())
    assert line["level"] == "error"
    assert line["error"] == "ValueError: bad value"


def test_logger_not_duplicated(monkeypatch):
    log, _ = _capture("dup", monkeypatch)
    assert flog.get_logger("dup") is log
    assert len(log.handlers) == 1


def test_logger_rejects_bad_slug():
    with pytest.raises(ValueError):
        flog.get_logger("bad slug!")


def test_error_tracking_off_without_dsn(monkeypatch):
    from foundations.errors import init_error_tracking

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_error_tracking("foundations") is False


def test_health(monkeypatch):
    monkeypatch.setenv("APP_ENV", "live")
    monkeypatch.setenv("APP_VERSION", "foundations-v1.0")
    monkeypatch.setenv("APP_COMMIT", "abcdef1234")
    assert health() == {
        "status": "ok",
        "env": "live",
        "version": "foundations-v1.0",
        "commit": "abcdef1",
    }
