import unittest

from backend.server import STATE, make_proposal


class BackendContractTests(unittest.TestCase):
    def test_queue_is_loaded(self):
        self.assertGreaterEqual(len(STATE.records), 20)
        self.assertGreaterEqual(len(STATE.training_records), 1000)

    def test_assist_response_contains_reviewable_pipeline(self):
        proposal = make_proposal(STATE.records[0])

        self.assertTrue(proposal["ticket_id"])
        self.assertIn(proposal["proposed_work_type"], {"Incident", "Service Request"})
        self.assertIn(proposal["proposed_priority"], {"Lowest", "Low", "Medium", "High", "Highest"})
        self.assertIsInstance(proposal["sources"], list)
        self.assertEqual(len(proposal["resolution_options"]), 2)
        option_kinds = {option["kind"] for option in proposal["resolution_options"]}
        self.assertEqual(len(option_kinds), 2)
        self.assertIn("escalation", option_kinds)


if __name__ == "__main__":
    unittest.main()
