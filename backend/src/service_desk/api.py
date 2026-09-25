"""HTTP boundary for retrieval; routing and feedback persistence are separate."""
from contextlib import asynccontextmanager
from dataclasses import asdict
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from .feedback import FeedbackStore, ProcessTicketPayload
from .retrieval import TicketQuery, TicketRetriever
from .analysis import AnalysisConfig, TicketAnalysis, TicketInput


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(default="", max_length=10000)
    description: str | None = Field(default=None, max_length=50000)
    comments: list[str] = Field(default_factory=list, max_length=100)
    top_k: int = Field(default=50, ge=1, le=50, strict=True)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(default="", max_length=10000)
    description: str | None = Field(default=None, max_length=50000)
    comments: list[str] = Field(default_factory=list, max_length=100)
    current_services: list[str] = Field(default_factory=list, max_length=30)
    current_work_type: str | None = Field(default=None, max_length=100)


def create_app(artifact_dir=None, feedback_path=None, *, analysis_factory=None):
    @asynccontextmanager
    async def lifespan(app):
        path = artifact_dir or os.environ.get("RETRIEVAL_ARTIFACT_DIR")
        if not path:
            raise RuntimeError("Set RETRIEVAL_ARTIFACT_DIR to a built retrieval artifact")
        app.state.retriever = TicketRetriever.load(path)
        app.state.feedback = FeedbackStore(feedback_path or os.environ.get("FEEDBACK_DB", "data/feedback.sqlite3"))
        key = os.environ.get("OPENAI_API_KEY")
        app.state.analysis = analysis_factory(app.state.retriever) if analysis_factory else (
            TicketAnalysis(app.state.retriever, api_key=key, config=AnalysisConfig(
                model=os.environ.get("ANALYSIS_MODEL", AnalysisConfig.model),
                reasoning_effort=os.environ.get("ANALYSIS_REASONING_EFFORT", AnalysisConfig.reasoning_effort),
            )) if key else None)
        try:
            yield
        finally:
            if app.state.analysis:
                await app.state.analysis.close()

    app = FastAPI(title="Service Desk Retrieval", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.get("/health")
    def health():
        return {"status": "ok", "index_version": app.state.retriever.manifest["index_version"],
                "analysis_available": app.state.analysis is not None}

    @app.post("/tickets/analyze")
    async def analyze(body: AnalysisRequest):
        return await run_analysis(body, "analyze")

    @app.post("/tickets/resolve")
    async def resolve(body: AnalysisRequest):
        return await run_analysis(body, "analyze_and_resolve")

    @app.post("/tickets/resolve-fast")
    async def resolve_fast(body: AnalysisRequest):
        """Experimental joint inference; explicitly selected, never the UI default."""
        return await run_analysis(body, "analyze_and_resolve_fast")

    async def run_analysis(body, method):
        if not app.state.analysis:
            raise HTTPException(503, "Ticket analysis is not configured on this server")
        if sum(map(len, body.comments)) > 50000:
            raise HTTPException(422, "Comments exceed the input size limit")
        if sum(map(len, body.current_services)) > 3000:
            raise HTTPException(422, "Service metadata exceeds the input size limit")
        try:
            result = await getattr(app.state.analysis, method)(TicketInput(
                body.summary, body.description or "", tuple(body.comments),
                tuple(body.current_services), body.current_work_type))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        # Raw provider text/usage is available to the Python benchmark, not
        # duplicated in the serving contract. No credential reaches the client.
        stages = result.pop("stages")
        result["stage_status"] = {name: {"ok": value["ok"], "error": value.get("error")}
                                  for name, value in stages.items()}
        return result

    @app.post("/retrieval/search")
    def search(body: SearchRequest):
        if sum(map(len, body.comments)) > 50000:
            raise HTTPException(422, "Comments exceed the input size limit")
        retriever = app.state.retriever
        try:
            hits = retriever.search(TicketQuery(body.summary, body.description or "", tuple(body.comments)), body.top_k)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"index_version": retriever.manifest["index_version"],
                "model": retriever.manifest["model"], "score_type": "cosine",
                "hits": [asdict(hit) for hit in hits]}

    @app.get("/retrieval/documents/{document_id}/sources")
    def sources(document_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        try:
            return app.state.retriever.sources(document_id, offset, limit)
        except KeyError as exc:
            raise HTTPException(404, "Unknown document") from exc

    @app.post("/tickets/process", status_code=201)
    def process_ticket(body: ProcessTicketPayload):
        return {"feedback_id": app.state.feedback.save(body), "saved": True}

    return app


app = create_app()
