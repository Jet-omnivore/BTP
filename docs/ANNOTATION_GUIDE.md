# Observable Reasoning Annotation Guide

Annotate only what appears in `reasoning_text`. Do not infer an internal thought process, do not use the final answer, and assign exactly one primary operation to each state-changing step.

## Segmentation Rule

Start a new step when the trace changes the mathematical state, plan, or solution direction. Do not split a sentence only because it contains a connector such as “therefore” or “तो”. Keep a calculation and its immediate result together.

## Primary Operations

| Label | Use When | Example |
|---|---|---|
| `problem_parsing` | Extracting quantities, entities, conditions, or unknowns from the question. | “There are 3 boxes and 4 apples in each.” |
| `planning` | Establishing a future solution plan or intermediate goals. | “First find the total number of apples.” |
| `forward_computation` | Deriving a result directly from known values. | “3 × 4 = 12.” |
| `backward_chaining` | Starting from a desired result and reasoning backward to constraints. | “If the final value is 20, the earlier amount must be 10.” |
| `case_analysis` | Separating mutually relevant cases or alternatives. | “Consider whether x is even or odd.” |
| `verification` | Checking a prior calculation, constraint, or final candidate. | “Substituting 12 confirms that all apples are counted.” |
| `error_detection` | Identifying a concrete flaw in earlier reasoning. | “I counted one box twice, so 16 is incorrect.” |
| `correction_backtracking` | Replacing an abandoned route after an identified or explicit failure. | “Instead, calculate the rate per minute first.” |
| `answer_extraction` | Stating the completed answer without new derivation. | “Therefore, the answer is 12.” |
| `other` | Text that does not fit any primary operation. | “Let me think about this.” |

## Decision Rules

- A statement of intention is `planning`; performing the calculation is `forward_computation`.
- “Let us verify” without an actual check is `other`, not `verification`.
- An arithmetic correction is `error_detection` only when the previous error is explicitly identified; the replacement method is `correction_backtracking`.
- A final restatement after a derivation is `answer_extraction`.
- Hindi, English, and code-mixed traces use the same labels.

## Required Output Record

One JSONL annotation record per step:

```json
{
  "annotation_id": "ann-a01-t004-s02",
  "trace_id": "trace-004",
  "annotator_id": "annotator_a",
  "step_index": 2,
  "step_text": "पहले कुल सेब निकालते हैं: 3 × 4 = 12।",
  "primary_operation": "forward_computation",
  "notes": ""
}
```
