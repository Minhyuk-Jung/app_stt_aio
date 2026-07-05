"""Smoke tests for application entry point."""

from __future__ import annotations

import sys
from unittest.mock import patch


def test_main_returns_error_when_pyside6_missing() -> None:
    import importlib

    main_module = importlib.import_module("app.main")

    with patch.dict(sys.modules, {"PySide6.QtCore": None, "PySide6.QtWidgets": None}):
        with patch("builtins.print") as mock_print:
            result = main_module.main()

    assert result == 1
    mock_print.assert_called_once()
    assert "PySide6" in mock_print.call_args[0][0]
