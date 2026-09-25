import asyncio
from copy import deepcopy
from dataclasses import replace
import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from service_desk.analysis import TicketAnalysis
from service_desk.api import create_app
from test_analysis import Provider, Retriever, TICKET
from test_retrieval import artifact


class ResolveProvider(Provider):
    def __init__(self, variant="valid"):
        super().__init__()
        self.variant = variant

    async def create(self, **kwargs):
        if kwargs["text"]["format"]["name"] != "ticket_resolve":
            return await super().create(**kwargs)
        self.calls.append(kwargs)
        payload = json.loads(kwargs["input"])
        comments = payload["historical_comments"]
        action = {"kind": "procedure", "next_step": "Provision the approved Archive role.",
                  "reason": "The current request concerns Archive access.", "check_first": None,
                  "expected_outcome": None, "fact_ids": ["Q2"],
                  "source_ids": [comments[0]["id"]] if comments else ["Q2"]}
        value = {"mode": "action_plan" if comments else "needs_information",
                 "actions": [action] if comments else [],
                 "critical_question": None if comments else "Which Archive role has been approved?",
                 "reply_draft": "Once the required role is approved, access can be provisioned and checked."}
        if self.variant == "fabricated":
            action["source_ids"] = ["E-made-up"]
        if self.variant == "case_only":
            action["source_ids"] = [payload["historical_cases"][0]["id"]]
        if self.variant == "blocked_procedure":
            value["actions"] = [action]
        return SimpleNamespace(id="resolve-response", model="fake-model", status="completed", usage=None,
                               output_text=json.dumps(value))


def test_resolve_adds_one_call_preserves_prerequisites_and_deduplicates_repeated_requests():
    async def run():
        provider = ResolveProvider()
        pipeline = TicketAnalysis(Retriever(), client=provider)
        try:
            original = await pipeline.analyze(TICKET)
            first, second = await asyncio.gather(pipeline.analyze_and_resolve(TICKET), pipeline.analyze_and_resolve(TICKET))
            assert len(provider.calls) == 3
            assert first["analysis_cache_hit"] and first["status"] == "ready"
            assert first["retrieval"] == original["retrieval"]
            card = first["resolution"]["actions"][0]
            assert card["required_checks"] == ["Verify the approved Archive role before provisioning."]
            assert card["check_first"] is None and card["expected_outcome"] is None
            assert card["sources"][0]["sources"][0]["document_id"] == "remove"
            assert not card["execution_authorized"] and not first["resolution"]["execution_authorized"]
            payload = json.loads(provider.calls[-1]["input"])
            assert len(payload["historical_cases"]) == 1 and len(payload["historical_comments"]) == 1
            assert "expert@example.com" not in provider.calls[-1]["input"]
            first["resolution"]["actions"].clear()
            cached = await pipeline.analyze_and_resolve(TICKET)
            assert cached["cache_hit"] and len(cached["resolution"]["actions"]) == 1
            assert len(second["resolution"]["actions"]) == 1 and len(provider.calls) == 3
        finally:
            await pipeline.close()
    asyncio.run(run())


@pytest.mark.parametrize("variant", ["fabricated", "case_only"])
def test_invalid_resolve_evidence_falls_back_without_retry_and_preserves_analysis(variant):
    async def run():
        provider = ResolveProvider(variant)
        pipeline = TicketAnalysis(Retriever(), client=provider)
        try:
            result = await pipeline.analyze_and_resolve(TICKET)
            assert len(provider.calls) == 3 and result["status"] == "partial"
            assert result["resolution"]["status"] == "unavailable"
            assert result["filter"]["primary_document_ids"] == ["grant"]
            assert result["stages"]["resolve"]["error"]["type"] == "ValidationFailed"
        finally:
            await pipeline.close()
    asyncio.run(run())


@pytest.mark.parametrize("state", ["unfiltered_fallback", "needs_review", "unresolved"])
def test_unusable_filter_evidence_only_produces_a_clarification(state):
    async def run():
        provider = ResolveProvider()
        pipeline = TicketAnalysis(Retriever(), client=provider)
        try:
            analysis = await pipeline.analyze(TICKET)
            if state == "unresolved":
                analysis["filter"]["service"] = None
            else:
                analysis["filter"]["status"] = state
            result = await pipeline.resolve(TICKET, analysis)
            payload = json.loads(provider.calls[-1]["input"])
            assert not payload["historical_comments"] and not payload["historical_cases"]
            assert result["resolution"]["mode"] == "needs_information"
            assert not result["resolution"]["actions"]
            assert result["resolution"]["critical_question"]
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_resolution_rejects_a_different_ticket_and_cannot_propose_a_blocked_procedure():
    async def run():
        provider = ResolveProvider("blocked_procedure")
        pipeline = TicketAnalysis(Retriever(), client=provider)
        try:
            analysis = await pipeline.analyze(TICKET)
            with pytest.raises(ValueError, match="original facts"):
                await pipeline.resolve(replace(TICKET, summary="Other ticket"), analysis)
            assert len(provider.calls) == 2
            analysis["conflicts"] = [{"field": "service"}]
            result = await pipeline.resolve(TICKET, analysis)
            assert result["resolution"]["status"] == "unavailable"
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_http_resolve_and_feedback_persist_original_proposal_edits_and_actual_outcome(artifact, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path, _ = artifact
    provider = ResolveProvider()
    db_path = path.parent / "resolve-feedback.sqlite3"
    factory = lambda _: TicketAnalysis(Retriever(), client=provider)
    body = {"summary": TICKET.summary, "description": TICKET.description,
            "current_services": list(TICKET.current_services), "current_work_type": TICKET.current_work_type}
    with TestClient(create_app(path, db_path, analysis_factory=factory)) as client:
        assert client.post("/tickets/analyze", json=body).status_code == 200
        response = client.post("/tickets/resolve", json=body)
        assert response.status_code == 200
        result = response.json()
        assert "stages" not in result and result["stage_status"]["resolve"]["ok"]
        assert result["analysis_cache_hit"] and len(provider.calls) == 3
        proposal = result["resolution"]
        feedback = {"issue_id": "1", "issue_key": "DEMO-1", "recommended_solution": "Edited next step.",
                    "real_solution": "Requested the approved role; awaiting a response.",
                    "affected_business_aspect": "Access", "processed_at": "2026-09-25T00:00:00Z",
                    "source": "human_resolution_workflow", "resolution": {
                        "proposal": proposal,
                        "actions": [{"action_id": "A1", "decision": "edit", "edited_next_step": "Edited next step."}],
                        "reply_draft": "Please confirm the approved role.",
                        "actual_outcome": "Requested the approved role; awaiting a response."}}
        saved = client.post("/tickets/process", json=feedback)
        assert saved.status_code == 201
        assert client.post("/tickets/process", json=feedback).json() == saved.json()
        for field, value in [("action_id", "A999"), ("edited_next_step", "")]:
            invalid = deepcopy(feedback)
            invalid["resolution"]["actions"][0][field] = value
            assert client.post("/tickets/process", json=invalid).status_code == 422
        invalid = deepcopy(feedback)
        invalid["real_solution"] = ""
        assert client.post("/tickets/process", json=invalid).status_code == 422
        assert client.post("/tickets/resolve", json={**body, "analysis": result}).status_code == 422
    with sqlite3.connect(db_path) as db:
        records = db.execute("SELECT payload FROM feedback").fetchall()
    assert len(records) == 1
    record = json.loads(records[0][0])["resolution"]
    assert record["proposal"]["actions"][0]["next_step"] == "Provision the approved Archive role."
    assert record["actions"][0]["edited_next_step"] == "Edited next step."
    assert record["proposal"]["actions"][0]["required_checks"]
    with TestClient(create_app(path, db_path)) as client:
        assert client.post("/tickets/resolve", json=body).status_code == 503
