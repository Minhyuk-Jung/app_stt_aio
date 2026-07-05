"""Korean WER regression baseline (README §12)."""

from __future__ import annotations

from tests.regression.ko_wer.wer_utils import load_baseline, wer


def test_ko_wer_baseline_from_fixture() -> None:
    payload = load_baseline()
    default_max = float(payload.get("max_wer", 0.0))
    for case in payload["cases"]:
        if "hypothesis" not in case:
            continue
        score = wer(case["reference"], case["hypothesis"])
        limit = float(case.get("max_wer", default_max))
        assert score <= limit, f"{case['id']}: wer={score:.3f} > {limit}"
