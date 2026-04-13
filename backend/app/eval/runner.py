"""Evaluation harness — runs the real detector against a labelled golden set.

What this is:
  - A regression gate on detector quality.  We hold a small committed corpus
    of known-human and known-AI samples; if a code change causes detector
    accuracy to drop meaningfully (or false positives to rise), CI fails.

What this is NOT:
  - A frontier benchmark.  We don't compare against GPTZero / Originality
    scores — those are cloud services that'd break the local-first story.
  - A proof of absolute accuracy.  The samples are small and curated.  This
    exists so we catch regressions, not to publish accuracy numbers.

Usage:
  python -m app.eval.runner                    # print metrics
  python -m app.eval.runner --update-baseline  # overwrite baseline.json
  pytest -m eval                               # regression gate (CI)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..humanizer import preserve

EVAL_DIR = Path(__file__).parent
SAMPLES_DIR = EVAL_DIR / "samples"
BASELINE_PATH = EVAL_DIR / "baseline.json"

# How much accuracy drop is tolerated before CI fails.  Loose for v1 so
# routine prompt tweaks don't turn CI red, tighter once we have a real
# corpus and the signal is stable.
ACCURACY_TOLERANCE = 0.10  # absolute (e.g. 0.80 → 0.70 still passes)


def _load_samples(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def run_detection_metrics(detector) -> dict:
    """Run the detector against the committed samples and compute metrics."""
    human = _load_samples(SAMPLES_DIR / "human.json")
    ai = _load_samples(SAMPLES_DIR / "ai.json")

    human_scores = [detector.detect(s["text"])["ai_score"] for s in human]
    ai_scores = [detector.detect(s["text"])["ai_score"] for s in ai]

    # Binary threshold: >= 0.5 → AI.  Adjust as the detector evolves.
    threshold = 0.5
    human_correct = sum(1 for s in human_scores if s < threshold)
    ai_correct = sum(1 for s in ai_scores if s >= threshold)

    n_human = len(human_scores)
    n_ai = len(ai_scores)
    accuracy = (human_correct + ai_correct) / (n_human + n_ai)

    return {
        "samples_human": n_human,
        "samples_ai": n_ai,
        "accuracy": round(accuracy, 4),
        "human_specificity": round(human_correct / n_human, 4) if n_human else 0.0,
        "ai_recall": round(ai_correct / n_ai, 4) if n_ai else 0.0,
        "avg_score_human": round(sum(human_scores) / n_human, 4) if n_human else 0.0,
        "avg_score_ai": round(sum(ai_scores) / n_ai, 4) if n_ai else 0.0,
    }


def run_preserve_metrics() -> dict:
    """Citation/quote/code preservation is deterministic — verify roundtrip
    on curated tricky inputs."""
    cases = _load_samples(SAMPLES_DIR / "preserve.json")
    passed = 0
    failures: list[str] = []
    for case in cases:
        protected, spans = preserve.protect(case["text"])
        restored = preserve.restore(protected, spans)
        if restored != case["text"]:
            failures.append(f"{case['id']}: roundtrip differs")
            continue

        missing = [m for m in case["must_preserve"] if m not in restored]
        if missing:
            failures.append(f"{case['id']}: missing {missing}")
            continue
        passed += 1
    return {
        "samples": len(cases),
        "passed": passed,
        "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        "failures": failures,
    }


def compare_to_baseline(current: dict, baseline: dict) -> tuple[bool, list[str]]:
    """Regression check — return (passed, reasons)."""
    reasons: list[str] = []
    ok = True

    # Detection accuracy drop
    cur_acc = current["detection"]["accuracy"]
    base_acc = baseline["detection"]["accuracy"]
    if cur_acc + ACCURACY_TOLERANCE < base_acc:
        reasons.append(
            f"detection accuracy dropped: {base_acc:.2%} → {cur_acc:.2%} "
            f"(tolerance {ACCURACY_TOLERANCE:.0%})"
        )
        ok = False

    # Preservation must never regress
    cur_pres = current["preserve"]["pass_rate"]
    base_pres = baseline["preserve"]["pass_rate"]
    if cur_pres < base_pres:
        reasons.append(
            f"preserve pass-rate dropped: {base_pres:.2%} → {cur_pres:.2%}"
        )
        ok = False

    return ok, reasons


def _load_detector():
    """Import the real detector lazily so this module is importable without
    loading models (needed for test discovery)."""
    from ..detector.ensemble import EnsembleDetector

    return EnsembleDetector()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update-baseline", action="store_true", help="Overwrite baseline.json"
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero if metrics regress past tolerance.",
    )
    args = parser.parse_args()

    print("Loading detector (this downloads/loads ~2 GB of models)...")
    detector = _load_detector()

    print("Running detection metrics...")
    detection = run_detection_metrics(detector)
    print("Running preserve metrics...")
    preserve_metrics = run_preserve_metrics()

    current = {"detection": detection, "preserve": preserve_metrics}
    print(json.dumps(current, indent=2))

    if args.update_baseline:
        BASELINE_PATH.write_text(json.dumps(current, indent=2) + "\n")
        print(f"\nBaseline updated: {BASELINE_PATH}")
        return 0

    if not BASELINE_PATH.exists():
        print(f"\nNo baseline at {BASELINE_PATH} — run --update-baseline.")
        return 0

    baseline = json.loads(BASELINE_PATH.read_text())
    ok, reasons = compare_to_baseline(current, baseline)
    if not ok:
        print("\n=== REGRESSION ===")
        for r in reasons:
            print(f"  - {r}")
        if args.fail_on_regression:
            return 1
    else:
        print("\nNo regression vs baseline.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
