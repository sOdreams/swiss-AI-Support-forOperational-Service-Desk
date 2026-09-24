import unittest

from triage_pipeline import PRIORITY_MATRIX, TriageEngine


def training_record(summary, description, service, team, assignee, work_type="Incident", comments=None):
    return {
        "Work type": work_type,
        "Summary": summary,
        "Description": description,
        "Affected Business or IT Services": [service],
        "Business Entity": ["Germany"],
        "Service Team(s)": [team],
        "Assignee": assignee,
        "All Comments": comments or [],
        "Resolution": "done",
    }


class TriagePipelineTests(unittest.TestCase):
    def setUp(self):
        self.engine = TriageEngine(
            [
                training_record(
                    "Benchmark file delayed",
                    "Rimes benchmark file arrived after the downstream cutoff.",
                    "Rimes Data Feed",
                    "Market Data Services",
                    "rimes.agent@intcom.com",
                ),
                training_record(
                    "Shared mailbox request",
                    "Standard shared mailbox and distribution list requested.",
                    "Outlook & Email",
                    "Enterprise Applications",
                    "mail.agent@intcom.com",
                    work_type="Service Request",
                ),
                training_record(
                    "NAV tolerance breach",
                    "NAV batch stopped after valuation tolerance breach on several funds.",
                    "NAV Calculation",
                    "Valuation & Pricing",
                    "nav.agent@intcom.com",
                ),
                training_record(
                    "Cash margin sweep shortfall",
                    "Cash was short after a margin sweep and required ledger reconciliation.",
                    "Cash Management",
                    "Treasury & Cash",
                    "cash.assignee@intcom.com",
                    comments=[
                        "vincent.lange@intcom.com: Resolution: Reconciled the cash ledger against the bank statement and found the sweep missed the prior day's cutoff; booked a value-dated adjustment and confirmed the balance with the desk."
                    ],
                ),
                training_record(
                    "Trade matching allocation rejection",
                    "Adapter rejected broker allocations and the matching backlog needed reprocessing.",
                    "Trade Matching",
                    "Investment Operations",
                    "random.assignee@intcom.com",
                    comments=[
                        "quinn.anderson@intcom.com: Resolution: Corrected the broker setup, reprocessed the rejected allocation batch, and confirmed matching status."
                    ],
                ),
            ]
        )

    def test_priority_matrix_edges(self):
        self.assertEqual(PRIORITY_MATRIX[4][4], "Highest")
        self.assertEqual(PRIORITY_MATRIX[0][0], "Lowest")
        self.assertEqual(PRIORITY_MATRIX[2][2], "Medium")

    def test_narrative_can_override_selected_service(self):
        ticket = {
            "Work type": "Incident",
            "Summary": "Vendor notice: benchmark publication delayed beyond the publishing window",
            "Description": "Rimes benchmark file arrived after the downstream cutoff.",
            "Affected Business or IT Services": ["SharePoint & File Storage"],
            "All Comments": [],
        }
        retrieved = self.engine.retrieve(ticket)
        service, _, reasons = self.engine.infer_service(ticket, retrieved)
        self.assertEqual(service, "Rimes Data Feed")
        self.assertIn("narrative overrode supplied service", reasons)

    def test_access_cleanup_is_service_request(self):
        ticket = {
            "Work type": "Incident",
            "Summary": "Need access removed from all deactivated users in portal today",
            "Description": "Routine identity cleanup after a batch of user deactivations.",
            "Affected Business or IT Services": ["Identity & Access Management"],
            "All Comments": [],
        }
        result, _, _ = self.engine.infer_work_type(ticket)
        self.assertEqual(result, "Service Request")

    def test_phase_three_generates_resolution_and_uses_resolution_owner(self):
        ticket = {
            "Work type": "Incident",
            "Summary": "Trade matching adapter rejected broker allocations",
            "Description": "The matching backlog is blocked and needs reprocessing.",
            "Affected Business or IT Services": ["Trade Matching"],
            "All Comments": [],
        }
        result = self.engine.triage(ticket)
        self.assertEqual(result["resolution"], "done")
        self.assertIn("reprocessed", result["resolution_comment"])
        self.assertEqual(result["assignee"], "quinn.anderson@intcom.com")

    def test_phase_three_requests_missing_cash_context(self):
        ticket = {
            "Work type": "Incident",
            "Summary": "Cash not there after margin sweep",
            "Description": "Please clarify the exact account and booking date.",
            "Affected Business or IT Services": ["Cash Management"],
            "All Comments": [],
        }
        result = self.engine.triage(ticket)
        self.assertEqual(result["resolution"], "clarification")
        self.assertIn("cash account", result["resolution_comment"])


if __name__ == "__main__":
    unittest.main()
