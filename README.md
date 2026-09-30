# Hindi Reasoning Prefills

Reproducible pipeline for studying whether Hindi reasoning prefills change an LRM's observable reasoning strategies and mathematical accuracy.

## Research Design

The experiment separates input language, prefill language, prefill strategy, observable reasoning behavior, and final-answer accuracy.

Pilot conditions are configured in `config/experiment.json`:

- Hindi input, no prefill.
- Hindi input, neutral Hindi prefill.
- Hindi input, neutral English prefill.
- Hindi input, Hindi planning prefill.

The final study can enable additional English-input and verification-prefill controls already present in the configuration.

### Why These Prefill Strings

The prefills are fixed, human-written constant strings in `config/experiment.json`, not sampled tokens or model output. They are full assistant messages that Groq continues, and each Hindi version is a human translation of the structurally matching English version:

- `hi_none` / `en_none`: no assistant prefill.
- `hi_neutral_hi`: "ठीक है, मैं इस समस्या को चरणों में हल करता हूँ।"
- `hi_neutral_en`: "Okay, I will solve this problem step by step."
- `hi_planning_hi`: "पहले समस्या को छोटे उप-लक्ष्यों में बाँटते हैं।"
- `hi_planning_en`: "First, let us break the problem into smaller subgoals."

Holding the Hindi/English wording structure constant across strategies isolates the **language** effect (Hindi vs English prefill) from the **strategy** effect (neutral vs planning vs verification).

## Data Contract

Place audited problem records in `data/processed/problems.jsonl`, one JSON object per line:

```json
{
  "problem_id": "pilot-001",
  "split": "pilot",
  "problem_en": "A shop has 3 boxes with 4 apples each. How many apples are there?",
  "problem_hi": "एक दुकान में 3 डिब्बे हैं और हर डिब्बे में 4 सेब हैं। कुल कितने सेब हैं?",
  "answer": "12",
  "answer_type": "numeric",
  "domain": "arithmetic",
  "difficulty": "easy",
  "source": "human_authored",
  "translation_reviewed": true
}
```

Do not place chain-of-thought reference answers in this dataset. The study evaluates generated traces, not provided gold traces.

### Legacy 250-Item Pilot Source

The workspace's existing `../250_entries/final_dataset.csv` and `../250_entries/en_explained.csv` can be used for the midsem pilot. Import it with:

```bash
PYTHONPATH=src python -m hrp.cli import-legacy-pilot \
  --hindi-csv ../250_entries/final_dataset.csv \
  --english-csv ../250_entries/en_explained.csv \
  --output data/processed/problems.jsonl \
  --pilot-size 100
```

The importer marks every record as `translation_reviewed: false` and `source: legacy_250_entries_unreviewed`. The generated pilot is suitable for engineering validation and preliminary midsem figures until its translation audit is completed.

Create your 100-item Hindi review sheet with:

```bash
PYTHONPATH=src python -m hrp.cli make-translation-audit \
  --problems data/processed/problems.jsonl \
  --output data/annotations/pilot_translation_audit.csv \
  --split pilot
```

For each row, set `review_status` to `approved`, `revision_needed`, or `invalid`, and add a short note when it is not approved. Then update the dataset provenance:

```bash
PYTHONPATH=src python -m hrp.cli apply-translation-audit \
  --problems data/processed/problems.jsonl \
  --audit data/annotations/pilot_translation_audit.csv \
  --output data/processed/problems_reviewed.jsonl
```

Model traces are stored in `data/traces/traces.jsonl`. Each trace includes the generated reasoning, final answer, experimental condition, model metadata, and correctness. The exact schema is in `src/hrp/schema.py`.

### What Each Artifact Represents

- **Raw trace** (`groq_pilot_raw.jsonl`): one record per real model call. `reasoning_text` is the complete text for annotation (`prefill + model continuation`). `response_text` is only the model continuation. `final_answer_canonical` is still blank and `scoring_status` is absent until the `score-traces` step runs.
- **Scored trace** (`groq_pilot_scored.jsonl`): the `score-traces` command adds `final_answer_canonical` (the parsed numeric value, or `""` when there is no explicit `FINAL_ANSWER:` line with exactly one numeric value), `is_correct` (numeric equality with the gold answer), and `scoring_status` (`scored` or `unparseable`). The numeric parser accepts Hindi digits and Hindi words or units after the marker; for example, `FINAL_ANSWER: उत्तर ७२ रुपये` parses as `72`.
- **Language metrics**: measured only on `response_text`, so the authored prefill never inflates the Hindi/English script shares.
- **Accuracy**: always paired with the parse rate. Accuracy and paired differences are computed only over traces with an explicit answer; a trace truncated by the completion cap is `unparseable`, never "wrong".
- **Evaluation exclusions** (`data/processed/pilot_scoring_exclusions.jsonl`): records pilot problems whose Hindi prompt, source wording, or gold answer cannot support a fair single-number exact-match score. Raw and scored traces remain unchanged; pass this registry to `analyze` to create an evaluation-valid report.
- **Operation classification**: derived from blinded annotation tasks. The current LLM-judge labels are a draft and require human-overlap validation before supporting substantive strategy claims.

## Setup

```bash
cd hindi_reasoning_prefills
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For Groq, create `.env` from `.env.example` and set `GROQ_API_KEY`. Existing `.env` files using `API_KEY` are also supported. The key file is ignored by Git.

## Workflow

```bash
# 1. Validate the audited bilingual benchmark.
PYTHONPATH=src python -m hrp.cli validate-dataset \
  --input data/processed/problems.jsonl

# 2. Create reproducible model-run jobs for the configured pilot conditions.
PYTHONPATH=src python -m hrp.cli build-manifest \
  --problems data/processed/problems.jsonl \
  --config config/experiment.json \
  --output data/processed/pilot_manifest.jsonl \
  --stage pilot

# 3. After model traces have been collected, make blinded annotation tasks.
PYTHONPATH=src python -m hrp.cli make-annotation-tasks \
  --traces data/traces/traces.jsonl \
  --output data/annotations/annotation_tasks.jsonl \
  --limit 120

# 4. Validate trace and primary-operation annotation files.
PYTHONPATH=src python -m hrp.cli validate-traces --input data/traces/traces.jsonl
PYTHONPATH=src python -m hrp.cli validate-annotations --input data/annotations/annotations.jsonl

# 5. Calculate metrics and create presentation-ready figures.
PYTHONPATH=src python -m hrp.cli analyze \
  --traces data/traces/traces.jsonl \
  --annotations data/annotations/annotations.jsonl \
  --output-dir outputs/pilot
```

For the audited legacy pilot, create the evaluation-valid report without modifying the collected traces:

```bash
PYTHONPATH=src python -m hrp.cli analyze \
  --traces data/traces/groq_pilot_scored.jsonl \
  --annotations data/annotations/groq_judge_annotations.jsonl \
  --exclude-problems data/processed/pilot_scoring_exclusions.jsonl \
  --output-dir outputs/midsem_validated
```

Truncated traces (those that hit the completion token cap before emitting `FINAL_ANSWER`) carry no usable answer, so they are re-collected with a larger token budget rather than guessed. Snapshot the affected files to `outputs/backups/` first, drop the truncated traces, re-run `collect-groq` with `--max-completion-tokens 2048`, re-run `score-traces`, and prune stale judge annotations whose trace ids changed before regenerating the report.

The expanded pilot collected 93 of 100 manifest problems (the remaining 7 `legacy-237/239/241/243/244/245/246` were not collected due to the Groq daily token cap). Of those, 17 problems are excluded by `pilot_scoring_exclusions.jsonl`, leaving 76 valid problems per condition in `outputs/midsem_expanded/` (matched N=74).

The separate MMLU run (`split=mmlu`, multiple-choice) uses the same pipeline on the first 100 aligned Hindi/English MMLU rows; its report needs the `--answer-type multiple_choice` flag so the prose says "option answer" instead of "numeric answer":

```bash
PYTHONPATH=src python -m hrp.cli analyze \
  --traces data/traces/groq_mmlu_scored.jsonl \
  --annotations data/annotations/groq_judge_annotations.jsonl \
  --output-dir outputs/mmlu \
  --answer-type multiple_choice
```

## Groq Collection

Groq supports assistant-message prefilling, which is required for the language-prefill intervention. First list the models available to your key:

```bash
PYTHONPATH=src python -m hrp.cli groq-list-models
```

Before collecting, estimate a strict maximum cost from the manifest. At Groq's currently published prices, `openai/gpt-oss-20b` is `$0.075`/M input and `$0.30`/M output; `openai/gpt-oss-120b` is `$0.15`/M input and `$0.60`/M output. Verify current prices in Groq documentation before running.

```bash
PYTHONPATH=src python -m hrp.cli estimate-cost \
  --manifest data/processed/pilot_manifest_reviewed.jsonl \
  --max-completion-tokens 1024 \
  --input-price-per-million 0.075 \
  --output-price-per-million 0.30
```

Run a four-job smoke test first. It is intentionally limited so we can verify the exact response format and prefill behavior before spending on the full pilot:

```bash
PYTHONPATH=src python -m hrp.cli collect-groq \
  --manifest data/processed/pilot_manifest_reviewed.jsonl \
  --output data/traces/groq_smoke.jsonl \
  --model openai/gpt-oss-20b \
  --limit 4 \
  --max-completion-tokens 1024
```

After inspecting the smoke traces, run all 400 jobs, score them, and analyze:

```bash
PYTHONPATH=src python -m hrp.cli collect-groq \
  --manifest data/processed/pilot_manifest_reviewed.jsonl \
  --output data/traces/groq_pilot_raw.jsonl \
  --model openai/gpt-oss-20b \
  --max-completion-tokens 1024

PYTHONPATH=src python -m hrp.cli score-traces \
  --traces data/traces/groq_pilot_raw.jsonl \
  --problems data/processed/problems_reviewed.jsonl \
  --output data/traces/groq_pilot_scored.jsonl
```

Always present exact-match accuracy alongside the explicit `FINAL_ANSWER` parse rate. A trace that reaches the token cap before its answer marker is an output-format failure, not evidence of incorrect reasoning.

`analyze` writes `summary.json`, CSV tables, a Markdown summary, and PNG/PDF figures.

## LLM-Judge Draft Annotations

Primary-operation labels can be drafted with an LLM judge. The judge sees only the taxonomy and the trace text; the condition and final answer stay withheld. Its records are tagged `annotator_id: "llm_judge"` and are a **draft, not evidence** — a shared human overlap is required before analysis treats them as agreed:

```bash
PYTHONPATH=src python -m hrp.cli judge-annotate \
  --tasks data/annotations/groq_preliminary_annotation_tasks.jsonl \
  --output data/annotations/groq_judge_annotations.jsonl \
  --model openai/gpt-oss-20b \
  --limit 1
```

Use a short `--limit` first, then validate with `validate-annotations`. Judge labeling is a separate API operation from trace collection, so run it only when you explicitly allow additional usage.

## Annotation Taxonomy

Each segmented reasoning step receives one primary operation:

- `problem_parsing`
- `planning`
- `forward_computation`
- `backward_chaining`
- `case_analysis`
- `verification`
- `error_detection`
- `correction_backtracking`
- `answer_extraction`
- `other`

The annotation format intentionally contains no secondary-label properties. Annotators may add a short free-text note only when needed to explain an uncertain decision.

## Current Boundaries

- The scaffold does not choose an inference provider, use API keys, or make model calls.
- Before trace collection, the hosted runtime must be confirmed to support assistant-prefix continuation; a normal chat API that merely accepts an assistant message is not enough for this prefill experiment.
- The old files in `../250_entries/` are untouched and are not considered an audited benchmark.
- Generated chain-of-thought is described as **observable reasoning behavior**, not as verified access to hidden model reasoning.
- Operation-strategy conclusions require human annotation overlap. LLM-judge outputs are explicitly labeled drafts until this validation is completed.
