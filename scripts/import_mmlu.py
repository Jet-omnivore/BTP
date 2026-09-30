"""Convert the first 100 aligned EN/HI MMLU test rows into pipeline problem records."""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
MMLU_DIR = ROOT / "data" / "mmlu"
OUTPUT = ROOT / "data" / "processed" / "mmlu_problems.jsonl"

EN_FILE = MMLU_DIR / "test-00000-of-00001.parquet"
HI_FILE = MMLU_DIR / "test-00000-of-00001-hindi.parquet"
LIMIT = 100
LETTERS = [chr(ord("A") + i) for i in range(26)]


def format_question(question: str, choices: list[str]) -> str:
    lines = [question.strip()]
    for position, choice in enumerate(choices):
        lines.append(f"{LETTERS[position]}) {choice.strip()}")
    return "\n".join(lines)


def main() -> None:
    if not EN_FILE.exists() or not HI_FILE.exists():
        print(f"MMLU parquet files not found in {MMLU_DIR}", file=sys.stderr)
        raise SystemExit(1)
    en_rows = pq.read_table(EN_FILE).to_pylist()
    hi_rows = pq.read_table(HI_FILE).to_pylist()
    if len(en_rows) != len(hi_rows):
        raise ValueError(
            f"Row counts differ: EN {len(en_rows)} vs HI {len(hi_rows)}; refusing index alignment."
        )
    records = []
    for index, (en, hi) in enumerate(zip(en_rows, hi_rows[:LIMIT])):
        if index >= LIMIT:
            break
        choices = list(en["choices"])
        if len(choices) != len(hi["choices"]):
            raise ValueError(f"Row {index}: choice counts differ EN {len(choices)} vs HI {len(hi['choices'])}")
        correct_index = int(en["answer"])
        if not (0 <= correct_index < len(choices)):
            raise ValueError(f"Row {index}: answer index {correct_index} out of range")
        records.append(
            {
                "problem_id": f"mmlu-{index + 1:03d}",
                "split": "mmlu",
                "problem_en": format_question(en["question"], choices),
                "problem_hi": format_question(hi["question"], hi["choices"]),
                "answer": LETTERS[correct_index],
                "answer_index": correct_index,
                "choices": choices,
                "choices_hi": list(hi["choices"]),
                "answer_type": "multiple_choice",
                "domain": "mmlu",
                "difficulty": "medium",
                "source": "mmlu_test",
                "translation_reviewed": False,
                "translation_audit_status": "pending",
            }
        )
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(__import__("json").dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} MMLU problems to {OUTPUT}")


if __name__ == "__main__":
    main()