"""ModelManager — Whisper cache and Ollama probe (C18)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from core.models.catalog import CATALOG_BY_ID, WHISPER_CATALOG
from core.models.downloader import download_whisper_model
from core.models.errors import ModelError, ModelNotFoundError
from core.models.ollama_probe import list_ollama_models
from core.models.resolver import KNOWN_WHISPER_MODELS, resolve_whisper_model_path
from core.models.store_paths import (
    is_locally_installed,
    model_install_dir,
    resolve_models_dir,
    verify_model_install,
)
from core.models.types import InstalledModel, ModelCatalogItem, OllamaModel, ProgressCallback

if TYPE_CHECKING:
    from app.config.config import Config


class ModelManager:
    """Plan §3: catalog, install, ensure, active model, Ollama list."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def models_dir(self) -> Path:
        return resolve_models_dir(
            default_dir=self._config.paths().models,
            custom_path=str(self._config.get("models.custom_path")),
        )

    @property
    def default_models_dir(self) -> Path:
        return self._config.paths().models

    def list_catalog(self) -> list[ModelCatalogItem]:
        return list(WHISPER_CATALOG)

    def list_installed(self) -> list[InstalledModel]:
        results: list[InstalledModel] = []
        seen: set[str] = set()
        for item in WHISPER_CATALOG:
            install_dir = model_install_dir(self.models_dir, item.id)
            if is_locally_installed(install_dir, model_id=item.id):
                results.append(
                    InstalledModel(
                        id=item.id,
                        path=install_dir,
                        status="installed",
                        source="local",
                    )
                )
                seen.add(item.id)

        models_root = self.models_dir
        if models_root.is_dir():
            for entry in sorted(models_root.iterdir()):
                if not entry.is_dir() or entry.name in seen or entry.name.startswith("."):
                    continue
                if is_locally_installed(entry, model_id=entry.name):
                    results.append(
                        InstalledModel(
                            id=entry.name,
                            path=entry,
                            status="installed",
                            source="local",
                        )
                    )
                    seen.add(entry.name)

        active = self.get_active()
        if active in KNOWN_WHISPER_MODELS and active not in seen:
            results.append(
                InstalledModel(
                    id=active,
                    path=active,
                    status="builtin",
                    source="faster-whisper",
                )
            )
        return results

    def get_active(self) -> str:
        return str(self._config.get("stt.model")).strip()

    def set_active(self, model_id: str) -> None:
        model_id = model_id.strip()
        if not model_id:
            raise ModelError("model_id is empty")
        self._config.set("stt.model", model_id)

    def set_custom_path(self, path: str) -> None:
        cleaned = path.strip()
        if cleaned and not Path(cleaned).is_dir():
            raise ModelError(f"오프라인 모델 경로가 존재하지 않습니다: {cleaned}")
        self._config.set("models.custom_path", cleaned)

    def get_custom_path(self) -> str:
        return str(self._config.get("models.custom_path")).strip()

    def is_installed(self, model_id: str) -> bool:
        install_dir = model_install_dir(self.models_dir, model_id)
        if is_locally_installed(install_dir, model_id=model_id):
            return True
        if model_id in KNOWN_WHISPER_MODELS:
            try:
                resolve_whisper_model_path(self.models_dir, model_id)
                return True
            except ModelNotFoundError:
                return False
        return False

    def verify_install(self, model_id: str) -> str | None:
        """Return install error message, or None when valid or absent."""
        install_dir = model_install_dir(self.models_dir, model_id)
        if not install_dir.exists():
            return None
        return verify_model_install(install_dir, model_id=model_id)

    def repair_install(self, model_id: str) -> bool:
        """Remove corrupt partial install (plan §7 checksum mismatch)."""
        install_dir = model_install_dir(self.models_dir, model_id)
        if not install_dir.exists():
            return False
        if verify_model_install(install_dir, model_id=model_id) is None:
            return False
        shutil.rmtree(install_dir)
        return True

    def ensure(
        self,
        model_id: str | None = None,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> Path | str:
        """Return local model path or faster-whisper builtin id."""
        active_id = (model_id or self.get_active()).strip()
        if not active_id:
            raise ModelNotFoundError("stt.model is empty")

        install_dir = model_install_dir(self.models_dir, active_id)
        install_error = verify_model_install(install_dir, model_id=active_id)
        if install_dir.exists() and install_error:
            shutil.rmtree(install_dir, ignore_errors=True)
        elif is_locally_installed(install_dir, model_id=active_id):
            return install_dir

        if active_id in KNOWN_WHISPER_MODELS:
            return resolve_whisper_model_path(self.models_dir, active_id)

        if active_id in CATALOG_BY_ID and CATALOG_BY_ID[active_id].repo_id:
            download_whisper_model(active_id, install_dir, on_progress=on_progress)
            return install_dir

        return resolve_whisper_model_path(self.models_dir, active_id)

    def download(
        self,
        model_id: str,
        *,
        on_progress: ProgressCallback | None = None,
        force: bool = False,
        controller=None,
    ) -> Path:
        install_dir = model_install_dir(self.models_dir, model_id)
        return download_whisper_model(
            model_id,
            install_dir,
            on_progress=on_progress,
            force=force,
            controller=controller,
        )

    def remove(self, model_id: str) -> bool:
        install_dir = model_install_dir(self.models_dir, model_id)
        if not install_dir.exists():
            return False
        shutil.rmtree(install_dir)
        return True

    def list_ollama_models(self) -> list[OllamaModel]:
        base_url = str(self._config.get("llm.base_url"))
        timeout = float(self._config.get("llm.timeout_sec"))
        return list_ollama_models(base_url, timeout_sec=timeout)

    def readiness_message(self) -> tuple[bool, str]:
        model_id = self.get_active()
        install_dir = model_install_dir(self.models_dir, model_id)
        install_error = self.verify_install(model_id)
        if install_error:
            hint = (
                "설정 → 모델 탭에서 다시 다운로드하거나 "
                "오프라인 경로(models.custom_path)를 지정하세요."
            )
            return False, f"{install_error} {hint}"

        try:
            path = resolve_whisper_model_path(self.models_dir, model_id)
            if is_locally_installed(install_dir, model_id=model_id):
                return True, f"STT 모델 준비됨 (로컬): {install_dir}"
            custom = self.get_custom_path()
            if custom:
                return True, f"STT 모델 준비됨 (오프라인 경로): {path}"
            return True, f"STT 모델 준비됨: {path}"
        except ModelNotFoundError as exc:
            hint = (
                "설정 → 모델 탭에서 다운로드하거나 오프라인 모델 폴더를 지정하세요."
            )
            return False, f"{exc} {hint}"
