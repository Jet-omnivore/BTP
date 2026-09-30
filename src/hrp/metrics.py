"""Language and reasoning-operation metrics for observable model traces."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Iterable


DEVANAGARI = re.compile(r"[\u0900-\u097F]")
LATIN = re.compile(r"[A-Za-z]")
TOKEN = re.compile(r"[\u0900-\u097FA-Za-z]+")


def language_profile(text: str) -> dict[str, float | int]:
    """Estimate visible Hindi/English usage from script, without external services."""
    devanagari_count = len(DEVANAGARI.findall(text))
    latin_count = len(LATIN.findall(text))
    total_script = devanagari_count + latin_count
    tokens = [_token_language(token) for token in TOKEN.findall(text)]
    language_tokens = [token for token in tokens if token != "other"]
    switches = sum(
        current != previous
        for previous, current in zip(language_tokens, language_tokens[1:])
    )
    return {
        "devanagari_characters": devanagari_count,
        "latin_characters": latin_count,
        "hindi_script_share": _safe_divide(devanagari_count, total_script),
        "english_script_share": _safe_divide(latin_count, total_script),
        "language_token_count": len(language_tokens),
        "code_switch_count": switches,
        "code_switch_rate": _safe_divide(switches, max(len(language_tokens) - 1, 0)),
    }


def _has_explicit_answer(trace: dict[str, Any]) -> bool:
    return trace.get("scoring_status", "scored") in {"scored", "adjudicated"}


def cross_condition_agreement(traces: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Measure per-problem agreement across conditions to expose ceiling effects.

    A mainstream grade-school benchmark that a model solves almost perfectly produces
    near-identical condition accuracies. This diagnostic reports how many problems all
    conditions answered explicitly, how often they emitted the same numeric answer, and
    how often every condition was correct, so a ceiling effect is visible rather than
    misinterpreted as a real accuracy difference.
    """
    by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        by_problem[trace["problem_id"]].append(trace)

    n_complete = 0
    n_identical_answers = 0
    n_all_correct = 0
    n_any_wrong = 0
    wrong_trace_ids: list[str] = []
    for rows in by_problem.values():
        scored = [trace for trace in rows if _has_explicit_answer(trace)]
        if len(scored) == len(rows):
            n_complete += 1
            canonicals = {trace.get("final_answer_canonical") for trace in scored}
            if len(canonicals) == 1:
                n_identical_answers += 1
            if all(bool(trace["is_correct"]) for trace in scored):
                n_all_correct += 1
        wrong = [trace for trace in rows if bool(trace["is_correct"]) is False and _has_explicit_answer(trace)]
        if wrong:
            n_any_wrong += 1
            wrong_trace_ids.extend(trace["trace_id"] for trace in wrong)

    return {
        "n_problems": len(by_problem),
        "n_complete": n_complete,
        "n_incomplete": len(by_problem) - n_complete,
        "n_identical_answers": n_identical_answers,
        "n_all_correct": n_all_correct,
        "n_problems_with_any_wrong_answer": n_any_wrong,
        "wrong_trace_ids": sorted(wrong_trace_ids),
    }


def condition_summary(
    traces: Iterable[dict[str, Any]], annotations: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    trace_rows = list(traces)
    annotation_rows = list(annotations)
    operation_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for annotation in annotation_rows:
        operation_counts[annotation["trace_id"]][annotation["primary_operation"]] += 1

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in trace_rows:
        grouped[trace["condition_id"]].append(trace)

    matched_problems = _matched_problem_ids(trace_rows)
    rows: list[dict[str, Any]] = []
    for condition_id, condition_traces in sorted(grouped.items()):
        profiles = [
            language_profile(trace.get("response_text") or trace["reasoning_text"])
            for trace in condition_traces
        ]
        parseable = [
            trace for trace in condition_traces if _has_explicit_answer(trace)
        ]
        correct = sum(bool(trace["is_correct"]) for trace in parseable)
        matched = [trace for trace in parseable if trace["problem_id"] in matched_problems]
        matched_correct = sum(bool(trace["is_correct"]) for trace in matched)
        all_operations: Counter[str] = Counter()
        for trace in condition_traces:
            all_operations.update(operation_counts[trace["trace_id"]])
        n = len(condition_traces)
        first = condition_traces[0]
        row: dict[str, Any] = {
            "condition_id": condition_id,
            "input_language": first["input_language"],
            "prefill_language": first["prefill_language"],
            "prefill_strategy": first["prefill_strategy"],
            "n_traces": n,
            "n_correct": correct,
            "n_wrong_answers": len(parseable) - correct,
            "n_parseable_answers": len(parseable),
            "n_unparseable": n - len(parseable),
            "answer_parse_rate": _safe_divide(len(parseable), n),
            "n_matched_problems": len(matched),
            "n_matched_correct": matched_correct,
            "matched_accuracy": _safe_divide(matched_correct, len(matched)),
            "matched_accuracy_ci_low": wilson_interval(matched_correct, len(matched))[0],
            "matched_accuracy_ci_high": wilson_interval(matched_correct, len(matched))[1],
            "accuracy": _safe_divide(correct, len(parseable)),
            "accuracy_ci_low": wilson_interval(correct, len(parseable))[0],
            "accuracy_ci_high": wilson_interval(correct, len(parseable))[1],
            "mean_hindi_script_share": _mean(profile["hindi_script_share"] for profile in profiles),
            "mean_english_script_share": _mean(profile["english_script_share"] for profile in profiles),
            "mean_code_switch_rate": _mean(profile["code_switch_rate"] for profile in profiles),
            "annotated_steps": sum(all_operations.values()),
        }
        for operation, count in all_operations.items():
            row[f"operation_{operation}"] = count
            row[f"operation_rate_{operation}"] = _safe_divide(count, row["annotated_steps"])
        rows.append(row)
    return rows


def _matched_problem_ids(trace_rows: list[dict[str, Any]]) -> set[str]:
    """Problems where every condition produced an explicit answer.

    Restricting accuracy to this set makes condition denominators identical, so a
    truncation in one condition can no longer silently inflate another condition's
    accuracy (the artifact that made hi_neutral_hi look better than hi_neutral_en).
    """
    by_problem: dict[str, set[str]] = defaultdict(set)
    by_problem_answered: dict[str, set[str]] = defaultdict(set)
    for trace in trace_rows:
        by_problem[trace["problem_id"]].add(trace["condition_id"])
        if _has_explicit_answer(trace):
            by_problem_answered[trace["problem_id"]].add(trace["condition_id"])
    return {
        problem_id
        for problem_id, conditions in by_problem.items()
        if by_problem_answered[problem_id] == conditions
    }


def paired_condition_differences(traces: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return per-problem outcome differences for every comparable condition pair.

    Only traces with an explicit parseable final answer are compared, so a truncated
    trace is treated as missing evidence rather than as a wrong answer.
    """
    by_problem: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for trace in traces:
        if not _has_explicit_answer(trace):
            continue
        existing = by_problem[trace["problem_id"]].get(trace["condition_id"])
        if existing is None or trace["seed"] < existing["seed"]:
            by_problem[trace["problem_id"]][trace["condition_id"]] = trace

    pairs: dict[tuple[str, str], list[int]] = defaultdict(list)
    for traces_by_condition in by_problem.values():
        condition_ids = sorted(traces_by_condition)
        for index, left in enumerate(condition_ids):
            for right in condition_ids[index + 1 :]:
                pairs[(left, right)].append(
                    int(traces_by_condition[right]["is_correct"])
                    - int(traces_by_condition[left]["is_correct"])
                )

    return [
        {
            "condition_a": left,
            "condition_b": right,
            "n_paired_problems": len(differences),
            "accuracy_difference_b_minus_a": _mean(differences),
            "b_only_correct": sum(value == 1 for value in differences),
            "a_only_correct": sum(value == -1 for value in differences),
            "mcnemar_p_value": _mcnemar_exact_p(
                b_only_correct=sum(value == 1 for value in differences),
                a_only_correct=sum(value == -1 for value in differences),
            ),
        }
        for (left, right), differences in sorted(pairs.items())
    ]


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt((proportion * (1 - proportion) + z**2 / (4 * total)) / total) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _mcnemar_exact_p(b_only_correct: int, a_only_correct: int) -> float:
    """Two-sided exact McNemar p-value on discordant pair counts.

    With N = b_only_correct + a_only_correct discordant problems, each problem
    is equally likely to land on either side by chance. The exact p-value is
    twice the binomial tail below the smaller discordant count (capped at 1.0).
    """
    b, a = b_only_correct, a_only_correct
    if b == 0 and a == 0:
        return 1.0
    total = b + a
    smaller = min(b, a)
    from math import comb
    p = sum(comb(total, k) for k in range(smaller + 1)) / (2**total)
    return min(2 * p, 1.0)


def _token_language(token: str) -> str:
    if DEVANAGARI.search(token):
        return "hi"
    if LATIN.search(token):
        return "en"
    return "other"


def _safe_divide(numerator: float | int, denominator: float | int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _mean(values: Iterable[float | int]) -> float:
    values = list(values)
    return float(sum(values) / len(values)) if values else 0.0
