"""Generate PyInstaller Windows version resource (C16 plan §3)."""

from __future__ import annotations

from pathlib import Path


def write_version_info(path: Path, *, version: str, product: str, publisher: str) -> None:
    parts = [int(p) for p in version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    filevers = tuple(parts[:4])
    text = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={filevers},
    prodvers={filevers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', '{publisher}'),
            StringStruct('FileDescription', '{product}'),
            StringStruct('FileVersion', '{version}'),
            StringStruct('InternalName', '{product}'),
            StringStruct('OriginalFilename', 'STT-AIO.exe'),
            StringStruct('ProductName', '{product}'),
            StringStruct('ProductVersion', '{version}'),
          ],
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ]
)
"""
    path.write_text(text, encoding="utf-8")
