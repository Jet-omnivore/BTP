import unittest

from hrp.groq_client import _annotation_records, _load_steps_json, _step_validation_errors


class JudgeHelperTests(unittest.TestCase):
    def test_load_steps_json_accepts_fenced_json(self):
        content = '```json\n{"steps": [{"step_text": "a", "primary_operation": "planning"}]}\n```'
        self.assertEqual(
            _load_steps_json(content),
            [{"step_text": "a", "primary_operation": "planning"}],
        )

    def test_load_steps_json_rejects_invalid_json(self):
        self.assertIsNone(_load_steps_json("not json at all"))

    def test_load_steps_json_rejects_empty_step_list(self):
        self.assertIsNone(_load_steps_json('{"steps": []}'))

    def test_validation_rejects_unknown_operation(self):
        steps = [{"step_text": "a", "primary_operation": "guessing"}]
        self.assertTrue(any("unknown primary_operation" in error for error in _step_validation_errors(steps)))

    def test_validation_rejects_empty_step_text(self):
        steps = [{"step_text": " ", "primary_operation": "other"}]
        self.assertTrue(any("empty step_text" in error for error in _step_validation_errors(steps)))

    def test_annotation_records_are_sequential_and_labeled_draft(self):
        task = {"annotation_task_id": "task-0007", "trace_id": "trace-009"}
        steps = [
            {"step_text": "बनाते हैं।", "primary_operation": "planning"},
            {"step_text": "3 × 4 = 12.", "primary_operation": "forward_computation"},
        ]
        records = _annotation_records(task, steps, "openai/gpt-oss-20b")
        self.assertEqual([record["step_index"] for record in records], [1, 2])
        self.assertEqual(records[0]["annotator_id"], "llm_judge")
        self.assertEqual(records[0]["judge_model_id"], "openai/gpt-oss-20b")
        self.assertEqual(records[1]["annotation_id"], "ann-task-0007-s02")


if __name__ == "__main__":
    unittest.main()