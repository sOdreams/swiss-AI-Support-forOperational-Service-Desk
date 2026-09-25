import unittest

from scripts.evaluate_pseudo_holdout import calibration_table, hide_targets


class PseudoHoldoutTests(unittest.TestCase):
    def test_hide_targets_removes_supervised_fields(self):
        record = {
            "Work type": "Incident",
            "Affected Business or IT Services": ["NAV Calculation"],
            "Service Team(s)": ["Valuation & Pricing"],
            "Assignee": "agent@example.com",
            "Priority": "high",
            "Urgency": "high",
            "Impact": "medium",
            "Resolution": "done",
            "Summary": "NAV failed",
            "Description": "The NAV batch stopped.",
        }
        hidden = hide_targets(record)
        self.assertEqual(hidden["Work type"], "")
        self.assertEqual(hidden["Affected Business or IT Services"], [])
        self.assertIsNone(hidden["Assignee"])
        self.assertEqual(hidden["Summary"], record["Summary"])

    def test_calibration_table_reports_accuracy(self):
        result = calibration_table([(0.9, True), (0.8, True), (0.6, False)])
        self.assertEqual(sum(row["count"] for row in result["bins"]), 3)
        self.assertGreaterEqual(result["ece"], 0.0)


if __name__ == "__main__":
    unittest.main()
