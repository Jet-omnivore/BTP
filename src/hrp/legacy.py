"""Import the workspace's prior 250-item CSVs without overstating their quality."""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any


def import_legacy_pairs(
    hindi_csv: str | Path,
    english_csv: str | Path,
    pilot_size: int,
    random_seed: int,
) -> list[dict[str, Any]]:
    hindi_rows = _read_csv(hindi_csv, "utf-8-sig")
    english_rows = _read_csv(english_csv, "cp1252")
    if len(hindi_rows) != len(english_rows):
        raise ValueError(
            f"Hindi and English CSV row counts differ: {len(hindi_rows)} != {len(english_rows)}"
        )
    if pilot_size < 1 or pilot_size > len(hindi_rows):
        raise ValueError(f"pilot_size must be between 1 and {len(hindi_rows)}")

    records: list[dict[str, Any]] = []
    for index, (hindi, english) in enumerate(zip(hindi_rows, english_rows), start=1):
        answer = str(hindi["answer"]).strip()
        if not answer:
            raise ValueError(f"Hindi row {index} has an empty answer.")
        records.append(
            {
                "problem_id": f"legacy-{index:03d}",
                "split": "development",
                "problem_en": str(english["question"]).strip(),
                "problem_hi": str(hindi["problem"]).strip(),
                "answer": answer,
                "answer_type": "numeric",
                "domain": "unlabeled",
                "difficulty": "unlabeled",
                "source": "legacy_250_entries_unreviewed",
                "translation_reviewed": False,
            }
        )

    randomizer = random.Random(random_seed)
    pilot_indices = set(randomizer.sample(range(len(records)), pilot_size))
    for index, record in enumerate(records):
        if index in pilot_indices:
            record["split"] = "pilot"
    return records


def _read_csv(path: str | Path, encoding: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding=encoding) as handle:
        return list(csv.DictReader(handle))
