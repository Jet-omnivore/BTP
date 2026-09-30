# Midsem Delivery Checklist

## What The Midsem Pilot Will Demonstrate

The pilot validates the full experimental chain, not the final research claim:

1. A reproducible Hindi-English paired problem source.
2. Four controlled Hindi-input conditions.
3. A hosted-model trace collection run.
4. Blinded manual annotation of observable reasoning operations.
5. Accuracy, reasoning-language, and operation-distribution figures.

## Required Artifacts

- `data/processed/problems_reviewed.jsonl`: imported 250 items, with the 100-item pilot subset marked approved after Hindi review.
- `data/annotations/pilot_translation_audit.csv`: completed Hindi review sheet for the pilot pairs.
- `data/processed/pilot_manifest.jsonl`: 400 jobs for 100 problems across four conditions at one seed.
- `data/traces/traces.jsonl`: validated model outputs.
- `data/annotations/annotation_tasks.jsonl`: 120 blinded sampled traces.
- `data/annotations/annotations.jsonl`: primary-operation labels from two annotators for at least 30 shared traces.
- `outputs/pilot/figures/accuracy_by_condition.png`.
- `outputs/pilot/figures/reasoning_language_composition.png`.
- `outputs/pilot/figures/reasoning_operation_distribution.png`.
- `outputs/pilot/midsem_summary.md`.

## Suggested Presentation Structure

1. Problem and motivation: Hindi users may receive Hindi answers while the model visibly reasons in English.
2. Gap in prior work: *Language Matters* has multilingual prefills and a four-class taxonomy, but not Hindi or matched language-versus-strategy controls.
3. Hypotheses and controlled conditions.
4. Data provenance: legacy 250-item set, unreviewed translation status, and planned audit.
5. Pipeline: manifest -> hosted endpoint -> traces -> blinded annotation -> metrics.
6. Accuracy and confidence-interval chart.
7. Script-composition and code-switching chart.
8. Reasoning-operation distribution chart.
9. Two qualitative traces, one successful and one failure case.
10. Limitations and final-semester expansion.

## Explicit Midsem Limitations

- The remaining 150 legacy items are not yet human-audited; only the 100-item pilot subset is approved.
- The pilot evaluates one hosted model and should not generalize across model families.
- Observable traces are not guaranteed faithful internal reasoning.
- The result is preliminary; final analysis requires a reviewed benchmark and multiple models.
