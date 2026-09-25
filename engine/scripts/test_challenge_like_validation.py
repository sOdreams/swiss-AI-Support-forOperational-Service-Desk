import unittest
import random

from scripts.evaluate_challenge_like import challenge_like_record
from scripts.triage_pipeline import LEVEL_LABELS, PRIORITY_MATRIX


class ChallengeLikeValidationTests(unittest.TestCase):
    def test_profile_blanks_fields_and_preserves_priority_matrix(self):
        gold = {
            "Work type": "Incident",
            "Affected Business or IT Services": ["Cash Management"],
            "Service Team(s)": ["Treasury & Cash"],
            "Assignee": "cash.agent@intcom.com",
            "Resolution": "done",
        }
        observed, flags = challenge_like_record(
            gold,
            random.Random(7),
            ["Cash Management", "Rimes Data Feed"],
            service_corruption_rate=1.0,
            work_type_corruption_rate=1.0,
        )
        self.assertTrue(flags["service_corrupted"])
        self.assertTrue(flags["work_type_corrupted"])
        self.assertEqual(observed["Service Team(s)"], [])
        self.assertIsNone(observed["Assignee"])
        self.assertIsNone(observed["Resolution"])
        urgency = LEVEL_LABELS.index(observed["Urgency"])
        impact = LEVEL_LABELS.index(observed["Impact"])
        self.assertEqual(observed["Priority"], PRIORITY_MATRIX[urgency][impact])


if __name__ == "__main__":
    unittest.main()
