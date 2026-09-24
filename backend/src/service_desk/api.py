"""HTTP boundary for retrieval; routing and feedback persistence are separate."""
from contextlib import asynccontextmanager
from dataclasses import asdict
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from .feedback import FeedbackStore, ProcessTicketPayload
from .retrieval import TicketQuery, TicketRetriever


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(default="", max_length=10000)
    description: str | None = Field(default=None, max_length=50000)
    comments: list[str] = Field(default_factory=list, max_length=100)
    top_k: int = Field(default=50, ge=1, le=50, strict=True)


def create_app(artifact_dir=None, feedback_path=None):
    @asynccontextmanager
    async def lifespan(app):
        path = artifact_dir or os.environ.get("RETRIEVAL_ARTIFACT_DIR")
        if not path:
            raise RuntimeError("Set RETRIEVAL_ARTIFACT_DIR to a built retrieval artifact")
        app.state.retriever = TicketRetriever.load(path)
        app.state.feedback = FeedbackStore(feedback_path or os.environ.get("FEEDBACK_DB", "data/feedback.sqlite3"))
        yield

    app = FastAPI(title="Service Desk Retrieval", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.get("/health")
    def health():
        return {"status": "ok", "index_version": app.state.retriever.manifest["index_version"]}

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
