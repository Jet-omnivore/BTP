"""Schemas and controlled vocabularies used throughout the study."""

from __future__ import annotations

from typing import Any

ANSWER_TYPES = {"numeric", "expression", "multiple_choice", "text"}
SPLITS = {"pilot", "development", "test", "hard", "mmlu"}
PRIMARY_OPERATIONS = {
    "problem_parsing",
    "planning",
    "forward_computation",
    "backward_chaining",
    "case_analysis",
    "verification",
    "error_detection",
    "correction_backtracking",
    "answer_extraction",
    "other",
}

PROBLEM_REQUIRED = {
    "problem_id",
    "split",
    "problem_en",
    "problem_hi",
    "answer",
    "answer_type",
    "domain",
    "difficulty",
    "source",
    "translation_reviewed",
}

TRACE_REQUIRED = {
    "trace_id",
    "problem_id",
    "model_id",
    "condition_id",
    "input_language",
    "prefill_language",
    "prefill_strategy",
    "prompt_version",
    "reasoning_text",
    "final_answer_raw",
    "final_answer_canonical",
    "is_correct",
    "seed",
}

ANNOTATION_REQUIRED = {
    "annotation_id",
    "trace_id",
    "annotator_id",
    "step_index",
    "step_text",
    "primary_operation",
}


def validate_problem(record: dict[str, Any]) -> list[str]:
    errors = _missing(record, PROBLEM_REQUIRED)
    if record.get("split") not in SPLITS:
        errors.append(f"split must be one of {sorted(SPLITS)}")
    if record.get("answer_type") not in ANSWER_TYPES:
        errors.append(f"answer_type must be one of {sorted(ANSWER_TYPES)}")
    if not isinstance(record.get("translation_reviewed"), bool):
        errors.append("translation_reviewed must be boolean")
    return errors


def validate_trace(record: dict[str, Any]) -> list[str]:
    errors = _missing(record, TRACE_REQUIRED)
    if record.get("input_language") not in {"hi", "en"}:
        errors.append("input_language must be hi or en")
    if record.get("prefill_language") not in {"hi", "en", "none"}:
        errors.append("prefill_language must be hi, en, or none")
    if record.get("prefill_strategy") not in {"none", "neutral", "planning", "verification"}:
        errors.append("prefill_strategy is not recognized")
    if not isinstance(record.get("is_correct"), bool):
        errors.append("is_correct must be boolean")
    if not isinstance(record.get("seed"), int):
        errors.append("seed must be an integer")
    return errors


def validate_annotation(record: dict[str, Any]) -> list[str]:
    errors = _missing(record, ANNOTATION_REQUIRED)
    if record.get("primary_operation") not in PRIMARY_OPERATIONS:
        errors.append(f"primary_operation must be one of {sorted(PRIMARY_OPERATIONS)}")
    if not isinstance(record.get("step_index"), int) or record.get("step_index", 0) < 1:
        errors.append("step_index must be a positive integer")
    return errors


def _missing(record: dict[str, Any], fields: set[str]) -> list[str]:
    return [f"missing required field: {field}" for field in sorted(fields - set(record))]
