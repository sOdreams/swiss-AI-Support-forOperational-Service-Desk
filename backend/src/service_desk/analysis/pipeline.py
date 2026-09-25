"""Parallel clean/filter with optional resolution, validation and memoization."""
import asyncio
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import time

import jsonschema
from openai import AsyncOpenAI

from ..retrieval import TicketQuery
from ..retrieval.types import RetrievalHit
from .contracts import clean_result, clean_schema, filter_result, filter_schema, validate_clean, validate_filter
from .evidence import current_facts, prepare_evidence
from .prompts import CLEAN_PROMPT, FILTER_PROMPT
from .resolution import RESOLVE_PROMPT, resolution_context, resolution_schema, validate_resolution, resolution_result


@dataclass(frozen=True)
class TicketInput:
    summary: str = ""
    description: str = ""
    comments: tuple[str, ...] = ()
    current_services: tuple[str, ...] = ()
    current_work_type: str | None = None


@dataclass(frozen=True)
class AnalysisConfig:
    model: str = "gpt-5.5-2026-04-23"
    reasoning_effort: str = "none"
    max_concurrent_calls: int = 6
    stage_timeout_seconds: float = 45.0
    cache_ttl_seconds: float = 300.0
    cache_size: int = 64

    def __post_init__(self):
        if self.max_concurrent_calls < 2 or self.stage_timeout_seconds <= 0 or self.cache_size < 0 or self.cache_ttl_seconds < 0:
            raise ValueError("Invalid analysis limits")
        if self.reasoning_effort not in {"none", "low", "medium", "high"}:
            raise ValueError("Unsupported reasoning effort")


def _safe_error(exc):
    # Do not return provider messages, headers, request bodies or credentials.
    return {"type": type(exc).__name__, "http_status": getattr(exc, "status_code", None)}


class TicketAnalysis:
    def __init__(self, retriever=None, *, service_catalog=None, api_key=None, config=None, client=None):
        self.retriever = retriever
        self.config = config or AnalysisConfig()
        if service_catalog is None and retriever is None:
            raise ValueError("Provide a retriever or an explicit service_catalog")
        self.catalog = list(service_catalog) if service_catalog is not None else retriever.service_catalog()
        self.client = client or AsyncOpenAI(api_key=api_key, base_url="https://api.openai.com/v1",
                                            timeout=self.config.stage_timeout_seconds, max_retries=0)
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_calls)
        self._cache = OrderedDict()
        self._inflight = {}

    async def close(self):
        pending = list(self._inflight.values())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await self.client.close()

    async def analyze(self, ticket: TicketInput):
        """Default: clean in parallel with original-text retrieval and filtering."""
        return await self._analyze(ticket, "parallel")

    async def analyze_clean_first(self, ticket: TicketInput):
        """Experimental: clean, retrieve with a proposed title, filter original facts."""
        return await self._analyze(ticket, "clean_first")

    async def analyze_and_resolve(self, ticket: TicketInput):
        """Reuse analysis, then make one additional call for reviewable next steps."""
        return await self._analyze(ticket, "resolve")

    async def _analyze(self, ticket, workflow):
        if self.retriever is None:
            raise ValueError("analyze requires a retriever; clean/filter can run independently")
        if not any(s.strip() for s in (ticket.summary, ticket.description, *ticket.comments)):
            raise ValueError("Provide a title, description or comment")
        started = time.perf_counter()
        key = hashlib.sha256(json.dumps({"ticket": asdict(ticket), "config": asdict(self.config), "workflow": workflow,
            "service_catalog": self.catalog,
            "index_version": self.retriever.manifest["index_version"],
            "prompts": [CLEAN_PROMPT, FILTER_PROMPT] + ([RESOLVE_PROMPT] if workflow == "resolve" else [])}, sort_keys=True).encode()).hexdigest()
        cached = self._cache.get(key)
        if cached and cached[0] > time.monotonic():
            self._cache.move_to_end(key)
            result = deepcopy(cached[1])
            result["cache_hit"] = True
            result["elapsed_ms"] = (time.perf_counter() - started) * 1000
            return result
        self._cache.pop(key, None)
        if key not in self._inflight:
            compute = {"parallel": self._compute, "clean_first": self._compute_clean_first,
                       "resolve": self._compute_with_resolution}[workflow]
            task = asyncio.create_task(compute(ticket))
            self._inflight[key] = task
            task.add_done_callback(lambda done: self._completed(key, done))
        result = deepcopy(await asyncio.shield(self._inflight[key]))
        result["cache_hit"] = False
        result["elapsed_ms"] = (time.perf_counter() - started) * 1000
        return result

    def _completed(self, key, task):
        self._inflight.pop(key, None)
        if task.cancelled() or task.exception() is not None:
            return
        result = task.result()
        if result["status"] == "ready" and self.config.cache_size:
            self._cache[key] = (time.monotonic() + self.config.cache_ttl_seconds, result)
            while len(self._cache) > self.config.cache_size:
                self._cache.popitem(last=False)

    async def _generate(self, stage, prompt, payload, schema, validate):
        calls = []
        started = time.perf_counter()
        try:
            # One call per branch; admission waiting is part of the deadline.
            return await asyncio.wait_for(self._call(stage, prompt, payload, schema, validate, calls),
                                          timeout=self.config.stage_timeout_seconds)
        except Exception as exc:
            return {"ok": False, "value": None, "error": _safe_error(exc), "calls": calls,
                    "seconds": time.perf_counter() - started}

    async def _call(self, stage, prompt, payload, schema, validate, calls):
        started = time.perf_counter()
        async with self._semaphore:
            call_started = time.perf_counter()
            response = await self.client.responses.create(
                model=self.config.model, instructions=prompt,
                input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                reasoning={"effort": self.config.reasoning_effort}, max_output_tokens=1500,
                store=False, text={"verbosity": "low", "format": {"type": "json_schema", "name": stage,
                                                                          "strict": True, "schema": schema}},
            )
        record = {"attempt": 1, "seconds": time.perf_counter() - call_started,
                  "response_id": response.id, "model": response.model,
                  "usage": response.usage.model_dump() if response.usage else {},
                  "status": response.status, "output_text": response.output_text}
        calls.append(record)
        if response.status != "completed" or not response.output_text:
            return {"ok": False, "value": None, "error": {"type": "IncompleteOrRefused"},
                    "calls": calls, "seconds": time.perf_counter() - started}
        try:
            value = json.loads(response.output_text)
            jsonschema.validate(value, schema)
            errors = validate(value)
        except (ValueError, jsonschema.ValidationError):
            errors = ["Invalid JSON or schema"]
        record["validation_errors"] = errors
        return {"ok": not errors, "value": value if not errors else None,
                "error": {"type": "ValidationFailed"} if errors else None,
                "calls": calls, "seconds": time.perf_counter() - started}

    async def clean(self, ticket: TicketInput):
        """Check current facts without retrieval; no implicit search or filtering."""
        facts = current_facts(ticket)
        if not facts:
            raise ValueError("Provide a title, description or comment")
        result = await self._generate("ticket_clean", CLEAN_PROMPT,
            {"current_facts": facts, "service_catalog": self.catalog}, clean_schema(facts, self.catalog),
            lambda value: validate_clean(value, facts))
        cleaned = clean_result(ticket, result["value"], facts) if result["ok"] else {
            "status": "unavailable", "fields": [], "questions": [], "reason": "Cleaning unavailable; current fields preserved."}
        return {"clean": cleaned, "facts": facts, "model_result": result}

    @staticmethod
    def query_after_clean(ticket: TicketInput, cleaning: dict):
        """Use only a proposed title correction; preserve body and comments verbatim.

        Service/work-type suggestions never enter the retrieval query. A failed
        clean or absent correction gives the original query. Original facts must
        match to prevent a saved result from another ticket being reused.
        """
        if cleaning["facts"] != current_facts(ticket):
            raise ValueError("Cleaning result does not belong to this ticket narrative")
        summary = ticket.summary
        if cleaning["model_result"]["ok"] and cleaning["clean"]["status"] == "ready":
            for field in cleaning["clean"]["fields"]:
                if (field["field"] == "summary" and field["state"] in {"propose_correction", "propose_completion"}
                        and isinstance(field["suggested"], str) and field["suggested"].strip()):
                    summary = field["suggested"]
        return TicketQuery(summary, ticket.description, ticket.comments)

    async def retrieve(self, query: TicketQuery):
        """Search an explicit query and return a self-contained, JSON-safe snapshot."""
        if self.retriever is None:
            raise ValueError("retrieve requires a retriever")
        started = time.perf_counter()
        hits = await asyncio.to_thread(self.retriever.search, query, 50)
        return {"retrieval": {"index_version": self.retriever.manifest["index_version"],
                              "model": self.retriever.manifest["model"], "score_type": "cosine",
                              "hits": [asdict(hit) for hit in hits]},
                "documents": {hit.document_id: self.retriever.describe(hit.document_id) for hit in hits},
                "query": asdict(query),
                "retrieval_ms": (time.perf_counter() - started) * 1000}

    async def filter(self, ticket: TicketInput, candidates: dict):
        """Filter supplied candidates without a retriever or prior clean call.

        Use a snapshot returned by retrieve(), including its exact documents.
        Neither the snapshot nor the current ticket is modified.
        """
        facts = current_facts(ticket)
        if not facts:
            raise ValueError("Provide a title, description or comment")
        hits = [RetrievalHit(**hit) for hit in candidates["retrieval"]["hits"]]
        ids, ranks = [hit.document_id for hit in hits], [hit.rank for hit in hits]
        if (len(ids) > 50 or len(set(ids)) != len(ids) or len(set(ranks)) != len(ranks)
                or any(type(rank) is not int or rank < 1 for rank in ranks) or ranks != sorted(ranks)):
            raise ValueError("Candidates require at most 50 unique IDs in original rank order")
        packet, originals, comments = prepare_evidence(candidates["documents"], hits)
        result = await self._generate("candidate_filter", FILTER_PROMPT,
            {"current_facts": facts, "service_catalog": self.catalog, **packet},
            filter_schema(facts, self.catalog, originals, comments),
            lambda value: validate_filter(value, originals, comments))
        return {"filter": filter_result(result["value"] if result["ok"] else None, originals, comments, facts),
                "model_result": result}

    async def _retrieve_and_filter(self, ticket, query=None):
        started = time.perf_counter()
        original = TicketQuery(ticket.summary, ticket.description, ticket.comments)
        query = query or original
        fallback = None
        try:
            try:
                candidates = await self.retrieve(query)
            except ValueError as exc:
                if query == original:
                    raise
                # A generated title can exceed the encoder's query limit.
                fallback = _safe_error(exc)
                candidates = await self.retrieve(original)
            retrieval_ms = (time.perf_counter() - started) * 1000
            filtered = await self.filter(ticket, candidates)
        except Exception as exc:
            return {"retrieval": None, "retrieval_ms": (time.perf_counter() - started) * 1000,
                    "filter": None, "model_result": {"ok": False, "error": _safe_error(exc), "calls": []}}
        return {"retrieval": candidates["retrieval"], "retrieval_ms": retrieval_ms,
                "query": candidates["query"], "query_fallback": fallback, **filtered}

    async def resolve(self, ticket: TicketInput, analysis: dict):
        """One independent model call using original facts and active evidence only."""
        payload, sources = resolution_context(ticket, analysis)
        result = await self._generate("ticket_resolve", RESOLVE_PROMPT, payload,
            resolution_schema(payload["current_facts"], sources),
            lambda value: validate_resolution(value, payload, sources))
        resolution = resolution_result(ticket, analysis, result["value"], sources, self.config.model) if result["ok"] else {
            "status": "unavailable", "actions": [], "critical_question": None, "reply_draft": "",
            "reason": "Next-step suggestions unavailable; review the original ticket and evidence."}
        return {"resolution": resolution, "model_result": result}

    async def _compute_with_resolution(self, ticket):
        started = time.perf_counter()
        result = await self.analyze(ticket)
        resolved = await self.resolve(ticket, result)
        result["analysis_cache_hit"] = result.pop("cache_hit")
        result["resolution"] = resolved["resolution"]
        result["stages"]["resolve"] = resolved["model_result"]
        result["timings"]["resolve_ms"] = resolved["model_result"]["seconds"] * 1000
        result["compute_ms"] = (time.perf_counter() - started) * 1000
        if not resolved["model_result"]["ok"]:
            result["status"] = "partial"
        return result

    async def _compute(self, ticket):
        started = time.perf_counter()
        # Both branches receive the original narrative. Clean predictions never
        # gate retrieval, and filter does not wait for the cleaning call.
        cleaning, evidence = await asyncio.gather(self.clean(ticket), self._retrieve_and_filter(ticket))
        return self._merge(cleaning, evidence, started)

    async def _compute_clean_first(self, ticket):
        started = time.perf_counter()
        cleaning = await self.clean(ticket)
        query = self.query_after_clean(ticket, cleaning)
        evidence = await self._retrieve_and_filter(ticket, query)
        result = self._merge(cleaning, evidence, started)
        result.update(workflow="clean_first", retrieval_query=evidence.get("query"),
                      query_fallback=evidence.get("query_fallback"))
        return result

    def _merge(self, cleaning, evidence, started):
        clean, cleaned, facts = cleaning["model_result"], cleaning["clean"], cleaning["facts"]
        filtered = evidence["filter"]
        conflicts = []
        if clean["ok"] and evidence["model_result"]["ok"]:
            a, b = clean["value"]["service"], filtered["service"]
            if a != b:
                conflicts.append({"field": "service", "clean": a, "filter": b,
                                  "action": "Review disagreement; no service correction is ready to apply."})
                for field in cleaned["fields"]:
                    if field["field"] == "affected_business_or_it_services":
                        field["state"] = "needs_review"
                filtered["status"] = "needs_review"
                filtered["proposed_primary_document_ids"] = filtered["primary_document_ids"]
                filtered["proposed_active_comment_ids"] = filtered["active_comment_ids"]
                filtered["primary_document_ids"] = []
                filtered["active_comment_ids"] = []
                for candidate in filtered["candidates"]:
                    if candidate["role"] == "primary":
                        candidate["role"] = "reserve"
                        candidate["filter_rank"] = None
                for comment in filtered["comments"]:
                    if comment["status"] in {"reference", "conditional"}:
                        comment["status"] = "uncertain"
        ready = clean["ok"] and evidence["model_result"]["ok"]
        return {"status": "needs_review" if conflicts else "ready" if ready else "partial",
                "clean": cleaned, "filter": filtered, "retrieval": evidence["retrieval"],
                "conflicts": conflicts, "facts": facts,
                "model": self.config.model, "reasoning_effort": self.config.reasoning_effort,
                "compute_ms": (time.perf_counter() - started) * 1000,
                "timings": {"clean_ms": clean["seconds"] * 1000,
                            "retrieval_ms": evidence["retrieval_ms"],
                            "filter_ms": evidence["model_result"].get("seconds", 0) * 1000},
                "stages": {"clean": clean, "filter": evidence["model_result"]}}
