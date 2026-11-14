"""HTTP requests with a timeout, retries and the module's User-Agent (contract section 2)."""

from __future__ import annotations

import time

import httpx

from ingestion.version import code_version

TIMEOUT_SECONDS = 60
ATTEMPTS = 3
BACKOFF_SECONDS = (2, 8)


class FetchError(RuntimeError):
    """Raised when a request still fails after every attempt."""


def get(url: str, accept: str, client: httpx.Client | None = None) -> httpx.Response:
    headers = {"Accept": accept, "User-Agent": f"statsmu-ingestion/{code_version()}"}
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True)
    last: Exception | None = None
    try:
        for attempt in range(ATTEMPTS):
            try:
                response = client.get(url, headers=headers)
                if response.status_code < 500:
                    response.raise_for_status()
                    return response
                last = FetchError(f"HTTP {response.status_code} from {url}")
            except httpx.HTTPStatusError as exc:  # 4xx: retrying will not help
                raise FetchError(f"HTTP {exc.response.status_code} from {url}") from exc
            except httpx.TransportError as exc:
                last = exc
            if attempt < ATTEMPTS - 1:
                time.sleep(BACKOFF_SECONDS[attempt])
        raise FetchError(f"{url} failed after {ATTEMPTS} attempts: {last}") from last
    finally:
        if own:
            client.close()
