import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from service_desk.analysis import TicketAnalysis
from service_desk.api import create_app
from test_analysis import Provider, Retriever, TICKET
from test_retrieval import artifact


class FastProvider(Provider):
    def __init__(self, variant="valid"):
        super().__init__(wait_for_both=True)
        self.variant = variant

    async def create(self, **kwargs):
        response = await super().create(**kwargs)
        value = json.loads(response.output_text)
        if kwargs["text"]["format"]["name"] == "ticket_clean":
            if self.variant == "conflict":
                value["service"] = "Payments"
        elif kwargs["text"]["format"]["name"] == "filter_resolve":
            comment = json.loads(kwargs["input"])["comments"][0]["id"]
            resolution = {"mode": "action_plan", "actions": [{"kind": "procedure",
                "next_step": "Provision the approved Archive role.", "reason": "The request concerns Archive access.",
                "check_first": None, "expected_outcome": None, "fact_ids": ["Q2"], "source_ids": [comment]}],
                "critical_question": None, "reply_draft": "We can provision access once the role is approved."}
            if self.variant == "reserve_source":
                resolution["actions"][0].update(kind="diagnostic", source_ids=["G2"])
            elif self.variant == "unselected_comment":
                value["comment_choices"] = []
            elif self.variant == "filter_failure":
                value["service"] = "Payments"
            elif self.variant == "invalid_procedure":
                resolution["actions"][0]["source_ids"] = ["Q2"]
            elif self.variant == "unknown":
                value.update(service=None, primary_ids=[], comment_choices=[])
                resolution.update(mode="needs_information", actions=[], critical_question="Which service needs access?")
            value = {"filter": value, "resolution": resolution}
        response.output_text = json.dumps(value)
        return response


def test_fast_uses_two_concurrent_calls_and_reuses_exact_ranked_provenance_and_conditions():
    async def run():
        provider = FastProvider()
        pipeline = TicketAnalysis(Retriever(), client=provider)
        try:
            first, second = await asyncio.gather(pipeline.analyze_and_resolve_fast(TICKET), pipeline.analyze_and_resolve_fast(TICKET))
            assert first["status"] == "ready" and first["workflow"] == "fast"
            assert len(provider.calls) == 2
            assert [h["rank"] for h in first["retrieval"]["hits"]] == [1, 2]
            card = first["resolution"]["actions"][0]
            assert card["required_checks"] == ["Verify the approved Archive role before provisioning."]
            assert card["sources"][0]["sources"][0]["document_id"] == "remove"
            assert not card["execution_authorized"]
            assert sum(len(s["calls"]) for s in first["stages"].values()) == 2
            assert "filter_resolve_ms" in first["timings"] and "filter_ms" not in first["timings"]
            first["resolution"]["actions"].clear()
            cached = await pipeline.analyze_and_resolve_fast(TICKET)
            assert cached["cache_hit"] and len(cached["resolution"]["actions"]) == 1
            assert len(second["resolution"]["actions"]) == 1
            # Fast output cannot masquerade as independently filtered analysis.
            assert (await pipeline.analyze(TICKET))["status"] == "ready"
            assert len(provider.calls) == 4
        finally:
            await pipeline.close()
    asyncio.run(run())


@pytest.mark.parametrize("variant", ["reserve_source", "unselected_comment", "filter_failure", "invalid_procedure", "conflict"])
def test_fast_revalidates_drafts_after_filtering_and_clean_reconciliation_without_retry(variant):
    async def run():
        provider = FastProvider(variant)
        pipeline = TicketAnalysis(Retriever(), client=provider)
        try:
            result = await pipeline.analyze_and_resolve_fast(TICKET)
            assert result["status"] == "partial" and len(provider.calls) == 2
            assert result["resolution"]["status"] == "unavailable"
            assert len(result["retrieval"]["hits"]) == 2
            if variant in {"filter_failure", "conflict"}:
                assert not result["filter"]["active_comment_ids"]
                assert result["triage"]["routing"]["team"] is None
            else:
                assert result["filter"]["status"] == "ready"
                assert result["filter"]["primary_document_ids"] == ["grant"]
            assert result["stages"]["resolve"]["validation_errors"]
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_fast_unknown_service_can_return_a_current_fact_clarification():
    async def run():
        provider = FastProvider("unknown")
        pipeline = TicketAnalysis(Retriever(), client=provider)
        try:
            result = await pipeline.analyze_and_resolve_fast(TICKET)
            assert result["conflicts"]  # Clean names Archive; joint inference abstains.
            assert result["resolution"]["status"] == "ready"
            assert result["resolution"]["mode"] == "needs_information"
            assert not result["resolution"]["actions"]
            assert len(provider.calls) == 2
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_experimental_http_fast_route_returns_existing_proposal_shape_and_hides_raw_provider_output(artifact, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path, _ = artifact
    provider = FastProvider()
    body = {"summary": TICKET.summary, "description": TICKET.description}
    factory = lambda _: TicketAnalysis(Retriever(), client=provider)
    with TestClient(create_app(path, path.parent / "fast.sqlite3", analysis_factory=factory)) as client:
        response = client.post("/tickets/resolve-fast", json=body)
        assert response.status_code == 200
        result = response.json()
        assert result["workflow"] == "fast" and result["resolution"]["status"] == "ready"
        assert result["stage_status"]["filter_resolve"]["ok"] and "stages" not in result
        assert "output_text" not in result and len(provider.calls) == 2
        assert client.post("/tickets/resolve-fast", json={**body, "analysis": result}).status_code == 422
    with TestClient(create_app(path, path.parent / "fast-disabled.sqlite3")) as client:
        assert client.post("/tickets/resolve-fast", json=body).status_code == 503
