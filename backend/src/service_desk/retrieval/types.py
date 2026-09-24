from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TicketQuery:
    summary: str = ""
    description: str = ""
    comments: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalHit:
    document_id: str
    rank: int
    score: float
    summary: str
    matched_text: str
    historical_count: int
    evidence: list[dict[str, Any]]
