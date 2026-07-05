"""P0 spike: Korean text injection byte integrity (C5).

Usage:
  python scripts/spike/inject_ko_smoke.py --dry-run
  python scripts/spike/inject_ko_smoke.py --verify-clipboard
  python scripts/spike/inject_ko_smoke.py --verify-paste   # paste path, Ctrl+V mocked
  python scripts/spike/inject_ko_smoke.py --inject-auto     # UNICODE SendInput dispatch check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLES = (
    "안녕하세요 STT-AIO 테스트입니다.",
    "한글 주입 0% 손실 검증: 가나다라마바사 12345",
    "혼합문장 Mixed 한글English 日本語テスト 🎤",
)


def verify_encoding_roundtrip() -> list[str]:
    from core.inject.text_encoding import text_to_utf16_units

    failures: list[str] = []
    for text in SAMPLES:
        units = text_to_utf16_units(text)
        recovered = b"".join(
            unit.to_bytes(2, "little") for unit in units
        ).decode("utf-16-le")
        if recovered != text:
            failures.append(f"roundtrip failed: {text!r} -> {recovered!r}")
    return failures


def verify_clipboard_samples() -> list[str]:
    """Windows clipboard UTF-16 via clipboard_input (with backup/restore)."""
    if sys.platform != "win32":
        return ["clipboard verify requires Windows"]
    from core.inject.clipboard_input import verify_clipboard_roundtrip

    failures: list[str] = []
    for text in SAMPLES:
        if not verify_clipboard_roundtrip(text):
            failures.append(f"clipboard roundtrip failed for {text!r}")
    return failures


def verify_paste_path_samples() -> list[str]:
    """Exercise paste_via_clipboard orchestration (Ctrl+V mocked, restore verified)."""
    if sys.platform != "win32":
        return ["paste verify requires Windows"]
    from core.inject.clipboard_input import paste_via_clipboard

    failures: list[str] = []
    for text in SAMPLES:
        with patch("core.inject.clipboard_input._send_ctrl_v") as mock_v:
            with patch("core.inject.clipboard_input._restore_clipboard") as mock_restore:
                with patch(
                    "core.inject.clipboard_input._read_clipboard_backup",
                    return_value="BACKUP",
                ):
                    try:
                        paste_via_clipboard(text)
                    except Exception as exc:  # noqa: BLE001
                        failures.append(f"paste_via_clipboard failed for {text!r}: {exc}")
                        continue
                    if mock_v.call_count != 1:
                        failures.append(f"ctrl+v not sent once for {text!r}")
                    if mock_restore.call_count != 1:
                        failures.append(f"clipboard not restored for {text!r}")
    return failures


def run_inject_auto() -> int:
    """Verify UNICODE SendInput dispatch (chars_injected) for Korean samples."""
    if sys.platform != "win32":
        print("inject-auto requires Windows")
        return 2
    from core.inject.injector import Injector
    from core.inject.types import InjectMethod, InjectOptions

    injector = Injector(default_method=InjectMethod.UNICODE)
    opts = InjectOptions(target_check=False)
    failures: list[str] = []
    for text in SAMPLES:
        result = injector.inject(text, method=InjectMethod.UNICODE, options=opts)
        if not result.success:
            failures.append(f"inject failed len={len(text)} err={result.error}")
        elif result.chars_injected != len(text):
            failures.append(
                f"chars mismatch len={len(text)} injected={result.chars_injected}"
            )

    if failures:
        for idx, line in enumerate(failures, start=1):
            print(f"FAIL[{idx}] {line}")
        return 1
    print(f"inject_auto=ok samples={len(SAMPLES)} method=unicode")
    return 0


def run_inject_notepad() -> int:
    """Legacy alias: Win11 Notepad is unreliable; use tkinter auto target."""
    return run_inject_auto()


def run_inject() -> int:
    if sys.platform != "win32":
        print("inject mode requires Windows")
        return 2
    from core.inject.injector import Injector
    from core.inject.types import InjectMethod

    injector = Injector(default_method=InjectMethod.UNICODE)
    caps = injector.capabilities()
    if not caps.supports_unicode:
        print("unicode injection not supported on this platform")
        return 2

    print("5초 안에 메모장 등 텍스트 입력 필드에 포커스를 맞추세요…")
    import time

    time.sleep(5)
    text = SAMPLES[0]
    result = injector.inject(text, method=InjectMethod.UNICODE)
    if not result.success:
        print(f"inject failed: {result.error}")
        return 1
    print(f"injected_chars={result.chars_injected}")
    print("수동 확인: 입력 필드의 텍스트가 원문과 일치하는지 확인하세요.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Korean injection smoke (P0)")
    parser.add_argument("--dry-run", action="store_true", help="UTF-16 roundtrip only")
    parser.add_argument(
        "--verify-clipboard",
        action="store_true",
        help="Windows clipboard UTF-16 roundtrip (automated)",
    )
    parser.add_argument(
        "--verify-paste",
        action="store_true",
        help="paste_via_clipboard path with Ctrl+V mocked",
    )
    parser.add_argument(
        "--inject-auto",
        action="store_true",
        help="Automated SendInput verify via tkinter Text (Windows)",
    )
    parser.add_argument(
        "--inject-notepad",
        action="store_true",
        help="Alias for --inject-auto",
    )
    parser.add_argument("--inject", action="store_true", help="Live Windows inject (manual focus)")
    args = parser.parse_args()

    failures = verify_encoding_roundtrip()
    if failures:
        for line in failures:
            print(f"FAIL {line}")
        return 1
    print(f"encoding_roundtrip=ok samples={len(SAMPLES)}")

    if args.verify_clipboard:
        cb_failures = verify_clipboard_samples()
        if cb_failures:
            for line in cb_failures:
                print(f"FAIL {line!a}")
            return 1
        print(f"clipboard_roundtrip=ok samples={len(SAMPLES)}")
        return 0

    if args.verify_paste:
        paste_failures = verify_paste_path_samples()
        if paste_failures:
            for line in paste_failures:
                print(f"FAIL {line!a}")
            return 1
        print(f"paste_path=ok samples={len(SAMPLES)}")
        return 0

    if args.inject_notepad or args.inject_auto:
        return run_inject_auto()

    if args.dry_run or not args.inject:
        if not args.inject:
            print("hint: use --inject-notepad for automated SendInput test")
            print("hint: use --inject for live Windows test with manual focus")
            print("hint: use --verify-clipboard or --verify-paste for automated tests")
        return 0
    return run_inject()


if __name__ == "__main__":
    raise SystemExit(main())
