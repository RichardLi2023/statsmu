"""Post-deployment smoke test: GET <base>/health and check it matches the contract.

Usage: python scripts/smoke_test.py <base url> <expected env> [expected version]
Retries for up to about a minute while a new deployment warms up.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request


def check(payload: dict, env: str, version: str | None) -> list[str]:
    problems = []
    if payload.get("status") != "ok":
        problems.append(f"status is {payload.get('status')!r}, expected 'ok'")
    if payload.get("env") != env:
        problems.append(f"env is {payload.get('env')!r}, expected {env!r}")
    if version and payload.get("version") != version:
        problems.append(f"version is {payload.get('version')!r}, expected {version!r}")
    for key in ("version", "commit"):
        if key not in payload:
            problems.append(f"missing field {key!r}")
    return problems


def fetch(url: str) -> dict:
    if not url.startswith("https://") and not url.startswith("http://localhost"):
        raise ValueError("Smoke test only calls https:// addresses (or http://localhost)")
    req = urllib.request.Request(url, headers={"User-Agent": "statsmu-smoke-test"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    url = argv[1].rstrip("/") + "/health"
    env, version = argv[2], (argv[3] if len(argv) == 4 else None)
    last = "no response"
    for attempt in range(6):
        try:
            problems = check(fetch(url), env, version)
            if not problems:
                print(f"Smoke test passed: {url}")
                return 0
            last = "; ".join(problems)
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(10 * (attempt + 1) if attempt < 5 else 0)
    print(f"::error::Smoke test failed for {url}: {last}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
