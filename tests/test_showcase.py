import tempfile
import unittest
from pathlib import Path

from hrp.showcase import benchmark_accuracy, build_showcase_data, create_showcase_figures


def _summary_row(condition_id: str, **overrides) -> dict:
    row = {
        "condition_id": condition_id,
        "prefill_language": "hi",
        "prefill_strategy": "none",
        "n_traces": 76,
        "n_correct": 72,
        "n_wrong_answers": 2,
        "n_parseable_answers": 74,
        "n_unparseable": 2,
        "answer_parse_rate": 74 / 76,
        "n_matched_problems": 74,
        "n_matched_correct": 72,
        "matched_accuracy": 72 / 74,
        "mean_hindi_script_share": 0.4,
        "mean_english_script_share": 0.6,
        "mean_code_switch_rate": 0.02,
        "annotated_steps": 120,
    }
    row.update(overrides)
    return row


class ShowcaseTests(unittest.TestCase):
    def test_showcase_figures_generated_from_summary_rows(self):
        summary = [
            _summary_row("hi_neutral_en", n_correct=72, n_wrong_answers=2),
            _summary_row("hi_neutral_hi", n_correct=73, n_wrong_answers=1),
            _summary_row("hi_none", n_correct=72, n_wrong_answers=2),
            _summary_row("hi_planning_hi", n_correct=73, n_wrong_answers=1),
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            figures = create_showcase_figures(summary, temporary_directory)
            self.assertGreaterEqual(len(figures), 5)
            self.assertTrue(all(Path(figure).exists() for figure in figures))

    def test_benchmark_accuracy_uses_all_valid_problems_as_denominator(self):
        data = build_showcase_data([_summary_row("hi_none", n_correct=72, n_valid=76)])
        self.assertAlmostEqual(benchmark_accuracy(data["conditions"][0]), 72 / 76)

    def test_benchmark_accuracy_is_below_matched_accuracy(self):
        summary = [
            _summary_row(
                "hi_none",
                n_correct=72,
                n_wrong_answers=2,
                n_parseable_answers=74,
                n_unparseable=2,
                n_matched_correct=72,
                n_matched_problems=74,
            )
        ]
        data = build_showcase_data(summary)
        condition = data["conditions"][0]
        self.assertLess(benchmark_accuracy(condition), condition.n_matched_correct / condition.n_matched)


if __name__ == "__main__":
    unittest.main()