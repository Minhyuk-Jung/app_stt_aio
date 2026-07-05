"""C15 pairing tests."""

from __future__ import annotations

import time

from remote.gateway.pairing import PairingManager


def test_issue_and_pair() -> None:
    manager = PairingManager(pin_ttl_sec=60, bootstrap_secret=False)
    pin = manager.issue_pin()
    assert len(pin) == 4
    token = manager.pair(pin)
    assert token is not None
    assert manager.verify_token(token)


def test_wrong_pin_rejected() -> None:
    manager = PairingManager(bootstrap_secret=False)
    manager.issue_pin()
    assert manager.pair("0000") is None


def test_token_required_after_pair() -> None:
    manager = PairingManager(bootstrap_secret=False)
    pin = manager.issue_pin()
    token = manager.pair(pin)
    assert token is not None
    assert manager.current_pin() is None
    assert not manager.verify_token("invalid")


def test_pin_expires() -> None:
    manager = PairingManager(pin_ttl_sec=1, bootstrap_secret=False)
    pin = manager.issue_pin()
    time.sleep(1.1)
    assert manager.current_pin() is None
    assert manager.pair(pin) is None


def test_pair_lockout_after_failed_attempts() -> None:
    manager = PairingManager(
        bootstrap_secret=False,
        max_failed_attempts=3,
        lockout_sec=60,
    )
    manager.issue_pin()
    for _ in range(3):
        assert manager.pair("0000") is None
    assert manager.is_locked_out()
    assert manager.pair("0000") is None


def test_ensure_pairing_secret_writes_store(tmp_path, monkeypatch) -> None:
    from core.secrets.mock_store import MemorySecretStore
    from core.secrets.store import reset_default_store

    store = MemorySecretStore()
    reset_default_store(store)
    try:
        manager = PairingManager(bootstrap_secret=True)
        assert store.has_secret("remote.pairing_secret")
        pin = manager.issue_pin()
        assert manager.pair(pin)
    finally:
        reset_default_store(None)
