"""Pull the HC3 (Human ChatGPT Comparison) corpus and write a
licensed-compatible subset into samples/hc3_human.json + hc3_ai.json.

Source: Hello-SimpleAI/HC3 on Hugging Face — CC BY-SA, redistributable
with attribution.  https://huggingface.co/datasets/Hello-SimpleAI/HC3

Usage (run once on your machine, then commit the resulting JSON files):

    python -m app.eval.fetch_hc3
    python -m app.eval.runner --update-baseline   # rebuild baseline
    git add backend/app/eval/samples/hc3_*.json backend/app/eval/baseline.json
    git commit -m "eval: add HC3 corpus subset + new baseline"

Why a script instead of pulling at CI time:
  - The full corpus is ~600 MB; we don't want every CI run to re-download.
  - License compliance is cleaner if WE redistribute a frozen subset with
    attribution rather than fetching from a third-party URL each run.
  - You stay in control of how big the corpus is — bump SAMPLES_PER_SOURCE
    or change SOURCES if you want different coverage.

Defaults:
  - 50 human + 50 AI samples per source (5 sources = 250 each side total)
  - Filter: text length 200..2000 chars, ASCII-printable density > 95%
  - Deterministic random seed so re-running produces the same subset
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path
from typing import Any

# Lazy import so this script doesn't add a hard dep for the rest of the app.
try:
    from huggingface_hub import hf_hub_download
except ImportError as e:
    print(
        "Missing huggingface_hub.  It ships with `transformers` already, so:\n"
        "    pip install -r backend/requirements.txt"
    )
    raise SystemExit(1) from e

REPO = "Hello-SimpleAI/HC3"
REPO_TYPE = "dataset"
SOURCES = ("reddit_eli5", "open_qa", "wiki_csai", "medicine", "finance")
SAMPLES_PER_SOURCE = 50
MIN_LEN = 200
MAX_LEN = 2_000
SEED = 20260413  # bump if you want a different deterministic subset

OUT_DIR = Path(__file__).parent / "samples"
HUMAN_OUT = OUT_DIR / "hc3_human.json"
AI_OUT = OUT_DIR / "hc3_ai.json"

_PRINTABLE_DENSITY_RE = re.compile(r"[\x20-\x7e\n\r\t]")


def _ascii_density(text: str) -> float:
    if not text:
        return 0.0
    return len(_PRINTABLE_DENSITY_RE.findall(text)) / len(text)


def _passes_filter(text: str) -> bool:
    if not (MIN_LEN <= len(text) <= MAX_LEN):
        return False
    if _ascii_density(text) < 0.95:
        return False
    return True


def _flatten_answers(answers: Any) -> list[str]:
    """HC3 stores answers as either a string or a list of strings.  Either
    way we want a flat list of candidate texts."""
    if isinstance(answers, str):
        return [answers]
    if isinstance(answers, list):
        flat: list[str] = []
        for a in answers:
            if isinstance(a, str):
                flat.append(a)
            elif isinstance(a, list):
                flat.extend(x for x in a if isinstance(x, str))
        return flat
    return []


def _load_subset(name: str) -> list[dict]:
    """HC3 is published as parquet partitions per subset.  huggingface_hub
    downloads one file at a time so we don't pull the whole dataset."""
    path = hf_hub_download(
        repo_id=REPO,
        repo_type=REPO_TYPE,
        filename=f"{name}.jsonl",
        # Older mirrors may store as parquet — try both.
    )
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _sample_from_source(rows: list[dict], rng: random.Random) -> tuple[list[dict], list[dict]]:
    """Each row has `human_answers` + `chatgpt_answers`.  Pick one passing
    answer per row, then sample SAMPLES_PER_SOURCE per side."""
    human_pool: list[tuple[str, str]] = []  # (id, text)
    ai_pool: list[tuple[str, str]] = []

    for row in rows:
        rid = str(row.get("id") or row.get("index") or len(human_pool))
        for h in _flatten_answers(row.get("human_answers")):
            if _passes_filter(h):
                human_pool.append((rid, h))
                break
        for a in _flatten_answers(row.get("chatgpt_answers")):
            if _passes_filter(a):
                ai_pool.append((rid, a))
                break

    rng.shuffle(human_pool)
    rng.shuffle(ai_pool)
    return human_pool[:SAMPLES_PER_SOURCE], ai_pool[:SAMPLES_PER_SOURCE]


def main() -> int:
    rng = random.Random(SEED)
    human_out: list[dict] = []
    ai_out: list[dict] = []

    for source in SOURCES:
        print(f"Fetching HC3 subset: {source} ...")
        try:
            rows = _load_subset(source)
        except Exception as e:  # noqa: BLE001 — surface mirror-format issues
            print(f"  Skipped {source!r}: {e}")
            continue

        humans, ais = _sample_from_source(rows, rng)
        for rid, text in humans:
            human_out.append(
                {
                    "id": f"hc3_{source}_{rid}",
                    "source": f"HC3/{source} (CC BY-SA, Hello-SimpleAI/HC3)",
                    "text": text,
                }
            )
        for rid, text in ais:
            ai_out.append(
                {
                    "id": f"hc3_{source}_{rid}_ai",
                    "source": f"HC3/{source} ChatGPT answer (CC BY-SA, Hello-SimpleAI/HC3)",
                    "text": text,
                }
            )
        print(f"  Sampled {len(humans)} human + {len(ais)} AI from {source}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HUMAN_OUT.write_text(json.dumps(human_out, indent=2, ensure_ascii=False) + "\n")
    AI_OUT.write_text(json.dumps(ai_out, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(human_out)} human samples to {HUMAN_OUT}")
    print(f"Wrote {len(ai_out)} AI samples to {AI_OUT}")
    print("\nNext steps:")
    print("  python -m app.eval.runner --update-baseline")
    print(f"  git add {HUMAN_OUT.name} {AI_OUT.name} ../baseline.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
