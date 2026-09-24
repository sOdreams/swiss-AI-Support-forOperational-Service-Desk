import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from service_desk.analysis import AnalysisConfig, TicketAnalysis, TicketInput
from service_desk.analysis.evidence import current_facts, prepare_evidence
from service_desk.analysis.contracts import validate_filter
from service_desk.api import create_app
from service_desk.retrieval.types import RetrievalHit
from test_retrieval import artifact  # shared synthetic artifact fixture


class Retriever:
    manifest = {"index_version": "synthetic-index", "model": "synthetic-embedding"}

    def __init__(self):
        self.queries = []

    def service_catalog(self):
        return ["Archive", "Payments"]

    def search(self, query, top_k):
        self.queries.append(query)
        assert top_k == 50
        evidence = [{"body": "Resolution: Granted Archive access after checking approval.",
                     "occurrences": 2, "sources": [{"row_index": 3, "comment_index": 1,
                     "ticket_id": "old", "author": "expert@example.com", "services": ["Archive"], "teams": ["Support"]}]}]
        return [RetrievalHit("grant", 1, .91, "Grant Archive access", "Original indexed text", 3, []),
                RetrievalHit("remove", 2, .87, "Remove Archive access", "Original indexed text", 4, evidence)]

    def describe(self, ident):
        return {"summary": "Grant Archive access" if ident == "grant" else "Remove Archive access",
                "description": "Grant standard Archive access." if ident == "grant" else "Remove inherited Archive access.",
                "services": ["Archive"]}


TICKET = TicketInput("Archive outage", "Grant Archive access to the new joiner. There is no outage.",
                     (), ("Payments",), "Incident")


class Provider:
    def __init__(self, *, invalid_filter=False, wait_for_both=False, slow_clean=False, conflict=False):
        self.responses = self
        self.calls = []
        self.started = set()
        self.both = asyncio.Event()
        self.invalid_filter, self.wait_for_both = invalid_filter, wait_for_both
        self.slow_clean, self.conflict = slow_clean, conflict
        self.closed = False

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        stage = kwargs["text"]["format"]["name"]
        self.started.add(stage)
        if len(self.started) == 2:
            self.both.set()
        if self.wait_for_both:
            await asyncio.wait_for(self.both.wait(), 1)
        if self.slow_clean and stage == "ticket_clean":
            await asyncio.sleep(10)
        data = json.loads(kwargs["input"])
        if stage == "ticket_clean":
            value = {"service": "Archive", "service_evidence_ids": ["Q2"],
                     "work_type": "Service Request", "work_type_evidence_ids": ["Q2"],
                     "title_conflict": True, "suggested_summary": "Archive access request",
                     "title_evidence_ids": ["Q3"], "questions": [], "reason": "The body explicitly requests access and denies an outage."}
        else:
            value = {"service": "Payments" if self.conflict else "Archive", "service_evidence_ids": ["Q2"],
                     "observed_stage": "request", "stage_evidence_ids": ["Q2"],
                     "primary_ids": [] if self.conflict else ["G1"], "reserve_ids": [], "comment_choices": [],
                     "questions": [], "reason": "Same access-grant workflow; removal is a different action."}
            if not self.conflict:
                value["comment_choices"] = [{"id": data["comments"][0]["id"], "status": "conditional",
                    "condition": "Verify the approved Archive role before provisioning.",
                    "evidence_stage": "request",
                    "evidence_ids": ["Q2"], "reason": "Related grant procedure; current approval not established."}]
            if self.invalid_filter:
                value["primary_ids"] = ["fabricated"]
        return SimpleNamespace(id="fake-response", model="fake-model", status="completed",
            usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 1, "output_tokens": 1}),
            output_text=json.dumps(value))

    async def close(self):
        self.closed = True


def test_clean_and_filter_are_concurrent_and_retain_independent_comment_sources():
    async def run():
        provider = Provider(wait_for_both=True); retriever = Retriever()
        pipeline = TicketAnalysis(retriever, client=provider)
        result = await pipeline.analyze(TICKET)
        assert result["status"] == "ready" and len(provider.calls) == 2
        assert retriever.queries[0].summary == TICKET.summary
        assert [h["rank"] for h in result["retrieval"]["hits"]] == [1, 2]
        assert [h["score"] for h in result["filter"]["candidates"]] == [.91, .87]
        assert result["filter"]["primary_document_ids"] == ["grant"]
        comment = result["filter"]["comments"][0]
        assert comment["sources"][0]["document_id"] == "remove"
        assert comment["execution_authorized"] is False and comment["requires_current_verification"] is True
        assert comment["status"] == "conditional" and comment["condition"]
        assert len([f for f in result["clean"]["fields"] if f["state"] == "propose_correction"]) == 3
        for request in provider.calls:
            payload = json.loads(request["input"])
            assert "current_services" not in payload and "current_work_type" not in payload
            assert "expert@example.com" not in request["input"] and "Support" not in request["input"]
            assert request["store"] is False
        await pipeline.close()
    asyncio.run(run())


def test_duplicate_requests_share_work_cache_copies_and_metadata_changes_invalidate():
    async def run():
        provider = Provider(wait_for_both=True)
        pipeline = TicketAnalysis(Retriever(), client=provider)
        first, second = await asyncio.gather(pipeline.analyze(TICKET), pipeline.analyze(TICKET))
        assert len(provider.calls) == 2
        first["filter"]["candidates"].clear()
        cached = await pipeline.analyze(TICKET)
        assert cached["cache_hit"] and len(cached["filter"]["candidates"]) == 2
        assert len(second["filter"]["candidates"]) == 2
        await pipeline.analyze(replace(TICKET, current_work_type="Service Request"))
        assert len(provider.calls) == 4
        pipeline.retriever.manifest = {"index_version": "changed-index", "model": "synthetic-embedding"}
        await pipeline.analyze(TICKET)
        assert len(provider.calls) == 6
        await pipeline.close()
    asyncio.run(run())


def test_filter_validation_failure_preserves_clean_and_unfiltered_reserve():
    async def run():
        provider = Provider(invalid_filter=True)
        pipeline = TicketAnalysis(Retriever(), client=provider)
        result = await pipeline.analyze(TICKET)
        assert result["status"] == "partial" and result["clean"]["status"] == "ready"
        assert len(provider.calls) == 3
        assert not result["filter"]["primary_document_ids"]
        assert all(g["role"] == "reserve" for g in result["filter"]["candidates"])
        assert result["filter"]["comments"][0]["status"] == "uncertain"
        assert not (await pipeline.analyze(TICKET))["cache_hit"]
        await pipeline.close()
    asyncio.run(run())


def test_clean_deadline_does_not_discard_filter_result():
    async def run():
        provider = Provider(slow_clean=True)
        pipeline = TicketAnalysis(Retriever(), client=provider, config=AnalysisConfig(stage_timeout_seconds=.1))
        result = await pipeline.analyze(TICKET)
        assert result["status"] == "partial"
        assert result["clean"]["status"] == "unavailable"
        assert result["filter"]["primary_document_ids"] == ["grant"]
        assert result["stages"]["clean"]["error"]["type"] == "TimeoutError"
        await pipeline.close()
    asyncio.run(run())


def test_disagreement_holds_service_correction_for_review():
    async def run():
        pipeline = TicketAnalysis(Retriever(), client=Provider(conflict=True))
        result = await pipeline.analyze(TICKET)
        assert result["status"] == "needs_review"
        assert result["clean"]["fields"][0]["state"] == "needs_review"
        assert result["conflicts"][0]["clean"] == "Archive"
        assert result["filter"]["status"] == "needs_review" and not result["filter"]["active_comment_ids"]
        await pipeline.close()
    asyncio.run(run())


def test_cancelling_one_waiter_preserves_shared_request():
    async def run():
        provider = Provider(wait_for_both=True)
        pipeline = TicketAnalysis(Retriever(), client=provider)
        first = asyncio.create_task(pipeline.analyze(TICKET))
        second = asyncio.create_task(pipeline.analyze(TICKET))
        await provider.both.wait()
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        assert (await second)["status"] == "ready" and len(provider.calls) == 2
        await pipeline.close()
    asyncio.run(run())


def test_facts_and_templates_preserve_literal_source_text():
    facts = current_facts(TICKET)
    assert facts["Q3"] == {"source": "description", "text": "There is no outage."}
    retriever = Retriever()
    model, originals, comments = prepare_evidence(retriever, retriever.search(TICKET, 50))
    assert len(model["templates"]) == 2 and len(comments) == 1
    assert originals["G2"]["document_id"] == "remove"
    assert "sources" not in model["comments"][0]


def test_http_contract_and_disabled_analysis(artifact, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path, _ = artifact
    with TestClient(create_app(path, path.parent / "feedback.sqlite3")) as client:
        assert client.post("/tickets/analyze", json={"summary": "q"}).status_code == 503
        assert client.get("/health").json()["analysis_available"] is False
    def factory(_):
        return TicketAnalysis(Retriever(), client=Provider())
    with TestClient(create_app(path, path.parent / "feedback.sqlite3", analysis_factory=factory)) as client:
        response = client.post("/tickets/analyze", json={"summary": TICKET.summary, "description": TICKET.description,
            "current_services": list(TICKET.current_services), "current_work_type": TICKET.current_work_type})
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "ready" and "stages" not in result
        assert result["stage_status"]["filter"]["ok"]
        assert client.post("/tickets/analyze", json={}).status_code == 422
        assert client.post("/tickets/analyze", json={"summary": "q", "comments": ["x" * 50001]}).status_code == 422
        assert client.post("/tickets/analyze", json={"summary": "q", "api_key": "invalid"}).status_code == 422


def test_condition_cannot_override_a_different_or_unknown_failure_stage():
    groups = {"G1": {"services": ["Archive"]}}
    comments = {"E1": {"services": ["Archive"]}}
    value = {"service": "Archive", "service_evidence_ids": ["Q1"], "primary_ids": [], "reserve_ids": [],
             "observed_stage": "external_delivery", "stage_evidence_ids": ["Q1"],
             "comment_choices": [{"id": "E1", "status": "conditional", "condition": "Check the internal consumer.",
                                   "evidence_ids": ["Q1"], "evidence_stage": "internal_processing"}]}
    assert validate_filter(value, groups, comments)
    value["comment_choices"][0]["status"] = "uncertain"
    value["comment_choices"][0]["condition"] = ""
    assert not validate_filter(value, groups, comments)
    value["observed_stage"] = "unknown"
    value["comment_choices"][0]["status"] = "reference"
    assert validate_filter(value, groups, comments)
