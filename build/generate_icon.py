"""Generate a minimal Windows .ico for PyInstaller (C16)."""

from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "assets" / "icon.ico"


def _bmp_header(width: int, height: int, *, bpp: int = 32) -> bytes:
    row_bytes = width * (bpp // 8)
    padded = row_bytes + ((4 - row_bytes % 4) % 4)
    image_size = padded * height
    header = struct.pack(
        "<IIIHHIIIIII",
        40,
        width,
        height * 2,
        1,
        bpp,
        0,
        image_size,
        0,
        0,
        0,
        0,
    )
    pixels = bytearray()
    for y in range(height):
        row = bytearray()
        for x in range(width):
            # simple mic-like circle on blue background
            cx, cy = width // 2, height // 2
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist < width * 0.35:
                row.extend((255, 255, 255, 255))
            elif dist < width * 0.42:
                row.extend((30, 120, 220, 255))
            else:
                row.extend((20, 80, 180, 255))
        row.extend(b"\x00" * (padded - row_bytes))
        pixels.extend(row)
    return header + bytes(pixels)


def write_icon(path: Path = OUT) -> Path:
    sizes = (16, 32, 48)
    images = [_bmp_header(size, size) for size in sizes]
    offset = 6 + 16 * len(images)
    parts = [struct.pack("<HHH", 0, 1, len(images))]
    for size, data in zip(sizes, images):
        parts.append(
            struct.pack(
                "<BBBBHHII",
                size,
                size,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        offset += len(data)
    for data in images:
        parts.append(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(parts))
    return path


def main() -> None:
    target = write_icon()
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
