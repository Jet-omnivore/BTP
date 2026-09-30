"""Build an English-input control manifest (en_none) for the collected MMLU problems.

Only the problems already collected in the Hindi-input conditions are included, so the
English control is directly paired with the existing four condition rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hrp.io import read_jsonl, write_jsonl  # noqa: E402

PROBLEMS = ROOT / "data" / "processed" / "mmlu_problems.jsonl"
SCORED = ROOT / "data" / "traces" / "groq_mmlu_scored.jsonl"
CONFIG = ROOT / "config" / "experiment.json"
OUTPUT = ROOT / "data" / "processed" / "mmlu_en_manifest.jsonl"

EN_NONE_CONDITION = "en_none"


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    try:
        condition = next(c for c in config["conditions"] if c["condition_id"] == EN_NONE_CONDITION)
    except StopIteration:
        raise SystemExit(f"Config has no condition {EN_NONE_CONDITION!r}")
    problems = {p["problem_id"]: p for p in read_jsonl(PROBLEMS)}
    collected = {trace["problem_id"] for trace in read_jsonl(SCORED)}
    missing = sorted(collected - set(problems))
    if missing:
        raise SystemExit(f"Collected traces refer to unknown problems: {missing[:5]}")
    jobs: list[dict] = []
    for problem_id in sorted(collected):
        problem = problems[problem_id]
        jobs.append(
            {
                "job_id": f"{problem_id}__{EN_NONE_CONDITION}__seed-0",
                "problem_id": problem_id,
                "condition_id": EN_NONE_CONDITION,
                "input_language": condition["input_language"],
                "prefill_language": condition["prefill_language"],
                "prefill_strategy": condition["prefill_strategy"],
                "assistant_prefill": condition["assistant_prefill"],
                "problem_text": problem["problem_en"],
                "canonical_answer_instruction": config["canonical_answer_instruction"],
                "prompt_version": config["prompt_version"],
                "seed": 0,
            }
        )
    write_jsonl(OUTPUT, jobs)
    print(f"Wrote {len(jobs)} en_none jobs ({len(collected)} problems) to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())