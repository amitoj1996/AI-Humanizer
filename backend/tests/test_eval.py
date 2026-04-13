"""Regression-gate test — loads the REAL detector and runs it against the
labelled golden set.

This is slow (~30s cold start loading HuggingFace models) so it's marked
with `@pytest.mark.eval` and excluded from the default pytest run.  Invoke
explicitly: `pytest -m eval`.  CI runs it on main-branch merges only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval import runner

pytestmark = pytest.mark.eval


@pytest.fixture(scope="module")
def real_detector():
    # Bypass the conftest FakeRegistry for this module — we need the real
    # ensemble detector to exercise the actual model stack.
    from app.detector.ensemble import EnsembleDetector

    return EnsembleDetector()


def test_detection_regression(real_detector):
    metrics = runner.run_detection_metrics(real_detector)
    baseline_path = Path(runner.BASELINE_PATH)
    # Fail loudly rather than skip when baseline is missing — otherwise the
    # "regression gate" silently passes in CI without enforcing anything.
    assert baseline_path.exists(), (
        f"No baseline at {baseline_path}. Run\n"
        f"    python -m app.eval.runner --update-baseline\n"
        f"on a known-good machine and commit the resulting baseline.json."
    )
    baseline = json.loads(baseline_path.read_text())

    assert (
        metrics["accuracy"] + runner.ACCURACY_TOLERANCE
        >= baseline["detection"]["accuracy"]
    ), (
        f"Detection accuracy regressed: {metrics['accuracy']:.2%} "
        f"(baseline {baseline['detection']['accuracy']:.2%}, "
        f"tolerance {runner.ACCURACY_TOLERANCE:.0%})"
    )
    assert (
        metrics["ai_recall"] + runner.ACCURACY_TOLERANCE
        >= baseline["detection"]["ai_recall"]
    ), (
        f"AI recall regressed: {metrics['ai_recall']:.2%} vs baseline "
        f"{baseline['detection']['ai_recall']:.2%}"
    )
    assert (
        metrics["human_specificity"] + runner.ACCURACY_TOLERANCE
        >= baseline["detection"]["human_specificity"]
    ), (
        f"Human specificity regressed: {metrics['human_specificity']:.2%} vs baseline "
        f"{baseline['detection']['human_specificity']:.2%}"
    )


def test_preserve_no_regression():
    metrics = runner.run_preserve_metrics()
    baseline_path = Path(runner.BASELINE_PATH)
    assert baseline_path.exists(), (
        f"No baseline at {baseline_path}. Run\n"
        f"    python -m app.eval.runner --update-baseline\n"
        f"on a known-good machine and commit the resulting baseline.json."
    )
    baseline = json.loads(baseline_path.read_text())
    # Preservation must NEVER regress — it's deterministic.
    assert metrics["pass_rate"] >= baseline["preserve"]["pass_rate"], (
        f"Preserve pass-rate regressed: {metrics['pass_rate']:.2%} vs "
        f"baseline {baseline['preserve']['pass_rate']:.2%} "
        f"— failures: {metrics['failures']}"
    )
