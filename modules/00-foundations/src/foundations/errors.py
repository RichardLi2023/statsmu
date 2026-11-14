"""Error tracking with Sentry, tagged by module and environment."""

from __future__ import annotations

from foundations.env import current_env, release_version
from foundations.secrets import get_secret


def init_error_tracking(module: str) -> bool:
    """Start Sentry if SENTRY_DSN is set. Returns True when tracking is on."""
    dsn = get_secret("SENTRY_DSN", required=False)
    if not dsn:
        return False
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=current_env(),
        release=release_version(),
        send_default_pii=False,
        traces_sample_rate=0.0,
        integrations=[LoggingIntegration(event_level=40)],  # error-level logs become events
    )
    sentry_sdk.set_tag("module", module)
    return True
