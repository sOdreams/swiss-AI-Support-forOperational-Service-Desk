import asyncio
from dataclasses import replace
import json

import pytest

from service_desk.analysis import AnalysisConfig, TicketAnalysis
from service_desk.analysis.evidence import current_facts
from test_analysis import Provider, Retriever, TICKET


def test_clean_first_uses_corrected_title_but_filters_original_facts_and_separates_cache():
    async def run():
        provider, retriever = Provider(), Retriever()
        pipeline = TicketAnalysis(retriever, client=provider)
        try:
            parallel = await pipeline.analyze(TICKET)
            sequential = await pipeline.analyze_clean_first(TICKET)
            assert not sequential["cache_hit"] and len(provider.calls) == 4
            assert retriever.queries[0].summary == TICKET.summary
            assert retriever.queries[1].summary == "Archive access request"
            assert retriever.queries[1].description == TICKET.description
            assert retriever.queries[1].comments == TICKET.comments
            assert sequential["retrieval_query"]["summary"] == "Archive access request"
            assert sequential["workflow"] == "clean_first"
            assert not sequential["query_fallback"]
            payload = json.loads(provider.calls[-1]["input"])
            assert payload["current_facts"] == current_facts(TICKET)
            assert "current_services" not in payload
            assert sequential["retrieval"] == parallel["retrieval"]  # Deterministic test retriever.
            assert sequential["clean"]["fields"][2]["current"] == TICKET.summary
            assert (await pipeline.analyze_clean_first(TICKET))["cache_hit"]
            assert (await pipeline.analyze(TICKET))["cache_hit"]
            assert len(provider.calls) == 4
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_clean_first_continues_with_original_query_if_clean_times_out():
    async def run():
        retriever = Retriever()
        pipeline = TicketAnalysis(retriever, client=Provider(slow_clean=True),
                                  config=AnalysisConfig(stage_timeout_seconds=.1))
        try:
            result = await pipeline.analyze_clean_first(TICKET)
            assert result["status"] == "partial"
            assert retriever.queries[0].summary == TICKET.summary
            assert result["filter"]["primary_document_ids"] == ["grant"]
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_rejected_corrected_query_falls_back_to_original_without_more_model_calls():
    class RejectCorrection(Retriever):
        def search(self, query, top_k):
            if query.summary != TICKET.summary:
                raise ValueError("Generated query exceeds the encoder limit")
            return super().search(query, top_k)

    async def run():
        provider = Provider()
        pipeline = TicketAnalysis(RejectCorrection(), client=provider)
        try:
            result = await pipeline.analyze_clean_first(TICKET)
            assert result["status"] == "ready" and len(provider.calls) == 2
            assert result["query_fallback"]["type"] == "ValueError"
            assert result["retrieval_query"]["summary"] == TICKET.summary
        finally:
            await pipeline.close()
    asyncio.run(run())


def test_query_adapter_preserves_original_when_title_is_unchanged_and_rejects_stale_clean():
    async def run():
        pipeline = TicketAnalysis(service_catalog=["Archive", "Payments"], client=Provider())
        try:
            cleaned = await pipeline.clean(TICKET)
            with pytest.raises(ValueError, match="does not belong"):
                pipeline.query_after_clean(replace(TICKET, description="Different request"), cleaned)
            cleaned["clean"]["fields"][2]["state"] = "keep"
            query = pipeline.query_after_clean(TICKET, cleaned)
            assert query.summary == TICKET.summary
            assert query.description == TICKET.description
            # Service/work-type corrections still exist, but never enter the query.
            assert cleaned["clean"]["fields"][0]["state"] == "propose_correction"
        finally:
            await pipeline.close()
    asyncio.run(run())
