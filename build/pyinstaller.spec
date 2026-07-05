# -*- mode: python ; coding: utf-8 -*-
# C16 PyInstaller spec — Windows desktop bundle (models excluded per C18).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
SPEC_DIR = Path(SPECPATH).resolve()
PROJECT = SPEC_DIR.parent
VERSION_INFO = SPEC_DIR / "version_info.txt"
ICON = SPEC_DIR / "assets" / "icon.ico"
PWA_DIR = PROJECT / "remote" / "gateway" / "pwa"

_pyside6_datas, _pyside6_binaries, _pyside6_hiddenimports = collect_all("PySide6")
_shiboken_datas, _shiboken_binaries, _shiboken_hiddenimports = collect_all("shiboken6")
_pwa_datas = [(str(PWA_DIR), "remote/gateway/pwa")] if PWA_DIR.is_dir() else []

a = Analysis(
    [str(PROJECT / "app" / "main.py")],
    pathex=[str(PROJECT)],
    binaries=_pyside6_binaries + _shiboken_binaries,
    datas=_pyside6_datas + _shiboken_datas + _pwa_datas,
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "faster_whisper",
        "ctranslate2",
        "huggingface_hub",
        "sounddevice",
        "_sounddevice_data",
        "docx",
        "certifi",
        "keyring.backends.Windows",
        "core.store.migrations.v001_initial",
        "core.store.migrations.v002_session_indexes",
        "core.store.migrations.v003_artifacts",
        "core.store.migrations.v004_modes",
        "core.store.migrations.v005_dictionaries",
        "core.store.migrations.v006_dictionary_target_app",
        *_pyside6_hiddenimports,
        *_shiboken_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pytest",
        "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="STT-AIO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(VERSION_INFO) if VERSION_INFO.is_file() else None,
    icon=str(ICON) if ICON.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="STT-AIO",
)
