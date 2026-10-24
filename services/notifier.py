"""Push notifications via Home Assistant's notify service (Signal).

Disabled until HA_URL, HA_TOKEN and HA_NOTIFY_SERVICE are all set to real
values. notify() never raises: a notification problem must not fail the task
that triggered it.
"""
import json
import logging
import urllib.request

from core.config import get_settings

logger = logging.getLogger(__name__)

_MAX_LEN = 500


def _configured(value: str) -> bool:
    return bool(value) and not value.lower().startswith("change")


def notify(message: str) -> bool:
    """Send `message`; True if HA accepted it. Keep messages free of PII."""
    s = get_settings()
    if not (_configured(s.ha_url) and _configured(s.ha_token) and _configured(s.ha_notify_service)):
        logger.info("Notifications not configured; dropped: %s", message[:80])
        return False

    url = f"{s.ha_url.rstrip('/')}/api/services/notify/{s.ha_notify_service}"
    req = urllib.request.Request(
        url,
        data=json.dumps({"message": message[:_MAX_LEN]}).encode(),
        headers={"Authorization": f"Bearer {s.ha_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001 - must never propagate
        logger.warning("Notification failed: %s", type(exc).__name__)
        return False
