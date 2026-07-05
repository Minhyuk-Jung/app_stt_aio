"""Config schema version migration and default seeding."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config.schema import (
    CONFIG_SCHEMA_VERSION,
    SCHEMA_BY_KEY,
    SETTING_DEFINITIONS,
    serialize_value,
)
from core.store.repos.setting_repo import SettingRepo

logger = logging.getLogger(__name__)

_SCHEMA_VERSION_KEY = "config.schema_version"


def migrate_settings(repo: SettingRepo) -> int:
    stored_version = _read_schema_version(repo)
    seeded = _seed_missing_defaults(repo)

    if stored_version < CONFIG_SCHEMA_VERSION or seeded:
        repo.set(_SCHEMA_VERSION_KEY, str(CONFIG_SCHEMA_VERSION))
        if stored_version < CONFIG_SCHEMA_VERSION:
            logger.info(
                "Config schema migrated from v%s to v%s",
                stored_version,
                CONFIG_SCHEMA_VERSION,
            )
    return CONFIG_SCHEMA_VERSION


def _seed_missing_defaults(repo: SettingRepo) -> bool:
    seeded = False
    for defn in SETTING_DEFINITIONS:
        if repo.get(defn.key) is None:
            repo.set(defn.key, serialize_value(defn, defn.default))
            logger.debug("Seeded default for %s", defn.key)
            seeded = True
    return seeded


def _read_schema_version(repo: SettingRepo) -> int:
    raw = repo.get(_SCHEMA_VERSION_KEY)
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid config.schema_version=%r, resetting", raw)
        return 0


def repair_invalid_settings(
    repo: SettingRepo,
    *,
    backup_dir: Path | None = None,
) -> list[str]:
    """Reset invalid stored values to defaults. Returns repaired keys."""
    from app.config.schema import parse_value, validate_value

    repaired: list[str] = []
    invalid_snapshot: dict[str, str] = {}

    for defn in SETTING_DEFINITIONS:
        raw = repo.get(defn.key)
        if raw is None:
            continue
        try:
            parsed = parse_value(defn, raw)
            validate_value(defn, parsed)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Repairing invalid setting %s (%s): %s",
                defn.key,
                raw,
                exc,
            )
            invalid_snapshot[defn.key] = raw
            repo.set(defn.key, serialize_value(defn, defn.default))
            repaired.append(defn.key)

    if repaired and backup_dir is not None:
        _write_repair_backup(backup_dir, invalid_snapshot)

    return repaired


def _write_repair_backup(backup_dir: Path, invalid_values: dict[str, str]) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"settings_repair_{timestamp}.json"
    payload = {
        "repaired_at": timestamp,
        "invalid_values": invalid_values,
    }
    backup_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Backed up invalid settings to %s", backup_path)
