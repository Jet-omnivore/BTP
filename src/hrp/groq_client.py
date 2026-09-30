"""Groq collection adapter for assistant-prefilled observable reasoning traces."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq, RateLimitError

from .io import read_jsonl, write_jsonl
from .schema import PRIMARY_OPERATIONS


def load_groq_client(env_file: str | Path = ".env") -> Groq:
    load_dotenv(Path(env_file))
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("API_KEY")
    if not api_key:
        raise ValueError("Neither GROQ_API_KEY nor API_KEY is set in .env.")
    return Groq(api_key=api_key)


def list_models(env_file: str | Path = ".env") -> list[str]:
    client = load_groq_client(env_file)
    return sorted(model.id for model in client.models.list().data)


def judge_annotate_tasks(
    tasks_path: str | Path,
    output_path: str | Path,
    model_id: str,
    max_completion_tokens: int,
    temperature: float,
    limit: int | None,
    env_file: str | Path,
    retry_count: int = 8,
    pace_seconds: int = 30,
    failures_path: str | Path | None = None,
    deadline_seconds: int = 240,
) -> dict[str, int]:
    """Draft primary-operation labels for blinded tasks with an LLM judge.

    Every annotation record is explicitly marked as an `llm_judge` draft. It must be
    validated on a shared human overlap before being treated as evidence. A single
    failing trace is recorded and skipped so the remaining tasks still complete.
    """
    failures_path = failures_path or f"{output_path}.failures"
    client = load_groq_client(env_file)
    tasks = read_jsonl(tasks_path)
    if limit is not None:
        tasks = tasks[:limit]
    existing = read_jsonl(output_path) if Path(output_path).exists() else []
    existing_trace_ids = {annotation["trace_id"] for annotation in existing}
    failures = read_jsonl(failures_path) if Path(failures_path).exists() else []
    failed_trace_ids = {failure["trace_id"] for failure in failures}
    annotations = list(existing)
    completed = 0
    failed = 0
    skipped = 0

    for task in tasks:
        trace_id = task["trace_id"]
        if trace_id in existing_trace_ids or trace_id in failed_trace_ids:
            skipped += 1
            continue
        try:
            steps = _judge_steps(
                client=client,
                task=task,
                model_id=model_id,
                max_completion_tokens=max_completion_tokens,
                temperature=temperature,
                retry_count=retry_count,
                deadline_seconds=deadline_seconds,
            )
        except RuntimeError as error:
            print(f"  judge failed for {trace_id}: {error}", flush=True)
            failures.append(
                {
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": str(error),
                }
            )
            write_jsonl(failures_path, failures)
            failed += 1
            continue
        annotations.extend(
            _annotation_records(task=task, steps=steps, model_id=model_id)
        )
        write_jsonl(output_path, annotations)
        completed += 1
        existing_trace_ids.add(trace_id)
        print(
            f"judge completed {completed}/{len(tasks)} (failed {failed}) -- {trace_id}",
            flush=True,
        )
        if pace_seconds:
            time.sleep(pace_seconds)
    return {"completed": completed, "failed": failed, "skipped": skipped, "total": len(tasks)}


def _judge_steps(
    client: Groq,
    task: dict[str, Any],
    model_id: str,
    max_completion_tokens: int,
    temperature: float,
    retry_count: int,
    deadline_seconds: int = 240,
) -> list[dict[str, str]]:
    last_invalid_content: str | None = None
    consecutive_rate_limits = 0
    content_attempts = 0
    deadline = time.monotonic() + deadline_seconds

    def _raise_if_past_deadline() -> None:
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"LLM judge exceeded {deadline_seconds}s deadline for {task['trace_id']}"
            )

    while content_attempts < retry_count:
        _raise_if_past_deadline()
        messages = [_judge_prompt(task["reasoning_text"])]
        if last_invalid_content:
            messages.append({"role": "assistant", "content": last_invalid_content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous answer was not valid, complete JSON with the required schema "
                        "(it may have been truncated). Return ONLY the COMPLETE JSON object "
                        "{\"steps\": [{\"step_text\": \"...\", \"primary_operation\": \"...\"}]} "
                        "using concise step_text excerpts."
                    ),
                }
            )
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
            )
        except RateLimitError as error:
            consecutive_rate_limits += 1
            if "tokens per day" in str(error) or "records per day" in str(error):
                raise RuntimeError(
                    f"LLM judge hit a daily rate limit for {task['trace_id']}: {error}"
                ) from error
            if consecutive_rate_limits > 12:
                raise RuntimeError(
                    f"LLM judge stayed rate-limited for {task['trace_id']}: {error}"
                ) from error
            remaining = max(1.0, deadline - time.monotonic())
            time.sleep(min(_rate_limit_wait(error), remaining))
            continue
        except Exception as error:
            raise RuntimeError(f"LLM judge request failed for {task['trace_id']}: {error}") from error
        consecutive_rate_limits = 0
        content_attempts += 1
        content = response.choices[0].message.content or ""
        steps = _load_steps_json(content)
        errors = _step_validation_errors(steps)
        if not errors:
            return steps
        last_invalid_content = content
        time.sleep(2)
    raise RuntimeError(
        f"LLM judge returned no valid steps for {task['trace_id']}: "
        f"{errors or 'missing JSON'} last content: {content[:200]!r}"
    )


def _rate_limit_wait(error: RateLimitError) -> float:
    match = re.search(r"Please try again in ([\d.]+)s", str(error))
    wait = float(match.group(1)) + 1 if match else 30.0
    return min(max(wait, 5.0), 120.0)


def _judge_prompt(reasoning_text: str) -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "You are labeling an observable reasoning trace for a study. Label only what is "
            "visible in the text; do not infer a hidden thought process.\n\n"
            "Valid primary operations:\n"
            "- problem_parsing: extracting quantities, entities, conditions, or unknowns from the question.\n"
            "- planning: establishing a future solution plan or intermediate goal.\n"
            "- forward_computation: deriving a result directly from known values.\n"
            "- backward_chaining: reasoning backward from a desired result to constraints.\n"
            "- case_analysis: separating mutually relevant cases or alternatives.\n"
            "- verification: checking a prior calculation, constraint, or final candidate.\n"
            "- error_detection: identifying a concrete flaw in earlier reasoning.\n"
            "- correction_backtracking: replacing an abandoned route after an identified failure.\n"
            "- answer_extraction: stating the completed answer without new derivation.\n"
            "- other: text that does not fit any primary operation.\n\n"
            "Rules:\n"
            "- Segment the trace into state-changing steps; start a new step when the state, plan, or "
            "direction changes.\n"
            "- Assign EXACTLY ONE primary operation to every step.\n"
            "- Return AT MOST 18 steps and keep every step_text to one short sentence; long "
            "verbatim quotes are not needed.\n"
            "- A statement of intention is planning; performing the calculation is forward_computation.\n"
            "- \"Let us verify\" without an actual check is other.\n"
            "- The experimental condition and final answer are intentionally withheld; do not guess them.\n\n"
            "Return ONLY a JSON object with no markdown fencing:\n"
            "{\"steps\": [{\"step_text\": \"...\", \"primary_operation\": \"forward_computation\"}]}\n"
            "Keep every step_text a concise excerpt and return the COMPLETE JSON: it must fit within "
            "the response budget with no truncation.\n\n"
            f"Trace:\n\"\"\"\n{reasoning_text}\n\"\"\""
        ),
    }


def _load_steps_json(content: str) -> list[dict[str, str]] | None:
    candidates = [content.strip()]
    if "```" in content:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            candidates.append(content[start : end + 1])
        list_start = content.find("[")
        list_end = content.rfind("]")
        if list_start != -1 and list_end > list_start:
            candidates.append(content[list_start : list_end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, list):
            steps = payload
        elif isinstance(payload, dict):
            steps = payload.get("steps") or payload.get("Steps")
        else:
            continue
        if isinstance(steps, list) and steps:
            return [
                {
                    "step_text": str(step.get("step_text", "")).strip(),
                    "primary_operation": str(step.get("primary_operation", "")).strip(),
                }
                for step in steps
            ]
    return None


def _step_validation_errors(steps: list[dict[str, str]] | None) -> list[str]:
    if not steps:
        return ["missing steps list"]
    errors: list[str] = []
    for index, step in enumerate(steps, start=1):
        if not step["step_text"].strip():
            errors.append(f"step {index}: empty step_text")
        if step["primary_operation"] not in PRIMARY_OPERATIONS:
            errors.append(f"step {index}: unknown primary_operation {step['primary_operation']!r}")
    return errors


def _annotation_records(
    task: dict[str, Any], steps: list[dict[str, str]], model_id: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        records.append(
            {
                "annotation_id": f"ann-{task['annotation_task_id']}-s{index:02d}",
                "trace_id": task["trace_id"],
                "annotator_id": "llm_judge",
                "judge_model_id": model_id,
                "step_index": index,
                "step_text": step["step_text"],
                "primary_operation": step["primary_operation"],
                "notes": "",
            }
        )
    return records


def collect_jobs(
    manifest_path: str | Path,
    output_path: str | Path,
    model_id: str,
    max_completion_tokens: int,
    temperature: float,
    limit: int | None,
    env_file: str | Path,
    retry_count: int = 3,
) -> dict[str, int]:
    """Call Groq sequentially and retain both output text and usage metadata."""
    client = load_groq_client(env_file)
    jobs = read_jsonl(manifest_path)
    if limit is not None:
        jobs = jobs[:limit]
    existing = read_jsonl(output_path) if Path(output_path).exists() else []
    existing_job_ids = {trace.get("job_id") for trace in existing}
    traces = list(existing)
    completed = 0
    skipped = 0

    for job in jobs:
        if job["job_id"] in existing_job_ids:
            skipped += 1
            continue
        response = _request_with_retry(
            client=client,
            job=job,
            model_id=model_id,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            retry_count=retry_count,
        )
        traces.append(_trace_from_response(job, response, model_id))
        write_jsonl(output_path, traces)
        completed += 1
    return {"completed": completed, "skipped": skipped, "total": len(jobs)}


def estimate_cost(
    job_count: int,
    estimated_input_tokens: int,
    max_completion_tokens: int,
    input_price_per_million: float,
    output_price_per_million: float,
) -> dict[str, float | int]:
    input_tokens = job_count * estimated_input_tokens
    output_tokens = job_count * max_completion_tokens
    input_cost = input_tokens / 1_000_000 * input_price_per_million
    output_cost = output_tokens / 1_000_000 * output_price_per_million
    return {
        "job_count": job_count,
        "estimated_input_tokens": input_tokens,
        "maximum_output_tokens": output_tokens,
        "estimated_input_cost_usd": input_cost,
        "maximum_output_cost_usd": output_cost,
        "maximum_total_cost_usd": input_cost + output_cost,
    }


def _request_with_retry(
    client: Groq,
    job: dict[str, Any],
    model_id: str,
    max_completion_tokens: int,
    temperature: float,
    retry_count: int,
) -> Any:
    messages = [
        {
            "role": "user",
            "content": (
                "Solve the following mathematics problem. Explain the solution as a sequence of clear "
                "reasoning steps. Do not use markdown tables. "
                f"{job['canonical_answer_instruction']}\n\nProblem:\n{job['problem_text']}"
            ),
        }
    ]
    if job["assistant_prefill"]:
        messages.append({"role": "assistant", "content": job["assistant_prefill"] + "\n"})

    last_error: Exception | None = None
    for attempt in range(retry_count):
        try:
            return client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
            )
        except Exception as error:  # The SDK has several provider-specific error classes.
            last_error = error
            if attempt == retry_count - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Groq request failed for {job['job_id']}: {last_error}") from last_error


def _trace_from_response(job: dict[str, Any], response: Any, model_id: str) -> dict[str, Any]:
    content = response.choices[0].message.content or ""
    # Groq appends the generated continuation after the assistant prefill. Preserve both for annotation.
    reasoning_text = f"{job['assistant_prefill']}\n{content}".strip() if job["assistant_prefill"] else content
    usage = response.usage
    return {
        "trace_id": f"trace__{job['job_id']}",
        "job_id": job["job_id"],
        "problem_id": job["problem_id"],
        "model_id": model_id,
        "condition_id": job["condition_id"],
        "input_language": job["input_language"],
        "prefill_language": job["prefill_language"],
        "prefill_strategy": job["prefill_strategy"],
        "prompt_version": job["prompt_version"],
        "reasoning_text": reasoning_text,
        "response_text": content,
        "final_answer_raw": content,
        "final_answer_canonical": "",
        "is_correct": False,
        "seed": job["seed"],
        "usage_prompt_tokens": getattr(usage, "prompt_tokens", None),
        "usage_completion_tokens": getattr(usage, "completion_tokens", None),
        "usage_total_tokens": getattr(usage, "total_tokens", None),
    }
