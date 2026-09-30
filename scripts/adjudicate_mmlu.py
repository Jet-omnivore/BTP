"""Manual adjudication of MMLU traces whose auto-scorer could not decode a single choice.

Rule applied consistently to every trace:
  * If the model's response unambiguously commits to the gold option (explicit letter,
    or choice text that maps to the gold) -> CORRECT.
  * If the model's response commits to an option/combination that is not the single
    gold option -> WRONG.
  * If the response is truncated with no answer, or answers only a shared prefix of
    multiple options, so no confident gold mapping exists -> stays UNPARSEABLE.

Every verdict is recorded with justification in the adjudication log so the outcome
is auditable rather than assumed favorable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACES = ROOT / "data" / "traces" / "groq_mmlu_scored.jsonl"
PROBLEMS = ROOT / "data" / "processed" / "mmlu_problems.jsonl"
LOG = ROOT / "data" / "annotations" / "groq_mmlu_adjudication.jsonl"
OUTPUT = ROOT / "data" / "traces" / "groq_mmlu_scored_adjudicated.jsonl"

MARKER = re.compile(r"FINAL_ANSWER\s*:\s*([^\n]+)", re.IGNORECASE)

# trace key -> (verdict, canonical, justification)
VERDICTS: dict[tuple[str, str], tuple[str, str | None, str]] = {
    ("mmlu-006", "hi_neutral_hi"): (
        "wrong",
        "A,C,D",
        "Model explicitly answers 'A, C, D'; gold is B. Definite over-answer.",
    ),
    ("mmlu-008", "hi_none"): (
        "correct",
        "C",
        "Answer text 'sarsen, lintel' matches gold choice C ('sarsens, lintels'); reasoning names 30 upright sarsen stones + horizontal lintels.",
    ),
    ("mmlu-008", "hi_neutral_hi"): (
        "correct",
        "C",
        "No FINAL_ANSWER marker but prose ends 'the correct option is: **C**'; gold is C.",
    ),
    ("mmlu-008", "hi_planning_hi"): (
        "wrong",
        "sarsens+tholoi",
        "Answer 'sarsen, tholoi' pairs sarsens with tholoi; no such choice exists (C is sarsens+lintels, D is trilithon+tholoi). Not the gold.",
    ),
    ("mmlu-009", "hi_neutral_hi"): (
        "wrong",
        "B,C",
        "Model commits to 'B and C'; gold is the single option C. Over-answer includes B.",
    ),
    ("mmlu-010", "hi_planning_hi"): (
        "unparseable",
        None,
        "Response truncated at 60 chars mid-sentence; no answer emitted. Cannot adjudicate.",
    ),
    ("mmlu-013", "hi_neutral_hi"): (
        "unparseable",
        None,
        "Answer 'Beringia' is the shared prefix of options A and C; reasoning does not name the period. No confident gold mapping.",
    ),
    ("mmlu-029", "hi_neutral_hi"): (
        "wrong",
        "B,C",
        "Model explicitly rejects D ('all of the above') and commits to 'B and C'; gold is D.",
    ),
    ("mmlu-030", "hi_none"): (
        "wrong",
        "all",
        "Answer 'All of the above' is not a listed option and is not the single gold C.",
    ),
    ("mmlu-030", "hi_neutral_hi"): ("wrong", "B,C", "Commit 'B and C'; gold is single C."),
    ("mmlu-030", "hi_neutral_en"): ("wrong", "B,C", "Commit 'B and C'; gold is single C."),
    ("mmlu-030", "hi_planning_hi"): (
        "wrong",
        "C,D",
        "Commit 'C and D'; gold is single C. Includes gold but over-answers.",
    ),
    ("mmlu-033", "hi_planning_hi"): (
        "unparseable",
        None,
        "Response enumerates subfields then ends; no answer committed.",
    ),
}


def main() -> None:
    traces = [json.loads(line) for line in TRACES.read_text(encoding="utf-8").splitlines() if line.strip()]
    problems = {p["problem_id"]: p for p in (json.loads(l) for l in PROBLEMS.read_text(encoding="utf-8").splitlines())}
    by_key = {(t["problem_id"], t["condition_id"]): t for t in traces}

    pending = [t for t in traces if t.get("scoring_status") == "unparseable"]
    keys = {(t["problem_id"], t["condition_id"]) for t in pending}
    missing = keys - set(VERDICTS)
    if missing:
        raise ValueError(f"Missing verdicts for: {sorted(missing)}")

    log_lines: list[str] = []
    for (pid, cond), (verdict, canonical, justification) in sorted(VERDICTS.items()):
        trace = by_key[(pid, cond)]
        gold = problems[pid]["answer"]
        if verdict == "correct":
            if canonical and canonical.upper() != gold:
                raise ValueError(f"Verdict correct but canonical {canonical!r} != gold {gold!r} for {pid}")
            trace["final_answer_canonical"] = canonical or ""
            trace["is_correct"] = True
            trace["scoring_status"] = "adjudicated"
        elif verdict == "wrong":
            trace["final_answer_canonical"] = canonical or ""
            trace["is_correct"] = False
            trace["scoring_status"] = "adjudicated"
        else:
            trace["scoring_status"] = "unparseable"
        trace["adjudication"] = json.dumps({"verdict": verdict, "gold": gold, "justification": justification}, ensure_ascii=False)
        log_lines.append(
            json.dumps(
                {"problem_id": pid, "condition_id": cond, "verdict": verdict, "gold": gold, "justification": justification},
                ensure_ascii=False,
            )
        )

    OUTPUT.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + "\n", encoding="utf-8")
    LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"Adjudicated {len(VERDICTS)} traces; log -> {LOG}; scored file -> {OUTPUT}")
    print("verdict counts:", {v: sum(1 for _, (ver, *_rest) in VERDICTS.items() if ver == v) for v in ("correct", "wrong", "unparseable")})


if __name__ == "__main__":
    main()