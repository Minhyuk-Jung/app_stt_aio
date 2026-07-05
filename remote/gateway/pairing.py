"""PIN pairing and session tokens (C15 §6.2, C19 §11)."""

from __future__ import annotations

import logging
import secrets
import threading
import time

logger = logging.getLogger(__name__)

PAIRING_SECRET_NAME = "remote.pairing_secret"
DEFAULT_MAX_FAILED_ATTEMPTS = 5
DEFAULT_LOCKOUT_SEC = 60


def ensure_pairing_secret() -> None:
    """Persist installation pairing secret via C19 store (best-effort)."""
    try:
        from core.secrets.store import get_default_store

        store = get_default_store()
        if store.get_secret(PAIRING_SECRET_NAME):
            return
        store.set_secret(PAIRING_SECRET_NAME, secrets.token_urlsafe(32))
    except Exception as exc:  # noqa: BLE001
        logger.debug("pairing secret bootstrap skipped: %s", exc)


class PairingManager:
    """Issue PIN, exchange for bearer token, verify uploads."""

    def __init__(
        self,
        *,
        pin_ttl_sec: int = 600,
        token_ttl_sec: int = 86_400,
        max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
        lockout_sec: int = DEFAULT_LOCKOUT_SEC,
        bootstrap_secret: bool = True,
    ) -> None:
        self._pin_ttl_sec = pin_ttl_sec
        self._token_ttl_sec = token_ttl_sec
        self._max_failed_attempts = max(1, max_failed_attempts)
        self._lockout_sec = max(1, lockout_sec)
        self._lock = threading.Lock()
        self._pin: str | None = None
        self._pin_expires_at: float = 0.0
        self._tokens: dict[str, float] = {}
        self._failed_attempts = 0
        self._lockout_until: float = 0.0
        if bootstrap_secret:
            ensure_pairing_secret()

    def is_locked_out(self) -> bool:
        with self._lock:
            now = time.time()
            if now < self._lockout_until:
                return True
            if self._lockout_until > 0 and now >= self._lockout_until:
                self._failed_attempts = 0
                self._lockout_until = 0.0
            return False

    def issue_pin(self) -> str:
        pin = f"{secrets.randbelow(10_000):04d}"
        with self._lock:
            self._pin = pin
            self._pin_expires_at = time.time() + self._pin_ttl_sec
        return pin

    def current_pin(self) -> str | None:
        with self._lock:
            if self._pin and time.time() < self._pin_expires_at:
                return self._pin
            return None

    def pair(self, pin: str) -> str | None:
        normalized = pin.strip()
        with self._lock:
            now = time.time()
            if now < self._lockout_until:
                return None
            if self._lockout_until > 0 and now >= self._lockout_until:
                self._failed_attempts = 0
                self._lockout_until = 0.0

            if not self._pin or now >= self._pin_expires_at:
                self._register_failed_attempt_locked()
                return None
            if normalized != self._pin:
                self._register_failed_attempt_locked()
                return None

            token = secrets.token_urlsafe(32)
            self._tokens[token] = now + self._token_ttl_sec
            self._pin = None
            self._pin_expires_at = 0.0
            self._failed_attempts = 0
            self._lockout_until = 0.0
            return token

    def _register_failed_attempt_locked(self) -> None:
        self._failed_attempts += 1
        if self._failed_attempts >= self._max_failed_attempts:
            self._lockout_until = time.time() + self._lockout_sec
            self._failed_attempts = 0

    def verify_token(self, token: str) -> bool:
        if not token:
            return False
        with self._lock:
            expires = self._tokens.get(token)
            if expires is None:
                return False
            if time.time() >= expires:
                del self._tokens[token]
                return False
            return True

    def revoke_all(self) -> None:
        with self._lock:
            self._pin = None
            self._pin_expires_at = 0.0
            self._tokens.clear()
            self._failed_attempts = 0
            self._lockout_until = 0.0
