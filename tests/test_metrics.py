import unittest
import tempfile
from pathlib import Path

from hrp.answers import canonicalize_numeric_answer, numeric_answers_match
from hrp.cli import _validate_file
from hrp.io import write_jsonl
from hrp.schema import validate_annotation, validate_trace
from hrp.metrics import (
    condition_summary,
    cross_condition_agreement,
    language_profile,
    paired_condition_differences,
)


class MetricTests(unittest.TestCase):
    def test_language_profile_detects_script_switching(self):
        profile = language_profile("पहले solve करें फिर उत्तर दें")
        self.assertGreater(profile["hindi_script_share"], 0)
        self.assertGreater(profile["english_script_share"], 0)
        self.assertGreater(profile["code_switch_count"], 0)

    def test_paired_differences_include_mcnemar_p_value(self):
        traces = [
            _trace("t1", "p1", "a", False),
            _trace("t2", "p1", "b", True),
            _trace("t3", "p2", "a", True),
            _trace("t4", "p2", "b", True),
            _trace("t5", "p3", "a", True),
            _trace("t6", "p3", "b", True),
        ]
        rows = paired_condition_differences(traces)
        row = rows[0]
        self.assertEqual(row["b_only_correct"], 1)
        self.assertEqual(row["a_only_correct"], 0)
        self.assertEqual(row["mcnemar_p_value"], 1.0)

    def test_mcnemar_p_detects_asymmetric_discordance(self):
        from hrp.metrics import _mcnemar_exact_p
        self.assertAlmostEqual(_mcnemar_exact_p(b_only_correct=4, a_only_correct=0), 0.125)
        self.assertAlmostEqual(_mcnemar_exact_p(b_only_correct=5, a_only_correct=1), 0.21875)
        self.assertEqual(_mcnemar_exact_p(b_only_correct=0, a_only_correct=0), 1.0)

    def test_condition_summary_computes_accuracy(self):
        traces = [
            _trace("t1", "p1", "hi_none", True),
            _trace("t2", "p2", "hi_none", False),
        ]
        rows = condition_summary(traces, [])
        self.assertEqual(rows[0]["n_traces"], 2)
        self.assertEqual(rows[0]["accuracy"], 0.5)

    def test_condition_summary_exposes_wrong_and_unparseable_counts(self):
        traces = [
            _trace("t1", "p1", "hi_none", True),
            _trace("t2", "p2", "hi_none", False),
            _trace("t3", "p3", "hi_none", False, scoring_status="unparseable"),
        ]
        rows = condition_summary(traces, [])
        self.assertEqual(rows[0]["n_wrong_answers"], 1)
        self.assertEqual(rows[0]["n_unparseable"], 1)
        self.assertEqual(rows[0]["n_parseable_answers"], 2)
        self.assertEqual(rows[0]["answer_parse_rate"], 2 / 3)

    def test_matched_accuracy_uses_identical_denominators_across_conditions(self):
        traces = [
            _trace("t1", "p-error", "a", False),
            _trace("t2", "p-error", "b", True, scoring_status="unparseable"),
            _trace("t3", "p-ok", "a", True),
            _trace("t4", "p-ok", "b", True),
        ]
        rows = {row["condition_id"]: row for row in condition_summary(traces, [])}
        self.assertEqual(rows["a"]["n_matched_problems"], 1)
        self.assertEqual(rows["b"]["n_matched_problems"], 1)
        self.assertEqual(rows["a"]["n_matched_correct"], 1)
        self.assertEqual(rows["b"]["n_matched_correct"], 1)
        self.assertEqual(rows["a"]["matched_accuracy"], 1.0)
        self.assertEqual(rows["b"]["matched_accuracy"], 1.0)
        self.assertEqual(rows["a"]["accuracy"], 0.5)
        self.assertEqual(rows["b"]["accuracy"], 1.0)

    def test_cross_condition_agreement_reports_ceiling(self):
        traces = [
            _trace("t1", "p1", "a", True),
            _trace("t2", "p1", "b", True),
            _trace("t3", "p1", "c", True),
            _trace("t4", "p2", "a", False),
            _trace("t5", "p2", "b", False, scoring_status="unparseable"),
        ]
        result = cross_condition_agreement(traces)
        self.assertEqual(result["n_problems"], 2)
        self.assertEqual(result["n_complete"], 1)
        self.assertEqual(result["n_incomplete"], 1)
        self.assertEqual(result["n_identical_answers"], 1)
        self.assertEqual(result["n_all_correct"], 1)
        self.assertEqual(result["n_problems_with_any_wrong_answer"], 1)
        self.assertIn("t4", result["wrong_trace_ids"])
        self.assertNotIn("t5", result["wrong_trace_ids"])

    def test_paired_differences_use_problem_alignment(self):
        traces = [
            _trace("t1", "p1", "a", False),
            _trace("t2", "p1", "b", True),
            _trace("t3", "p2", "a", True),
            _trace("t4", "p2", "b", True),
        ]
        rows = paired_condition_differences(traces)
        self.assertEqual(rows[0]["n_paired_problems"], 2)
        self.assertEqual(rows[0]["accuracy_difference_b_minus_a"], 0.5)

    def test_numeric_scorer_supports_devanagari_digits(self):
        answer = canonicalize_numeric_answer("FINAL_ANSWER: ७२")
        self.assertEqual(answer, "72")
        self.assertTrue(numeric_answers_match(answer, "72"))

    def test_numeric_scorer_allows_hindi_prefix_and_unit_after_marker(self):
        answer = canonicalize_numeric_answer("FINAL_ANSWER: उत्तर ७२ रुपये")
        self.assertEqual(answer, "72")

    def test_numeric_scorer_preserves_integer_trailing_zero(self):
        self.assertEqual(canonicalize_numeric_answer("FINAL_ANSWER: 10"), "10")

    def test_numeric_scorer_requires_explicit_marker(self):
        self.assertIsNone(canonicalize_numeric_answer("The answer appears to be 72."))

    def test_choice_scorer_extracts_letter_and_choice_text(self):
        from hrp.answers import canonicalize_choice_answer, choice_answers_match

        choices = ["trade.", "warfare.", "religion.", "consumption."]
        self.assertEqual(canonicalize_choice_answer("FINAL_ANSWER: B", choices), "B")
        self.assertEqual(canonicalize_choice_answer("FINAL_ANSWER: warfare.", choices), "B")
        self.assertTrue(choice_answers_match("B", "B"))
        self.assertFalse(choice_answers_match("A", "B"))

    def test_choice_scorer_requires_explicit_marker(self):
        from hrp.answers import canonicalize_choice_answer

        self.assertIsNone(canonicalize_choice_answer("I think B is correct.", None))

    def test_trace_validation_allows_paired_problem_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "traces.jsonl"
            write_jsonl(path, [_trace("t1", "p1", "a", True), _trace("t2", "p1", "b", True)])
            _validate_file(str(path), validate_trace)

    def test_annotation_validation_allows_multiple_steps_per_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "annotations.jsonl"
            write_jsonl(
                path,
                [
                    {
                        "annotation_id": "ann-a-s01",
                        "trace_id": "trace-a",
                        "annotator_id": "llm_judge",
                        "step_index": 1,
                        "step_text": "first",
                        "primary_operation": "planning",
                    },
                    {
                        "annotation_id": "ann-a-s02",
                        "trace_id": "trace-a",
                        "annotator_id": "llm_judge",
                        "step_index": 2,
                        "step_text": "second",
                        "primary_operation": "forward_computation",
                    },
                ],
            )
            _validate_file(str(path), validate_annotation)


def _trace(trace_id, problem_id, condition_id, is_correct, scoring_status=None):
    return {
        "trace_id": trace_id,
        "problem_id": problem_id,
        "model_id": "demo",
        "condition_id": condition_id,
        "input_language": "hi",
        "prefill_language": "none",
        "prefill_strategy": "none",
        "prompt_version": "v1",
        "reasoning_text": "पहले हल करें",
        "final_answer_raw": "1",
        "final_answer_canonical": "1",
        "is_correct": is_correct,
        "scoring_status": scoring_status or "scored",
        "seed": 0,
    }


if __name__ == "__main__":
    unittest.main()
