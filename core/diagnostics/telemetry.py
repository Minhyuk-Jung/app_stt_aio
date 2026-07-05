"""Optional telemetry (opt-in stub, C20)."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_TELEMETRY_ENDPOINT = ""  # unset until product telemetry URL is defined


def send_telemetry_event(
    event: str,
    *,
    enabled: bool,
    properties: dict[str, Any] | None = None,
) -> bool:
    """Send anonymized telemetry when privacy.telemetry is enabled."""
    if not enabled:
        return False
    payload = {"event": event, "properties": properties or {}}
    logger.debug("telemetry (local only): %s", json.dumps(payload, ensure_ascii=False))
    if not _TELEMETRY_ENDPOINT:
        return False
    try:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            _TELEMETRY_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5.0) as response:
            return 200 <= response.status < 300
    except Exception as exc:  # noqa: BLE001
        logger.debug("telemetry send failed: %s", exc)
        return False
