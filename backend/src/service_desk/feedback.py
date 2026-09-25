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


class ActionReview(BaseModel):
    action_id: str = Field(max_length=20)
    decision: Literal["unreviewed", "use", "edit", "not_applicable"]
    edited_next_step: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def edit_has_text(self):
        if self.decision == "edit" and not (self.edited_next_step or "").strip():
            raise ValueError("An edited action needs replacement text")
        if self.decision != "edit" and self.edited_next_step is not None:
            raise ValueError("Only edited actions may contain replacement text")
        return self


class ResolutionReview(BaseModel):
    proposal: dict
    actions: list[ActionReview] = Field(max_length=3)
    reply_draft: str = Field(max_length=10000)
    actual_outcome: str = Field(min_length=1, max_length=50000)

    @model_validator(mode="after")
    def review_matches_proposal(self):
        if not self.actual_outcome.strip():
            raise ValueError("Record the actual action or outcome separately from the proposal")
        if len(json.dumps(self.proposal)) > 200000 or self.proposal.get("status") != "ready" or not self.proposal.get("proposal_id"):
            raise ValueError("Provide a bounded, ready resolution proposal")
        cards = self.proposal.get("actions", [])
        if not isinstance(cards, list) or len(cards) > 3 or not all(isinstance(c, dict) and isinstance(c.get("id"), str) for c in cards):
            raise ValueError("Invalid proposal actions")
        ids = [c["id"] for c in cards]
        reviewed = [a.action_id for a in self.actions]
        if len(set(ids)) != len(ids) or len(set(reviewed)) != len(reviewed) or set(reviewed) != set(ids):
            raise ValueError("Provide one decision per proposed action")
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
    resolution: ResolutionReview | None = None
    triage: dict | None = None

    @model_validator(mode="after")
    def has_solution(self):
        if self.triage is not None and len(json.dumps(self.triage)) > 100000:
            raise ValueError("Triage review exceeds the size limit")
        if self.resolution and (self.real_solution or "").strip() != self.resolution.actual_outcome.strip():
            raise ValueError("The actual outcome must match the recorded human solution")
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
