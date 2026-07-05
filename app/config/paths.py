"""Re-export path rules (canonical implementation: core.paths)."""

from core.paths import APP_NAME, AppPaths, ensure_app_dirs, get_app_data_root, get_app_paths

__all__ = [
    "APP_NAME",
    "AppPaths",
    "ensure_app_dirs",
    "get_app_data_root",
    "get_app_paths",
]
