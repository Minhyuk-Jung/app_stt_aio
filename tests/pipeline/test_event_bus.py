"""Tests for pipeline event bus."""

from __future__ import annotations

from core.pipeline.event_bus import PipelineEventBus
from core.pipeline.types import PipelineRun, PipelineStatus, StageArtifact


def test_event_bus_emits_in_registration_order() -> None:
    bus = PipelineEventBus()
    events: list[str] = []

    bus.on_stage_started(lambda stage: events.append(f"start:{stage}"))
    bus.on_stage_completed(
        lambda stage, _artifact: events.append(f"done:{stage}")
    )
    bus.on_pipeline_finished(
        lambda run: events.append(f"finish:{run.status.value}")
    )

    artifact = StageArtifact(session_id="s", stage=1, text="t", language="ko")
    bus.emit_stage_started(1)
    bus.emit_stage_completed(1, artifact)
    bus.emit_pipeline_finished(
        PipelineRun(session_id="s", status=PipelineStatus.FINISHED)
    )

    assert events == ["start:1", "done:1", "finish:finished"]


def test_event_bus_isolates_failing_callbacks() -> None:
    bus = PipelineEventBus()
    seen: list[int] = []

    bus.on_stage_started(lambda _stage: (_ for _ in ()).throw(RuntimeError("fail")))
    bus.on_stage_started(lambda stage: seen.append(stage))

    bus.emit_stage_started(1)

    assert seen == [1]
