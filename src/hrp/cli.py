"""Command-line interface for preparing and analyzing study artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from .io import read_json, read_jsonl, write_json, write_jsonl
from .answers import canonicalize_numeric_answer, numeric_answers_match, canonicalize_choice_answer, choice_answers_match
from .groq_client import collect_jobs, estimate_cost, judge_annotate_tasks, list_models
from .legacy import import_legacy_pairs
from .metrics import condition_summary, cross_condition_agreement, paired_condition_differences
from .plotting import create_figures
from .showcase import create_showcase_figures
from .schema import (
    ANNOTATION_REQUIRED,
    PRIMARY_OPERATIONS,
    validate_annotation,
    validate_problem,
    validate_trace,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hindi Reasoning Prefills study tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_validation_parser(subparsers, "validate-dataset", "Validate bilingual problem records.", validate_problem)
    _add_validation_parser(subparsers, "validate-traces", "Validate generated model traces.", validate_trace)
    _add_validation_parser(subparsers, "validate-annotations", "Validate primary-operation annotations.", validate_annotation)

    legacy = subparsers.add_parser("import-legacy-pilot", help="Import the unreviewed legacy 250-item CSV source.")
    legacy.add_argument("--hindi-csv", required=True)
    legacy.add_argument("--english-csv", required=True)
    legacy.add_argument("--output", required=True)
    legacy.add_argument("--pilot-size", type=int, default=100)
    legacy.add_argument("--random-seed", type=int, default=2026)

    audit = subparsers.add_parser("make-translation-audit", help="Create a CSV review sheet for bilingual problems.")
    audit.add_argument("--problems", required=True)
    audit.add_argument("--output", required=True)
    audit.add_argument("--split", choices=["pilot", "development", "test", "hard", "mmlu"], required=True)
    audit.add_argument(
        "--initial-status",
        choices=["approved", "revision_needed", "invalid", "pending"],
        default="pending",
        help="Use only when a reviewer has already approved or rejected every selected item.",
    )

    apply_audit = subparsers.add_parser("apply-translation-audit", help="Record Hindi review outcomes in problem provenance.")
    apply_audit.add_argument("--problems", required=True)
    apply_audit.add_argument("--audit", required=True)
    apply_audit.add_argument("--output", required=True)

    score = subparsers.add_parser("score-traces", help="Score numeric trace answers against the paired problem set.")
    score.add_argument("--traces", required=True)
    score.add_argument("--problems", required=True)
    score.add_argument("--output", required=True)

    models = subparsers.add_parser("groq-list-models", help="List models accessible to the configured Groq key.")
    models.add_argument("--env-file", default=".env")

    estimate = subparsers.add_parser("estimate-cost", help="Calculate a conservative maximum collection cost.")
    estimate.add_argument("--manifest", required=True)
    estimate.add_argument("--estimated-input-tokens", type=int, default=350)
    estimate.add_argument("--max-completion-tokens", type=int, default=1024)
    estimate.add_argument("--input-price-per-million", type=float, required=True)
    estimate.add_argument("--output-price-per-million", type=float, required=True)

    collect = subparsers.add_parser("collect-groq", help="Collect assistant-prefilled traces through Groq.")
    collect.add_argument("--manifest", required=True)
    collect.add_argument("--output", required=True)
    collect.add_argument("--model", required=True)
    collect.add_argument("--max-completion-tokens", type=int, default=1024)
    collect.add_argument("--temperature", type=float, default=0.2)
    collect.add_argument("--limit", type=int)
    collect.add_argument("--env-file", default=".env")

    judge = subparsers.add_parser("judge-annotate", help="Draft primary-operation labels with an LLM judge.")
    judge.add_argument("--tasks", required=True)
    judge.add_argument("--output", required=True)
    judge.add_argument("--model", required=True)
    judge.add_argument("--max-completion-tokens", type=int, default=2048)
    judge.add_argument("--temperature", type=float, default=0.0)
    judge.add_argument("--limit", type=int)
    judge.add_argument("--pace-seconds", type=int, default=40)
    judge.add_argument("--retry-count", type=int, default=10)
    judge.add_argument("--deadline-seconds", type=int, default=240)
    judge.add_argument("--failures", default=None)
    judge.add_argument("--env-file", default=".env")

    manifest = subparsers.add_parser("build-manifest", help="Create model-run jobs without calling a model.")
    manifest.add_argument("--problems", required=True)
    manifest.add_argument("--config", required=True)
    manifest.add_argument("--output", required=True)
    manifest.add_argument("--stage", choices=["pilot", "final", "hard", "mmlu"], required=True)
    manifest.add_argument("--seeds", type=int, default=1, help="Number of decoding seeds per problem-condition pair.")

    tasks = subparsers.add_parser("make-annotation-tasks", help="Create blinded manual annotation tasks.")
    tasks.add_argument("--traces", required=True)
    tasks.add_argument("--output", required=True)
    tasks.add_argument("--limit", type=int, required=True)
    tasks.add_argument("--random-seed", type=int, default=2026)

    analyze = subparsers.add_parser("analyze", help="Write tables, figures, and a presentation summary.")
    analyze.add_argument("--traces", required=True)
    analyze.add_argument("--annotations", required=True)
    analyze.add_argument(
        "--exclude-problems",
        help="Optional JSONL registry of problem IDs excluded from all analysis metrics.",
    )
    analyze.add_argument("--output-dir", required=True)
    analyze.add_argument(
        "--answer-type",
        choices=["numeric", "multiple_choice"],
        default="numeric",
        help="Wording in the written summary; multiple_choice is used for the MMLU run.",
    )

    showcase = subparsers.add_parser(
        "showcase",
        help="Generate showcase bar/pie/heatmap figures from an analyzed summary directory.",
    )
    showcase.add_argument("--output-dir", required=True)

    arguments = parser.parse_args()
    if arguments.command.startswith("validate-"):
        _validate_file(arguments.input, arguments.validator)
    elif arguments.command == "import-legacy-pilot":
        _import_legacy_pilot(arguments)
    elif arguments.command == "make-translation-audit":
        _make_translation_audit(arguments)
    elif arguments.command == "apply-translation-audit":
        _apply_translation_audit(arguments)
    elif arguments.command == "score-traces":
        _score_traces(arguments)
    elif arguments.command == "groq-list-models":
        for model_id in list_models(arguments.env_file):
            print(model_id)
    elif arguments.command == "estimate-cost":
        _estimate_cost(arguments)
    elif arguments.command == "collect-groq":
        _collect_groq(arguments)
    elif arguments.command == "judge-annotate":
        _judge_annotate(arguments)
    elif arguments.command == "build-manifest":
        _build_manifest(arguments)
    elif arguments.command == "make-annotation-tasks":
        _make_annotation_tasks(arguments)
    elif arguments.command == "analyze":
        _analyze(arguments)
    elif arguments.command == "showcase":
        _showcase(arguments)


def _add_validation_parser(
    subparsers: argparse._SubParsersAction,
    name: str,
    help_text: str,
    validator: Callable[[dict[str, Any]], list[str]],
) -> None:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("--input", required=True)
    parser.set_defaults(validator=validator)


def _validate_file(path: str, validator: Callable[[dict[str, Any]], list[str]]) -> None:
    records = read_jsonl(path)
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        for error in validator(record):
            errors.append(f"record {index}: {error}")
    _validate_unique_ids(records, errors)
    if errors:
        print("Validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Validation passed: {len(records)} records in {path}")


def _validate_unique_ids(records: list[dict[str, Any]], errors: list[str]) -> None:
    identifier = None
    if records and all("annotation_id" in record for record in records):
        identifier = "annotation_id"
    elif records and all("trace_id" in record for record in records):
        identifier = "trace_id"
    elif records and all("problem_id" in record for record in records):
        identifier = "problem_id"
    if identifier is None:
        return
    values = [record[identifier] for record in records]
    duplicates = [value for value, count in Counter(values).items() if count > 1]
    if duplicates:
        errors.append(f"duplicate {identifier}: {', '.join(map(str, duplicates[:5]))}")


def _build_manifest(arguments: argparse.Namespace) -> None:
    problems = read_jsonl(arguments.problems)
    config = read_json(arguments.config)
    selected_ids = set(config["stages"][arguments.stage])
    conditions = [condition for condition in config["conditions"] if condition["condition_id"] in selected_ids]
    if len(conditions) != len(selected_ids):
        raise ValueError("The requested stage refers to unknown condition IDs.")
    jobs: list[dict[str, Any]] = []
    for problem in problems:
        if problem["split"] != arguments.stage:
            continue
        for condition in conditions:
            problem_text = problem["problem_hi"] if condition["input_language"] == "hi" else problem["problem_en"]
            for seed in range(arguments.seeds):
                jobs.append(
                    {
                        "job_id": f"{problem['problem_id']}__{condition['condition_id']}__seed-{seed}",
                        "problem_id": problem["problem_id"],
                        "condition_id": condition["condition_id"],
                        "input_language": condition["input_language"],
                        "prefill_language": condition["prefill_language"],
                        "prefill_strategy": condition["prefill_strategy"],
                        "assistant_prefill": condition["assistant_prefill"],
                        "problem_text": problem_text,
                        "canonical_answer_instruction": config["canonical_answer_instruction"],
                        "prompt_version": config["prompt_version"],
                        "seed": seed,
                    }
                )
    if not jobs:
        raise ValueError(f"No problems with split={arguments.stage!r} were found.")
    write_jsonl(arguments.output, jobs)
    print(f"Wrote {len(jobs)} model-run jobs to {arguments.output}")


def _import_legacy_pilot(arguments: argparse.Namespace) -> None:
    records = import_legacy_pairs(
        hindi_csv=arguments.hindi_csv,
        english_csv=arguments.english_csv,
        pilot_size=arguments.pilot_size,
        random_seed=arguments.random_seed,
    )
    write_jsonl(arguments.output, records)
    print(
        f"Imported {len(records)} legacy records; {arguments.pilot_size} are assigned to the pilot split. "
        "All records remain marked as unreviewed translations."
    )


def _make_translation_audit(arguments: argparse.Namespace) -> None:
    problems = read_jsonl(arguments.problems)
    selected = [problem for problem in problems if problem["split"] == arguments.split]
    if not selected:
        raise ValueError(f"No records found for split={arguments.split!r}")
    rows = [
        {
            "problem_id": problem["problem_id"],
            "problem_en": problem["problem_en"],
            "problem_hi": problem["problem_hi"],
            "answer": problem["answer"],
            "review_status": arguments.initial_status,
            "reviewer_notes": "",
        }
        for problem in selected
    ]
    _write_csv(Path(arguments.output), rows)
    print(f"Wrote {len(rows)} translation-audit rows to {arguments.output}")


def _apply_translation_audit(arguments: argparse.Namespace) -> None:
    problems = read_jsonl(arguments.problems)
    with Path(arguments.audit).open(newline="", encoding="utf-8") as handle:
        reviews = list(csv.DictReader(handle))
    required_columns = {"problem_id", "review_status", "reviewer_notes"}
    if not reviews or not required_columns.issubset(reviews[0]):
        raise ValueError(f"Audit CSV must contain columns: {sorted(required_columns)}")
    allowed_statuses = {"approved", "revision_needed", "invalid", "pending"}
    review_by_id = {review["problem_id"]: review for review in reviews}
    invalid_statuses = sorted(
        {review["review_status"].strip() for review in reviews} - allowed_statuses
    )
    if invalid_statuses:
        raise ValueError(f"Unknown review_status values: {', '.join(invalid_statuses)}")
    for problem in problems:
        review = review_by_id.get(problem["problem_id"])
        if not review:
            continue
        status = review["review_status"].strip()
        problem["translation_reviewed"] = status == "approved"
        problem["translation_audit_status"] = status
        if review["reviewer_notes"].strip():
            problem["translation_audit_notes"] = review["reviewer_notes"].strip()
    write_jsonl(arguments.output, problems)
    counts = Counter(review["review_status"].strip() for review in reviews)
    print(f"Wrote reviewed provenance to {arguments.output}: {dict(sorted(counts.items()))}")


def _score_traces(arguments: argparse.Namespace) -> None:
    traces = read_jsonl(arguments.traces)
    problems = {problem["problem_id"]: problem for problem in read_jsonl(arguments.problems)}
    missing_problems = sorted({trace["problem_id"] for trace in traces} - set(problems))
    if missing_problems:
        raise ValueError(f"Traces refer to unknown problems: {', '.join(missing_problems[:5])}")
    for trace in traces:
        problem = problems[trace["problem_id"]]
        raw_answer = trace.get("final_answer_raw") or trace.get("response_text", "")
        if problem["answer_type"] == "numeric":
            canonical = canonicalize_numeric_answer(raw_answer)
            is_correct = numeric_answers_match(canonical, problem["answer"])
        elif problem["answer_type"] == "multiple_choice":
            en_match = canonicalize_choice_answer(raw_answer, problem.get("choices") or [])
            hi_match = canonicalize_choice_answer(raw_answer, problem.get("choices_hi") or [])
            if en_match and hi_match and en_match != hi_match:
                canonical = None
            else:
                canonical = hi_match or en_match
            is_correct = choice_answers_match(canonical, problem["answer"]) if canonical is not None else False
        else:
            raise ValueError(f"Scorer does not support {problem['answer_type']!r} answers yet.")
        trace["final_answer_raw"] = raw_answer
        trace["final_answer_canonical"] = canonical or ""
        trace["is_correct"] = is_correct
        trace["scoring_status"] = "scored" if canonical is not None else "unparseable"
    write_jsonl(arguments.output, traces)
    scored = sum(trace["scoring_status"] == "scored" for trace in traces)
    print(f"Scored {len(traces)} traces; {scored} had an explicit parseable FINAL_ANSWER marker.")


def _estimate_cost(arguments: argparse.Namespace) -> None:
    estimate = estimate_cost(
        job_count=len(read_jsonl(arguments.manifest)),
        estimated_input_tokens=arguments.estimated_input_tokens,
        max_completion_tokens=arguments.max_completion_tokens,
        input_price_per_million=arguments.input_price_per_million,
        output_price_per_million=arguments.output_price_per_million,
    )
    print(json.dumps(estimate, indent=2))


def _collect_groq(arguments: argparse.Namespace) -> None:
    result = collect_jobs(
        manifest_path=arguments.manifest,
        output_path=arguments.output,
        model_id=arguments.model,
        max_completion_tokens=arguments.max_completion_tokens,
        temperature=arguments.temperature,
        limit=arguments.limit,
        env_file=arguments.env_file,
    )
    print(f"Groq collection complete: {result}")


def _judge_annotate(arguments: argparse.Namespace) -> None:
    result = judge_annotate_tasks(
        tasks_path=arguments.tasks,
        output_path=arguments.output,
        model_id=arguments.model,
        max_completion_tokens=arguments.max_completion_tokens,
        temperature=arguments.temperature,
        limit=arguments.limit,
        env_file=arguments.env_file,
        pace_seconds=arguments.pace_seconds,
        retry_count=arguments.retry_count,
        failures_path=arguments.failures,
        deadline_seconds=arguments.deadline_seconds,
    )
    print(f"LLM-judge annotation complete: {result}")


def _make_annotation_tasks(arguments: argparse.Namespace) -> None:
    traces = read_jsonl(arguments.traces)
    if arguments.limit > len(traces):
        raise ValueError(f"Requested {arguments.limit} tasks but only {len(traces)} traces are available.")
    randomizer = random.Random(arguments.random_seed)
    selected = randomizer.sample(traces, arguments.limit)
    taxonomy = sorted(PRIMARY_OPERATIONS)
    tasks = [
        {
            "annotation_task_id": f"task-{index:04d}",
            "trace_id": trace["trace_id"],
            "problem_id": trace["problem_id"],
            "input_language": trace["input_language"],
            "reasoning_text": trace["reasoning_text"],
            "taxonomy": taxonomy,
            "instructions": (
                "Segment this observable reasoning text into state-changing steps. "
                "Assign exactly one primary operation to every step. Do not infer hidden reasoning. "
                "The final answer and experimental condition are intentionally withheld."
            ),
        }
        for index, trace in enumerate(selected, start=1)
    ]
    write_jsonl(arguments.output, tasks)
    print(f"Wrote {len(tasks)} blinded annotation tasks to {arguments.output}")


def _analyze(arguments: argparse.Namespace) -> None:
    traces = read_jsonl(arguments.traces)
    annotations = read_jsonl(arguments.annotations)
    excluded_problem_ids = _read_excluded_problem_ids(arguments.exclude_problems)
    known_problem_ids = {trace["problem_id"] for trace in traces}
    unknown_problem_ids = sorted(excluded_problem_ids - known_problem_ids)
    if unknown_problem_ids:
        raise ValueError(f"Exclusion registry refers to unknown problems: {', '.join(unknown_problem_ids[:5])}")
    if excluded_problem_ids:
        traces = [trace for trace in traces if trace["problem_id"] not in excluded_problem_ids]
        trace_ids = {trace["trace_id"] for trace in traces}
        annotations = [annotation for annotation in annotations if annotation["trace_id"] in trace_ids]
    output_dir = Path(arguments.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _check_annotation_trace_links(traces, annotations)

    summary = condition_summary(traces, annotations)
    paired = paired_condition_differences(traces)
    agreement = cross_condition_agreement(traces)
    write_json(
        output_dir / "summary.json",
        {
            "conditions": summary,
            "cross_condition_agreement": agreement,
            "excluded_problem_ids": sorted(excluded_problem_ids),
            "paired_differences": paired,
        },
    )
    _write_csv(output_dir / "condition_summary.csv", summary)
    _write_csv(output_dir / "paired_differences.csv", paired)
    figures = create_figures(summary, output_dir / "figures")
    _write_markdown_summary(
        output_dir / "midsem_summary.md", summary, paired, agreement, figures, sorted(excluded_problem_ids), arguments.answer_type
    )
    print(f"Analysis complete. Tables, figures, and summary are in {output_dir}")


def _showcase(arguments: argparse.Namespace) -> None:
    output_dir = Path(arguments.output_dir)
    summary_path = output_dir / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"No summary.json found in {output_dir}. Run analyze first.")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))["conditions"]
    figures = create_showcase_figures(summary, output_dir / "showcase")
    print(f"Showcase figures ({len(figures)}) written to {output_dir}/showcase")


def _read_excluded_problem_ids(path: str | None) -> set[str]:
    if path is None:
        return set()
    records = read_jsonl(path)
    missing = [index + 1 for index, record in enumerate(records) if not record.get("problem_id")]
    if missing:
        raise ValueError(f"Exclusion registry has records without problem_id at lines: {missing[:5]}")
    return {record["problem_id"] for record in records}


def _check_annotation_trace_links(traces: list[dict[str, Any]], annotations: list[dict[str, Any]]) -> None:
    trace_ids = {trace["trace_id"] for trace in traces}
    unknown = sorted({annotation["trace_id"] for annotation in annotations} - trace_ids)
    if unknown:
        raise ValueError(f"Annotations refer to unknown trace IDs: {', '.join(unknown[:5])}")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown_summary(
    path: Path,
    summary: list[dict[str, Any]],
    paired: list[dict[str, Any]],
    agreement: dict[str, Any],
    figures: list[Path],
    excluded_problem_ids: list[str],
    answer_type: str = "numeric",
) -> None:
    answer_noun = "numeric answer" if answer_type == "numeric" else "option answer"
    report_title = "Pilot Summary" if answer_type == "numeric" else "Condition Summary (Multiple Choice)"
    lines = [
        f"# Hindi Reasoning Prefills: {report_title}",
        "",
        "This report describes observable model outputs. It does not establish access to hidden reasoning.",
        "",
    ]
    if excluded_problem_ids:
        lines.extend(
            [
                "## Evaluation Scope",
                "",
                f"- Excluded {len(excluded_problem_ids)} problem(s) from all metrics because their Hindi prompt, source wording, or gold answer does not support a fair single-number exact-match score.",
                f"- Excluded problem IDs: {', '.join(excluded_problem_ids)}.",
                "",
            ]
        )
    lines.extend(
        [
        "## Condition Results",
        "",
        "| Condition | N | Matched accuracy | Matched (correct/total) | Parse rate | Hindi script share | Code-switch rate | Annotated steps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary:
        lines.append(
            f"| {row['condition_id']} | {row['n_traces']} | {row['matched_accuracy']:.1%} | "
            f"{row['n_matched_correct']}/{row['n_matched_problems']} | "
            f"{row['answer_parse_rate']:.1%} | "
            f"{row['mean_hindi_script_share']:.1%} | {row['mean_code_switch_rate']:.1%} | "
            f"{row['annotated_steps']} |"
        )
    lines.extend(["", "## Paired Accuracy Differences", "", "| A | B | N | B - A | p (McNemar) |", "|---|---|---:|---:|---:|"])
    for row in paired:
        lines.append(
            f"| {row['condition_a']} | {row['condition_b']} | {row['n_paired_problems']} | "
            f"{row['accuracy_difference_b_minus_a']:+.1%} | {row['mcnemar_p_value']:.3f} |"
        )
    lines.extend(
        [
            "",
            "p-values come from the two-sided exact McNemar test on discordant problem pairs; "
            "values above 0.05 mean the accuracy difference is not statistically distinguishable from chance.",
            "",
            "## Cross-Condition Answer Agreement",
            "",
            f"- {agreement['n_complete']} of {agreement['n_problems']} problems were answered explicitly in every condition.",
            f"- In all {agreement['n_identical_answers']} of those complete problems, every condition produced the same {answer_noun}.",
            f"- In all {agreement['n_all_correct']} of those complete problems, every condition was correct.",
            f"- Only {agreement['n_problems_with_any_wrong_answer']} problem(s) had a wrong explicit answer in any condition.",
            "",
            "**Matched accuracy** scores only problems where every condition produced an explicit `FINAL_ANSWER`, so "
            "every condition is evaluated on the identical problem set. This removes the artifact where a truncation "
            "in one condition changes another condition's denominator.",
            "",
            "## Method Notes",
            "",
            "- Language shares measure the model continuation only (`response_text`); the authored prefill is excluded.",
            "- Matched accuracy and paired differences use only problems with an explicit parseable `FINAL_ANSWER` in every compared condition.",
            "- A trace that reaches the completion cap before its answer marker counts toward the parse rate, not toward correctness.",
            "- Paired rows show N equal to the number of problems where both conditions supplied an explicit answer.",
        ]
    )
    lines.extend(["", "## Figures", ""])
    lines.extend(f"- `{figure.name}`" for figure in figures)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
