import unittest

from scripts.triage_pipeline import PRIORITY_MATRIX, TriageEngine


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

    def test_priority_inference_exposes_rule_evidence(self):
        priority = self.engine.infer_urgency_impact(
            {
                "Summary": "Cash not there; processing is blocked",
                "Description": "The margin sweep missed the cutoff and there is no workaround.",
                "All Comments": [],
            },
            "Incident",
            "Cash Management",
        )
        self.assertEqual(PRIORITY_MATRIX[priority["urgency_score"]][priority["impact_score"]], priority["priority"])
        self.assertTrue(priority["rule_trace"])
        self.assertIn("critical service: impact +1", priority["rule_trace"])

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

    def test_explicit_request_titles_override_incidental_incident_words(self):
        for summary, description in (
            (
                "Access requested for Regulatory Reporting",
                "Please validate the standard role and permissions."
            ),
            (
                "General request for Rimes Data Feed with unclear details",
                "The message is incomplete and requires review."
            ),
            (
                "Email notification received for Emailed Support Tickets",
                "The message references a delayed feed or a possible outage."
            ),
        ):
            result, confidence, _ = self.engine.infer_work_type(
                {"Summary": summary, "Description": description}
            )
            self.assertEqual(result, "Service Request")
            self.assertLessEqual(confidence, 0.92)

    def test_mailbox_creation_is_request_even_with_outage_word(self):
        result, _, _ = self.engine.infer_work_type(
            {
                "Work type": "Incident",
                "Summary": "Production outage in Outlook & Email for shared mailbox creation",
                "Description": "The request is to create a shared mailbox for a new team.",
            }
        )
        self.assertEqual(result, "Service Request")

    def test_resolution_author_is_not_used_as_assignee(self):
        engine = TriageEngine(
            [
                training_record(
                    "Trade matching adapter rejected broker allocations",
                    "The matching backlog is blocked and needs reprocessing.",
                    "Trade Matching",
                    "Investment Operations",
                    "actual.assignee@intcom.com",
                    comments=[
                        "resolution.agent@intcom.com: Resolution: Corrected the broker setup, reprocessed the rejected allocation batch, and confirmed matching status."
                    ],
                )
            ]
        )
        result = engine.triage(
            {
                "Summary": "Trade matching adapter rejected broker allocations",
                "Description": "The matching backlog is blocked and needs reprocessing.",
                "Affected Business or IT Services": ["Trade Matching"],
                "All Comments": [],
            }
        )
        self.assertEqual(result["assignee"], "actual.assignee@intcom.com")
        self.assertNotEqual(result["assignee"], result["resolution_author"])

    def test_comment_authors_do_not_pollute_retrieval_text(self):
        from scripts.triage_pipeline import join_ticket_text

        text = join_ticket_text({"Summary": "Example", "All Comments": ["agent@example.com: Concrete issue details"]})
        self.assertNotIn("agent", text)
        self.assertIn("Concrete issue details", text)

    def test_challenge_target_fields_are_not_used_as_routing_evidence(self):
        ticket = {
            "Work type": "Incident",
            "Summary": "Vendor notice: benchmark publication delayed beyond the publishing window",
            "Description": "Rimes benchmark file arrived after the downstream cutoff.",
            "Affected Business or IT Services": ["SharePoint & File Storage"],
            "Priority": "Lowest",
            "Urgency": "Lowest",
            "Impact": "Lowest",
            "All Comments": [],
        }
        result = self.engine.triage(ticket)
        self.assertEqual(result["work_type"], "Incident")
        self.assertEqual(result["affected_services"], ["Rimes Data Feed"])

    def test_phase_three_generates_resolution_and_uses_historical_assignee(self):
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
        self.assertEqual(result["assignee"], "random.assignee@intcom.com")

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
