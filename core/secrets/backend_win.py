"""Windows DPAPI-backed secret file store (C19 P2 minimum)."""

from __future__ import annotations

import ctypes
import json
import logging
import sys
from ctypes import wintypes
from pathlib import Path

logger = logging.getLogger(__name__)

if sys.platform != "win32":
    raise RuntimeError("DpapiFileSecretStore is only available on Windows")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _bytes_to_blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = DATA_BLOB()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))
    return blob, buffer


def _blob_to_bytes(blob: DATA_BLOB) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def _dpapi_protect(data: bytes) -> bytes:
    in_blob, _ = _bytes_to_blob(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptProtectData failed")
    try:
        return _blob_to_bytes(out_blob)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    in_blob, _ = _bytes_to_blob(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return _blob_to_bytes(out_blob)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


class DpapiFileSecretStore:
    """Persist encrypted secrets for the current Windows user."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._secrets: dict[str, str] = {}
        self._load()

    def set_secret(self, name: str, value: str) -> None:
        if not value.strip():
            raise ValueError("secret value cannot be empty")
        self._secrets[name] = value.strip()
        self._save()

    def get_secret(self, name: str) -> str | None:
        return self._secrets.get(name)

    def delete_secret(self, name: str) -> bool:
        if name not in self._secrets:
            return False
        del self._secrets[name]
        self._save()
        return True

    def has_secret(self, name: str) -> bool:
        return name in self._secrets

    def _load(self) -> None:
        if not self._path.exists():
            self._secrets = {}
            return
        try:
            payload = _dpapi_unprotect(self._path.read_bytes())
            self._secrets = json.loads(payload.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load secret store %s: %s", self._path, exc)
            self._secrets = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._secrets, ensure_ascii=False).encode("utf-8")
        self._path.write_bytes(_dpapi_protect(payload))
