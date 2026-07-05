"""Tests for C18 ModelManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import Config
from core.models.downloader import check_disk_space
from core.models.errors import ModelDownloadError, ModelError, ModelNotFoundError
from core.models.model_manager import ModelManager
from core.models.store_paths import write_install_marker


def _seed_install(install_dir: Path, *, model_id: str = "tiny") -> None:
    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / "model.bin").write_bytes(b"weights")
    write_install_marker(install_dir, model_id=model_id, source="test")


@pytest.fixture
def config(tmp_path: Path):
    cfg = Config.open(tmp_path / "models.db", migrate_backup=False)
    yield cfg
    cfg.close()


@pytest.fixture
def manager(config: Config) -> ModelManager:
    config.bind_model_manager()
    return config.model_manager


def test_list_catalog_contains_base(manager: ModelManager) -> None:
    ids = {item.id for item in manager.list_catalog()}
    assert "base" in ids
    assert "large-v3" in ids


def test_set_and_get_active(manager: ModelManager) -> None:
    manager.set_active("small")
    assert manager.get_active() == "small"


def test_custom_path_resolution(manager: ModelManager, tmp_path: Path) -> None:
    custom = tmp_path / "offline-models"
    custom.mkdir()
    manager.set_custom_path(str(custom))
    assert manager.models_dir == custom
    assert manager.get_custom_path() == str(custom)


def test_custom_path_rejects_missing_dir(manager: ModelManager) -> None:
    with pytest.raises(ModelError, match="존재하지 않습니다"):
        manager.set_custom_path("/path/that/does/not/exist-xyz")


def test_list_installed_discovers_non_catalog_folder(manager: ModelManager) -> None:
    extra = manager.models_dir / "office-whisper"
    _seed_install(extra, model_id="office-whisper")
    installed = {item.id for item in manager.list_installed()}
    assert "office-whisper" in installed


def test_list_installed_local_marker(manager: ModelManager) -> None:
    install_dir = manager.models_dir / "tiny"
    _seed_install(install_dir, model_id="tiny")
    installed = {item.id: item for item in manager.list_installed()}
    assert "tiny" in installed
    assert installed["tiny"].status == "installed"


def test_list_installed_includes_builtin_base(manager: ModelManager) -> None:
    manager.set_active("base")
    installed = {item.id: item for item in manager.list_installed()}
    assert "base" in installed
    assert installed["base"].status == "builtin"


def test_remove_local_install(manager: ModelManager) -> None:
    install_dir = manager.models_dir / "tiny"
    _seed_install(install_dir, model_id="tiny")
    assert manager.remove("tiny") is True
    assert not install_dir.exists()
    assert manager.remove("tiny") is False


def test_readiness_message_builtin(manager: ModelManager) -> None:
    ok, message = manager.readiness_message()
    assert ok is True
    assert "base" in message or "STT" in message


def test_readiness_message_missing_custom(manager: ModelManager) -> None:
    manager.set_active("unknown-custom-model")
    ok, message = manager.readiness_message()
    assert ok is False
    assert "unknown-custom-model" in message or "not installed" in message.lower()


def test_ensure_returns_builtin_without_download(manager: ModelManager) -> None:
    path = manager.ensure("base")
    assert path == "base"


def test_download_invokes_snapshot(manager: ModelManager, tmp_path: Path) -> None:
    dest = manager.models_dir / "tiny"

    def fake_snapshot(**kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "model.bin").write_bytes(b"x")
        return str(dest)

    with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot):
        result = manager.download("tiny")

    assert result == dest
    assert (dest / ".stt_aio_installed.json").is_file()


def test_download_unknown_model_raises(manager: ModelManager) -> None:
    with pytest.raises(ModelDownloadError, match="다운로드 소스"):
        manager.download("not-a-catalog-id")


def test_check_disk_space_raises_when_insufficient(tmp_path: Path) -> None:
    with patch("core.models.downloader.shutil.disk_usage") as usage:
        usage.return_value = type("U", (), {"free": 1024})()
        with pytest.raises(ModelDownloadError, match="디스크"):
            check_disk_space(tmp_path, required_mb=100)


def test_list_ollama_models_parses_response(manager: ModelManager) -> None:
    payload = {"models": [{"name": "llama3", "size": 4_000_000}]}
    with patch("core.models.ollama_probe.request_json", return_value=payload):
        models = manager.list_ollama_models()
    assert len(models) == 1
    assert models[0].name == "llama3"
    assert models[0].size_bytes == 4_000_000


def test_ensure_returns_builtin_for_catalog_model(manager: ModelManager) -> None:
    path = manager.ensure("tiny")
    assert path == "tiny"


def test_repair_install_removes_corrupt(manager: ModelManager) -> None:
    install_dir = manager.models_dir / "tiny"
    install_dir.mkdir(parents=True)
    (install_dir / "partial.part").write_text("x")
    assert manager.repair_install("tiny") is True
    assert not install_dir.exists()


def test_stt_fallback_uses_custom_models_dir(tmp_path: Path) -> None:
    config = Config.open(tmp_path / "fallback.db", migrate_backup=False)
    offline = tmp_path / "offline"
    offline.mkdir()
    config.model_manager.set_custom_path(str(offline))
    config.bind_stt_session()
    fallback = config.stt_session._create_local_fallback()  # noqa: SLF001
    assert fallback._models_dir == offline  # noqa: SLF001
    config.close()


def test_stt_provider_uses_custom_models_dir(tmp_path: Path) -> None:
    config = Config.open(tmp_path / "custom-path.db", migrate_backup=False)
    offline = tmp_path / "offline"
    offline.mkdir()
    config.model_manager.set_custom_path(str(offline))
    provider = config.create_stt_provider()
    assert provider._models_dir == offline  # noqa: SLF001
    config.close()


def test_format_download_error_ssl() -> None:
    from core.models.downloader import format_download_error

    message = format_download_error(Exception("SSL certificate verify failed"))
    assert "SSL" in message


def test_download_installs_catalog_model_locally(manager: ModelManager) -> None:
    dest = manager.models_dir / "tiny"

    def fake_snapshot(**kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "model.bin").write_bytes(b"ok")
        return str(dest)

    with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot):
        path = manager.download("tiny")

    assert path == dest
    assert manager.is_installed("tiny") is True
    assert (dest / ".stt_aio_installed.json").is_file()
