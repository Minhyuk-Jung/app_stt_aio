"""Whisper model download helpers (C18)."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.models.catalog import CATALOG_BY_ID
from core.models.download_control import DownloadController
from core.models.errors import ModelDownloadError
from core.models.store_paths import compute_manifest_checksum, write_install_marker
from core.models.types import ProgressCallback


def _emit(callback: ProgressCallback | None, downloaded: int, total: int, state: str) -> None:
    if callback is not None:
        callback(downloaded, total, state)  # type: ignore[arg-type]


def format_download_error(exc: Exception) -> str:
    """Map network/proxy/SSL failures to actionable Korean messages (plan §6.3)."""
    message = str(exc).lower()
    if any(token in message for token in ("ssl", "certificate", "cert")):
        return (
            f"SSL/인증서 오류: 사내 프록시·루트 인증서 설정을 확인하세요. ({exc})"
        )
    if "proxy" in message:
        return f"프록시 오류: HTTP_PROXY/HTTPS_PROXY 환경 변수를 확인하세요. ({exc})"
    if any(token in message for token in ("timeout", "timed out")):
        return f"연결 시간 초과: 네트워크 상태를 확인하고 다시 시도하세요. ({exc})"
    if any(
        token in message
        for token in ("connection refused", "failed to establish", "name or service not known")
    ):
        return f"네트워크 연결 실패: 인터넷 연결을 확인하세요. ({exc})"
    return f"모델 다운로드 실패: {exc}"


def check_disk_space(dest_parent: Path, required_mb: int) -> None:
    target = dest_parent if dest_parent.exists() else dest_parent.parent
    target.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(target)
    required = required_mb * 1024 * 1024
    if usage.free < required:
        free_mb = usage.free // (1024 * 1024)
        raise ModelDownloadError(
            f"디스크 공간이 부족합니다. 필요 약 {required_mb}MB, 여유 {free_mb}MB"
        )


def _make_hf_tqdm_class(
    *,
    on_progress: ProgressCallback | None,
    expected_mb: int,
    controller: DownloadController | None,
):
    """Bridge huggingface_hub tqdm → app progress callback (MB)."""
    from tqdm.auto import tqdm

    class _DownloadTqdm(tqdm):
        def update(self, n=1):
            super().update(n)
            if controller is not None:
                controller.raise_if_canceled()
                if self.total:
                    controller.update_progress(int(self.n), int(self.total))
            if on_progress is not None:
                total_bytes = int(self.total or 0)
                if total_bytes > 0:
                    downloaded_mb = int(self.n) // (1024 * 1024)
                    total_mb = max(expected_mb, total_bytes // (1024 * 1024))
                else:
                    downloaded_mb = 0
                    total_mb = expected_mb
                on_progress(downloaded_mb, total_mb, "downloading")

    return _DownloadTqdm


def _snapshot_to_dir(
    repo_id: str,
    dest_dir: Path,
    *,
    controller: DownloadController | None = None,
    on_progress: ProgressCallback | None = None,
    expected_mb: int = 0,
) -> None:
    from huggingface_hub import snapshot_download

    dest_dir.mkdir(parents=True, exist_ok=True)

    kwargs: dict = {
        "repo_id": repo_id,
        "local_dir": str(dest_dir),
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    tqdm_class = None
    if on_progress is not None or controller is not None:
        tqdm_class = _make_hf_tqdm_class(
            on_progress=on_progress,
            expected_mb=expected_mb,
            controller=controller,
        )
    try:
        snapshot_download(**kwargs, tqdm_class=tqdm_class)
    except TypeError:
        try:
            snapshot_download(**kwargs)
        except TypeError:
            cached = snapshot_download(repo_id=repo_id, resume_download=True)
            cached_path = Path(cached)
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(cached_path, dest_dir)
        return
    if controller is not None:
        controller.raise_if_canceled()


def download_whisper_model(
    model_id: str,
    dest_dir: Path,
    *,
    on_progress: ProgressCallback | None = None,
    force: bool = False,
    controller: DownloadController | None = None,
) -> Path:
    """Download a catalog model into dest_dir, verify weights, write marker."""
    item = CATALOG_BY_ID.get(model_id)
    if item is None or not item.repo_id:
        raise ModelDownloadError(f"다운로드 소스가 없는 모델입니다: {model_id}")

    if force and dest_dir.exists():
        shutil.rmtree(dest_dir)

    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    check_disk_space(dest_dir.parent, item.size_mb)
    _emit(on_progress, 0, item.size_mb, "starting")

    try:
        from huggingface_hub import snapshot_download  # noqa: F401
    except ImportError as exc:
        raise ModelDownloadError(
            "huggingface_hub가 설치되지 않았습니다. pip install -e \".[stt]\" 를 실행하세요."
        ) from exc

    _emit(on_progress, 0, item.size_mb, "downloading")
    try:
        if controller is not None:
            controller.raise_if_canceled()
        _snapshot_to_dir(
            item.repo_id,
            dest_dir,
            controller=controller,
            on_progress=on_progress,
            expected_mb=item.size_mb,
        )
        if controller is not None:
            controller.raise_if_canceled()
    except Exception as exc:  # noqa: BLE001
        _emit(on_progress, 0, item.size_mb, "error")
        from core.diagnostics import report_error

        report_error(exc, context={"model_id": model_id, "repo_id": item.repo_id})
        raise ModelDownloadError(format_download_error(exc)) from exc

    _emit(on_progress, item.size_mb, item.size_mb, "verifying")
    from core.models.store_paths import has_model_weights, verify_model_install

    verify_error = verify_model_install(dest_dir, model_id=model_id)
    if verify_error:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise ModelDownloadError(verify_error)

    if not has_model_weights(dest_dir):
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise ModelDownloadError("다운로드가 완료되지 않았습니다. 네트워크를 확인하세요.")

    checksum = compute_manifest_checksum(dest_dir)
    write_install_marker(
        dest_dir,
        model_id=model_id,
        source=item.repo_id,
        checksum=checksum,
    )
    _emit(on_progress, item.size_mb, item.size_mb, "finished")
    return dest_dir
