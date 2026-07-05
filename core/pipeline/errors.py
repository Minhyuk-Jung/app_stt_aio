"""Pipeline errors (C4)."""

from __future__ import annotations


class PipelineError(Exception):
    """Base pipeline failure."""


class PipelineCanceledError(PipelineError):
    """Pipeline run was canceled before completion."""


class PipelineNotImplementedError(PipelineError):
    """Feature reserved for a later phase."""
