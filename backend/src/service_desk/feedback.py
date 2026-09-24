"""Persist human review separately from retrieval artifacts."""
import json
from pathlib import Path
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RetrievalProvenance(BaseModel):
    index_version: str
    model: str
    shown_document_ids: list[str] = Field(max_length=50)
    selected_document_ids: list[str] = Field(max_length=50)

    @model_validator(mode="after")
    def selected_were_shown(self):
        if not set(self.selected_document_ids) <= set(self.shown_document_ids):
            raise ValueError("Selected evidence must be part of the shown candidates")
        return self


class ProcessTicketPayload(BaseModel):
    issue_id: str
    issue_key: str
    recommended_solution: str | None = Field(default=None, max_length=50000)
    real_solution: str | None = Field(default=None, max_length=50000)
    affected_business_aspect: str = Field(min_length=1, max_length=10000)
    processed_at: str
    source: Literal["human_resolution_workflow"]
    retrieval: RetrievalProvenance | None = None

    @model_validator(mode="after")
    def has_solution(self):
        if not (self.recommended_solution or "").strip() and not (self.real_solution or "").strip():
            raise ValueError("Provide a selected review step or an actual solution")
        return self


class FeedbackStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def save(self, payload: ProcessTicketPayload):
        # Content-derived identity makes a retry of the same submission idempotent.
        import hashlib
        body = json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False)
        identity = hashlib.sha256(body.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO feedback (id, payload) VALUES (?, ?)", (identity, body))
        return identity
