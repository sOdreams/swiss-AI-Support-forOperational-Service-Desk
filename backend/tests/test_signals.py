import asyncio
from copy import deepcopy
import json

import pytest

from service_desk.analysis import TicketAnalysis, TicketInput
from service_desk.analysis.evidence import evidence_support, verification_excerpt
from test_analysis import Retriever
from test_resolution import ResolveProvider


TICKET = TicketInput("Archive access", "The manager approved standard Archive access. No elevated rights are requested.")


class SignalProvider(ResolveProvider):
    def __init__(self, variant="valid"):
        super().__init__()
        self.signal_variant = variant

    async def create(self, **kwargs):
        response = await super().create(**kwargs)
        if kwargs["text"]["format"]["name"] == "candidate_filter":
            value = json.loads(response.output_text)
            value["signals"] = {
                "observations": [{"kind": "constraint", "text": "Standard access only; no elevated rights.", "evidence_ids": ["Q3"]}],
                "prerequisites": [{"check": "Manager approval for standard access", "state": "satisfied", "evidence_ids": ["Q2"]}],
            }
            if self.signal_variant == "unknown_fact":
                value["signals"]["prerequisites"][0]["evidence_ids"] = ["Q999"]
            elif self.signal_variant == "duplicate_kind":
                value["signals"]["observations"] *= 2
            elif self.signal_variant == "no_evidence":
                value["signals"]["observations"][0]["evidence_ids"] = []
            response.output_text = json.dumps(value)
        return response


def test_signals_reach_resolve_with_exact_quotes_without_extra_calls_or_query_changes():
    async def run():
        provider = SignalProvider()
        retriever = Retriever()
        pipeline = TicketAnalysis(retriever, client=provider)
        try:
            result = await pipeline.analyze_and_resolve(TICKET)
            assert result["status"] == "ready" and len(provider.calls) == 3
            assert len(retriever.queries) == 1 and retriever.queries[0].summary == TICKET.summary
            signals = result["filter"]["signals"]
            assert signals["prerequisites"][0]["state"] == "satisfied"
            assert signals["prerequisites"][0]["evidence"][0]["text"] == "The manager approved standard Archive access."
            assert signals["observations"][0]["evidence"][0]["text"] == "No elevated rights are requested."
            payload = json.loads(provider.calls[-1]["input"])
            assert payload["signals"]["prerequisites"][0]["state"] == "satisfied"
            assert "evidence" not in payload["signals"]["prerequisites"][0]  # Q IDs refer to existing original facts.
            assert result["resolution"]["context_signals"] == signals
            assert result["resolution"]["evidence_support"]["state"] == "procedure_reference"
            assert result["filter"]["evidence_support"]["active_comment_count"] == 1
            await pipeline.analyze_and_resolve(TICKET)
            assert len(provider.calls) == 3
            analysis = await pipeline.analyze(TICKET)
            analysis["conflicts"] = [{"field": "service"}]
            blocked = await pipeline.resolve(TICKET, analysis)
            assert not json.loads(provider.calls[-1]["input"])["signals"]["prerequisites"]
            assert not blocked["resolution"]["context_signals"]["prerequisites"]
            assert blocked["resolution"]["evidence_support"]["state"] == "needs_review"
        finally:
            await pipeline.close()
    asyncio.run(run())


@pytest.mark.parametrize("variant", ["unknown_fact", "duplicate_kind", "no_evidence"])
def test_invalid_signal_evidence_fails_closed_without_retry(variant):
    async def run():
        provider = SignalProvider(variant)
        pipeline = TicketAnalysis(Retriever(), client=provider)
        try:
            result = await pipeline.analyze(TICKET)
            assert result["status"] == "partial" and len(provider.calls) == 2
            assert result["filter"]["signals"] == {"observations": [], "prerequisites": []}
            assert result["filter"]["evidence_support"]["state"] == "unavailable"
            assert len(result["retrieval"]["hits"]) == 2
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_coverage_is_about_selected_patterns_not_duplicate_counts_or_corpus_completeness():
    filtered = {"status": "ready", "service": "Archive", "primary_document_ids": ["G1"],
                "active_comment_ids": ["E1"], "comments": [{"id": "E1", "status": "conditional", "occurrences": 900}]}
    assert evidence_support(filtered)["active_comment_count"] == 1
    held = deepcopy(filtered)
    held["status"] = "needs_review"
    assert evidence_support(held)["state"] == "needs_review"
    assert evidence_support(held)["active_comment_count"] == 0
    filtered["active_comment_ids"] = []
    assert evidence_support(filtered)["state"] == "analogue_only"
    filtered["primary_document_ids"] = []
    assert evidence_support(filtered)["state"] == "no_selected_evidence"
    filtered["service"] = None
    assert evidence_support(filtered)["state"] == "needs_review"
    assert evidence_support(None)["state"] == "unavailable"


def test_historical_verification_is_a_literal_clause_and_never_a_synthetic_current_result():
    source = "Resolution: Corrected the template, reran the batch, and confirmed the fee table renders correctly."
    quote = verification_excerpt(source)
    assert quote == "confirmed the fee table renders correctly." and quote in source
    assert verification_excerpt("Resolution: Reclassified the request and provisioned access.") is None
    assert verification_excerpt("Problem fixed.") is None
    assert verification_excerpt("Resolution: Confirmed access, then validated the output workspace.") == "validated the output workspace."
