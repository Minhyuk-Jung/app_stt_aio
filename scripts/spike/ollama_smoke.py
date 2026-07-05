"""P0 spike: Ollama connection check (C3, README P0 DoD ③)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ollama connection smoke (P0)")
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama HTTP base URL",
    )
    args = parser.parse_args()

    try:
        from core.llm.ollama_local import OllamaLocalProvider
    except ImportError as exc:
        print("status=skip")
        print(f"reason={exc}")
        return 0

    provider = OllamaLocalProvider(base_url=args.base_url)
    result = provider.test_connection()
    print(f"status={'ok' if result.success else 'fail'}")
    print(f"message={result.message}")
    if result.models:
        print(f"models={len(result.models)}")
        for model in result.models[:5]:
            print(f"  - {model.id}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
