import unittest

from scripts.export_submission import compact_record, validate_record


class ExportSubmissionTests(unittest.TestCase):
    def test_compact_record_drops_reasoning_fields(self):
        record = {
            "ticket_index": 1,
            "summary": "Example",
            "prediction": {
                "work_type": "Service Request",
                "affected_services": ["Tax Reporting"],
                "service_teams": ["Tax & Reporting"],
                "assignee": "agent@example.com",
                "urgency": "Lowest",
                "impact": "Lowest",
                "priority": "Lowest",
                "resolution": "done",
                "resolution_comment": "Completed the request.",
                "reasoning_summary": {"work_type": ["hidden from submission"]},
            },
        }
        exported = compact_record(record)
        self.assertNotIn("reasoning_summary", exported)
        self.assertEqual(validate_record(exported), [])

if __name__ == "__main__":
    unittest.main()
