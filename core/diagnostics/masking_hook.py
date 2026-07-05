"""C19 masking hook alias (C20 plan §6.1)."""

from core.diagnostics.masking_filter import MaskingFilter, MaskingFormatter

# Plan document names this module masking_hook.py
MaskingHook = MaskingFilter

__all__ = ["MaskingFilter", "MaskingFormatter", "MaskingHook"]
