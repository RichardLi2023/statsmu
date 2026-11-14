"""The shared logger: one JSON object per line, tagged with module and environment."""

from __future__ import annotations

import json
import logging as _stdlib
import sys
from datetime import UTC, datetime

from foundations.env import current_env

_RESERVED = set(vars(_stdlib.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}
_LEVELS = {
    _stdlib.DEBUG: "debug",
    _stdlib.INFO: "info",
    _stdlib.WARNING: "warning",
    _stdlib.ERROR: "error",
    _stdlib.CRITICAL: "critical",
}


class JsonFormatter(_stdlib.Formatter):
    """Format records as the contract's JSON log line."""

    def __init__(self, module: str, env: str) -> None:
        super().__init__()
        self.module = module
        self.env = env

    def format(self, record: _stdlib.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC)
        line: dict[str, object] = {
            "ts": ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z",
            "level": _LEVELS.get(record.levelno, record.levelname.lower()),
            "module": self.module,
            "env": self.env,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            line["error"] = f"{type(exc).__name__}: {exc}"
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in line and not key.startswith("_"):
                line[key] = value
        return json.dumps(line, default=str, ensure_ascii=False)


def get_logger(module: str, level: int = _stdlib.INFO) -> _stdlib.Logger:
    """Return the logger for a module, writing contract-format JSON lines to stdout."""
    if not module or not module.replace("-", "").replace("_", "").isalnum():
        raise ValueError("module must be the module slug, such as 'ingestion'")
    logger = _stdlib.getLogger(f"statsmu.{module}")
    if not getattr(logger, "_statsmu_configured", False):
        handler = _stdlib.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter(module, current_env()))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
        logger._statsmu_configured = True  # type: ignore[attr-defined]
    return logger
