import tempfile
import unittest
from pathlib import Path

from hrp.plotting import create_figures


class PlottingTests(unittest.TestCase):
    def test_create_figures_writes_accuracy_and_language_charts(self):
        summary = [
            {
                "condition_id": "hi_none",
                "prefill_strategy": "none",
                "accuracy": 0.5,
                "matched_accuracy": 1.0,
                "matched_accuracy_ci_low": 0.9,
                "matched_accuracy_ci_high": 1.0,
                "answer_parse_rate": 0.75,
                "accuracy_ci_low": 0.3,
                "accuracy_ci_high": 0.7,
                "mean_hindi_script_share": 0.4,
                "mean_english_script_share": 0.6,
                "annotated_steps": 0,
            }
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            figures = create_figures(summary, temporary_directory)
            self.assertEqual(len(figures), 3)
            self.assertTrue(all(Path(figure).exists() for figure in figures))


if __name__ == "__main__":
    unittest.main()
