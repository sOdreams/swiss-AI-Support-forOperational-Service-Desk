"""Optional retrieval backends for apples-to-apples triage experiments.

The default project remains dependency-free. Embedding and local LLM backends
are imported lazily so the lexical baseline continues to run without ML
packages.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any, Protocol

from .triage_pipeline import TriageEngine, RetrievedTicket, join_ticket_text


class Retriever(Protocol):
    def retrieve(self, ticket: dict[str, Any], top_k: int = 8) -> list[RetrievedTicket]:
        ...


class LexicalRetriever:
    """Adapter around the existing standard-library retriever."""

    name = "lexical"

    def __init__(self, engine: TriageEngine):
        self.engine = engine

    def retrieve(self, ticket: dict[str, Any], top_k: int = 8) -> list[RetrievedTicket]:
        return self.engine.retrieve(ticket, top_k=top_k)


def _require_sentence_transformers() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Embedding retrieval requires sentence-transformers. "
            "Create the ML Conda environment with: conda env create -f environment-ml.yml"
        ) from exc
    return SentenceTransformer


class EmbeddingRetriever:
    """Dense semantic retrieval over historical ticket narratives."""

    name = "embedding"

    def __init__(
        self,
        records: list[dict[str, Any]],
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str | None = None,
        batch_size: int = 64,
    ):
        sentence_transformer = _require_sentence_transformers()
        model_kwargs = {"device": device} if device else {}
        self.model_name = model_name
        self.model = sentence_transformer(model_name, **model_kwargs)
        self.records = records
        texts = [join_ticket_text(record) for record in records]
        self.embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_tensor=True,
        )

    def retrieve(self, ticket: dict[str, Any], top_k: int = 8) -> list[RetrievedTicket]:
        query = join_ticket_text(ticket)
        if not query.strip():
            return []
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_tensor=True,
        )[0]
        scores = self.embeddings @ query_embedding
        values, indices = scores.topk(min(top_k, len(self.records)))
        return [
            RetrievedTicket(index=int(index), score=round(float(score), 6))
            for score, index in zip(values.tolist(), indices.tolist())
        ]


class HybridRetriever:
    """Fuse lexical and dense retrieval while preserving deterministic ranking."""

    name = "hybrid"

    def __init__(
        self,
        engine: TriageEngine,
        embedding: EmbeddingRetriever,
        lexical_weight: float = 0.65,
        candidate_pool: int = 50,
    ):
        if not 0.0 <= lexical_weight <= 1.0:
            raise ValueError("lexical_weight must be between 0 and 1")
        self.engine = engine
        self.embedding = embedding
        self.lexical_weight = lexical_weight
        self.candidate_pool = candidate_pool

    def retrieve(self, ticket: dict[str, Any], top_k: int = 8) -> list[RetrievedTicket]:
        lexical = self.engine.retrieve(ticket, top_k=self.candidate_pool)
        dense = self.embedding.retrieve(ticket, top_k=self.candidate_pool)
        lexical_scores = {item.index: item.score for item in lexical}
        dense_scores = {item.index: item.score for item in dense}
        candidates = set(lexical_scores) | set(dense_scores)
        if not candidates:
            return []

        max_lexical = max(lexical_scores.values(), default=1.0) or 1.0
        combined: list[tuple[int, float]] = []
        for index in candidates:
            lexical_score = lexical_scores.get(index, 0.0) / max_lexical
            dense_score = (dense_scores.get(index, -1.0) + 1.0) / 2.0
            score = self.lexical_weight * lexical_score + (1.0 - self.lexical_weight) * dense_score
            combined.append((index, score))

        combined.sort(key=lambda item: (-item[1], item[0]))
        return [
            RetrievedTicket(index=index, score=round(score, 6))
            for index, score in combined[:top_k]
        ]


def _require_transformers() -> tuple[Any, Any]:
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Local LLM reranking requires transformers and accelerate. "
            "Install the ML environment and pass --llm-model."
        ) from exc
    return AutoTokenizer, AutoModelForCausalLM


class LocalLLMReranker:
    """Optional local Hugging Face reranker over a small candidate pool.

    The model is never asked to invent a service, team, or assignee. It only
    returns candidate positions, after which the normal pipeline constraints
    still determine the final structured fields.
    """

    name = "llm"

    def __init__(
        self,
        base: Retriever,
        records: list[dict[str, Any]],
        model_name: str,
        device_map: str = "auto",
        candidate_pool: int = 12,
        max_new_tokens: int = 128,
    ):
        tokenizer_cls, model_cls = _require_transformers()
        self.base = base
        self.records = records
        self.candidate_pool = candidate_pool
        self.max_new_tokens = max_new_tokens
        self.tokenizer = tokenizer_cls.from_pretrained(model_name)
        self.model = model_cls.from_pretrained(model_name, device_map=device_map, torch_dtype="auto")
        self.model_name = model_name

    def _prompt(self, ticket: dict[str, Any], candidates: list[RetrievedTicket]) -> str:
        query = join_ticket_text(ticket)
        candidate_lines = []
        for position, item in enumerate(candidates):
            record = self.records[item.index]
            candidate_lines.append(
                json.dumps(
                    {
                        "position": position,
                        "summary": record.get("Summary", ""),
                        "description": record.get("Description", ""),
                        "service": record.get("Affected Business or IT Services", []),
                        "work_type": record.get("Work type", ""),
                        "resolution": record.get("Resolution", ""),
                    },
                    ensure_ascii=False,
                )
            )
        return (
            "Rank the historical candidates by semantic relevance to the new Jira ticket. "
            "Return only a JSON array of candidate positions, best first. Do not invent positions.\n\n"
            f"NEW TICKET:\n{query}\n\nCANDIDATES:\n" + "\n".join(candidate_lines)
        )

    def _generate(self, prompt: str) -> str:
        if hasattr(self.tokenizer, "apply_chat_template"):
            messages = [
                {"role": "system", "content": "You are a precise ticket retrieval reranker."},
                {"role": "user", "content": prompt},
            ]
            inputs = self.tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
            )
        else:
            inputs = self.tokenizer(prompt, return_tensors="pt").input_ids
        inputs = inputs.to(self.model.device)
        generated = self.model.generate(inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        new_tokens = generated[0][inputs.shape[-1] :]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    @staticmethod
    def _parse_positions(text: str, size: int) -> list[int]:
        match = re.search(r"\[[^\]]*\]", text, flags=re.DOTALL)
        if not match:
            return []
        try:
            values = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        if not isinstance(values, list):
            return []
        positions = []
        for value in values:
            if isinstance(value, int) and 0 <= value < size and value not in positions:
                positions.append(value)
        return positions

    def retrieve(self, ticket: dict[str, Any], top_k: int = 8) -> list[RetrievedTicket]:
        candidates = self.base.retrieve(ticket, top_k=max(self.candidate_pool, top_k))
        if not candidates:
            return []
        response = self._generate(self._prompt(ticket, candidates))
        positions = self._parse_positions(response, len(candidates))
        reranked = [candidates[position] for position in positions]
        used = {item.index for item in reranked}
        reranked.extend(item for item in candidates if item.index not in used)
        return reranked[:top_k]
