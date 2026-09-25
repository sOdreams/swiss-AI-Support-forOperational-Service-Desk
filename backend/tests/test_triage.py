import asyncio
from copy import deepcopy
import json
import sqlite3

from fastapi.testclient import TestClient

from service_desk.analysis import TicketAnalysis
from service_desk.analysis.triage import URGENCIES, IMPACTS, build_triage, calculate_priority
from service_desk.api import create_app
from service_desk.retrieval import TicketRetriever
from test_analysis import Provider, Retriever, TICKET
from test_retrieval import artifact


CATALOGUE = {"Archive": [{"team": "Access Operations", "historical_rows": 14, "example_row_indices": [1, 2, 3]}]}


class TriageProvider(Provider):
    async def create(self, **kwargs):
        response = await super().create(**kwargs)
        if kwargs["text"]["format"]["name"] == "ticket_clean":
            value = json.loads(response.output_text)
            value.update(urgency="Low", urgency_evidence_ids=["Q2"], impact="No direct impact / Information", impact_evidence_ids=["Q3"])
            response.output_text = json.dumps(value)
        return response


def test_all_25_priority_cells_match_the_published_matrix_and_unknowns_stay_unknown():
    expected_rows = [
        "Highest Highest High Medium Medium",
        "Highest High High Medium Low",
        "High High Medium Low Low",
        "Medium Medium Low Low Lowest",
        "Medium Low Low Lowest Lowest",
    ]
    for urgency, expected in zip(URGENCIES, expected_rows):
        assert [calculate_priority(urgency, impact) for impact in IMPACTS] == expected.split()
    for unknown in (None, "", "ASAP", "highest"):
        assert calculate_priority(unknown, IMPACTS[0]) is None
        assert calculate_priority(URGENCIES[0], unknown) is None


def test_cited_priority_catalogue_team_and_active_authors_use_no_extra_calls_or_search_inputs():
    async def run():
        provider = TriageProvider()
        retriever = Retriever()
        pipeline = TicketAnalysis(retriever, client=provider, routing_catalog=CATALOGUE)
        try:
            result = await pipeline.analyze(TICKET)
            priority, routing = result["triage"]["priority"], result["triage"]["routing"]
            assert priority["value"] == "Lowest" and priority["requires_review"]
            assert priority["urgency"]["evidence"][0]["text"] == "Grant Archive access to the new joiner."
            assert routing["team"] == "Access Operations" and routing["service"] == "Archive"
            assert routing["service_evidence"][0]["fact_id"] == "Q2"
            assert routing["assignee"] is None and routing["assignment_authorized"] is False
            assert routing["historical_contributors"][0]["author"] == "expert@example.com"
            assert routing["historical_contributors"][0]["evidence"][0]["document_id"] == "remove"
            assert len(provider.calls) == 2 and len(retriever.queries) == 1
            assert retriever.queries[0].summary == TICKET.summary
            assert all("Access Operations" not in call["input"] and "expert@example.com" not in call["input"] for call in provider.calls)
            await pipeline.analyze(TICKET)
            assert len(provider.calls) == 2
            pipeline.routing_catalog["Archive"][0]["team"] = "Changed catalogue team"
            changed = await pipeline.analyze(TICKET)
            assert not changed["cache_hit"] and changed["triage"]["routing"]["team"] == "Changed catalogue team"
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_unknown_evidence_conflicts_and_ambiguous_catalogues_withhold_supported_values():
    facts = {"Q1": {"source": "description", "text": "The operational queue is delayed."}}
    analysis = {"facts": facts, "clean": {"status": "ready", "interpretation": {
        "urgency": "High", "urgency_evidence_ids": [], "impact": "Significant / Large", "impact_evidence_ids": ["Q1"]}},
        "filter": {"status": "ready", "service": "Archive", "comments": [], "active_comment_ids": []}}
    assert build_triage(analysis, CATALOGUE)["priority"]["value"] is None
    analysis["clean"]["interpretation"]["urgency_evidence_ids"] = ["Q1"]
    assert build_triage(analysis, CATALOGUE)["priority"]["value"] == "High"
    ambiguous = deepcopy(CATALOGUE)
    ambiguous["Archive"].append({"team": "Another team", "historical_rows": 1, "example_row_indices": [10]})
    assert build_triage(analysis, ambiguous)["routing"]["team"] is None
    assert build_triage(analysis, {})["routing"]["status"] == "needs_information"
    analysis["conflicts"] = [{"field": "service"}]
    held = build_triage(analysis, CATALOGUE)
    assert held["priority"]["value"] is None and held["priority"]["proposed_value"] == "High"
    assert held["routing"]["team"] is None and not held["routing"]["historical_contributors"]
    assert held["priority"]["status"] == held["routing"]["status"] == "needs_review"
    missing = build_triage({})
    assert missing["priority"]["status"] == missing["routing"]["status"] == "unavailable"


def test_catalogue_counts_source_rows_once_and_ignores_ambiguous_service_records(artifact):
    retriever = TicketRetriever.load(artifact[0])
    doc = retriever._documents[0]
    doc["evidence"].append(deepcopy(doc["evidence"][0]))
    catalogue = retriever.service_team_catalog()
    assert catalogue["service0"] == [{"team": "team0", "historical_rows": 1, "example_row_indices": [0]}]
    for comment in doc["evidence"]:
        comment["sources"][0]["services"].append("Another service")
    assert "service0" not in retriever.service_team_catalog()


def test_http_triage_review_is_persisted_separately_from_the_actual_outcome(artifact):
    path, _ = artifact
    db_path = path.parent / "triage.sqlite3"
    factory = lambda _: TicketAnalysis(Retriever(), client=TriageProvider(), routing_catalog=CATALOGUE)
    with TestClient(create_app(path, db_path, analysis_factory=factory)) as client:
        response = client.post("/tickets/analyze", json={"summary": TICKET.summary, "description": TICKET.description})
        assert response.status_code == 200
        triage = response.json()["triage"]
        body = {"issue_id": "1", "issue_key": "TEST-1", "real_solution": "Asked for the target account; no access change made.",
                "affected_business_aspect": "Access", "processed_at": "2026-09-25T00:00:00Z",
                "source": "human_resolution_workflow", "triage": triage}
        first = client.post("/tickets/process", json=body)
        assert first.status_code == 201 and client.post("/tickets/process", json=body).json() == first.json()
        assert client.post("/tickets/process", json={**body, "triage": {"oversize": "x" * 100001}}).status_code == 422
    with sqlite3.connect(db_path) as db:
        records = db.execute("SELECT payload FROM feedback").fetchall()
    assert len(records) == 1 and json.loads(records[0][0])["triage"] == triage
