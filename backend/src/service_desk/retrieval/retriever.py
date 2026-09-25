"""Exact cosine retrieval. FAISS types stay inside this module."""
import json
from pathlib import Path
from threading import Lock

import faiss
import numpy as np

from .documents import DIMENSION, MODEL, RECIPE, REVISION, query_text
from .types import RetrievalHit, TicketQuery


def _load_encoder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL, revision=REVISION, device="cpu")


class TicketRetriever:
    @classmethod
    def load(cls, artifact_dir):
        path = Path(artifact_dir)
        manifest = json.loads((path / "manifest.json").read_text())
        expected = {"schema_version": 1, "model": MODEL, "revision": REVISION,
                    "dimension": DIMENSION, "metric": "cosine", "normalized": True, "recipe": RECIPE}
        if any(manifest.get(k) != v for k, v in expected.items()):
            raise ValueError("Incompatible retrieval manifest; rebuild with the current recipe")
        import hashlib
        for filename in ("index.faiss", "documents.jsonl", "chunks.json"):
            if hashlib.sha256((path / filename).read_bytes()).hexdigest() != manifest["checksums"][filename]:
                raise ValueError(f"Artifact checksum mismatch: {filename}")
        index = faiss.read_index(str(path / "index.faiss"))
        documents = [json.loads(line) for line in (path / "documents.jsonl").read_text().splitlines()]
        chunks = json.loads((path / "chunks.json").read_text())
        if not isinstance(index, faiss.IndexFlatIP) or index.d != DIMENSION or index.ntotal != len(chunks):
            raise ValueError("Incompatible FAISS index")
        if not documents or not chunks or len(documents) != manifest["documents"] or len(chunks) != manifest["chunks"]:
            raise ValueError("Invalid artifact counts")
        if any(not 0 <= c["owner"] < len(documents) for c in chunks):
            raise ValueError("Invalid chunk ownership")
        if set(c["owner"] for c in chunks) != set(range(len(documents))):
            raise ValueError("Document has no indexed chunks")
        if len({d["document_id"] for d in documents}) != len(documents):
            raise ValueError("Duplicate document IDs")
        vectors = index.reconstruct_n(0, index.ntotal)
        if not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5):
            raise ValueError("Index contains invalid or unnormalized vectors")
        instance = cls()
        instance.manifest = manifest
        instance._index, instance._documents, instance._chunks = index, documents, chunks
        instance._by_id = {d["document_id"]: d for d in documents}
        instance._encoder = _load_encoder()
        instance._lock = Lock()
        return instance

    def search(self, query: TicketQuery, top_k: int = 50) -> list[RetrievalHit]:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 50:
            raise ValueError("top_k must be between 1 and 50")
        text = query_text(query)
        if not text.strip():
            raise ValueError("Provide a title, description or comment")
        with self._lock:
            if len(self._encoder.tokenizer.encode(text)) > self._encoder.max_seq_length:
                raise ValueError("Query exceeds the model context; shorten the title, description or comments")
            vector = np.asarray(self._encoder.encode([text], normalize_embeddings=True), dtype="float32")
        if vector.shape != (1, DIMENSION) or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
            raise ValueError("Encoder produced an invalid query vector")
        faiss.normalize_L2(vector)
        # Exact all-chunk search preserves group max scores and deterministic ties.
        scores, ids = self._index.search(vector, self._index.ntotal)
        best = {}
        for score, chunk_id in zip(scores[0], ids[0]):
            chunk_id = int(chunk_id)
            owner = self._chunks[chunk_id]["owner"]
            candidate = (float(score), -chunk_id)
            if owner not in best or candidate > best[owner]:
                best[owner] = candidate
        # Owner order is sorted (title, description), matching the NumPy baseline.
        ranked = sorted(best, key=lambda owner: (-best[owner][0], owner))[:top_k]
        hits = []
        for rank, owner in enumerate(ranked, 1):
            doc = self._documents[owner]
            score, negative_chunk_id = best[owner]
            evidence = [{"body": e["body"], "occurrences": len(e["sources"]),
                         "sources": e["sources"][:3]} for e in doc["evidence"]]
            hits.append(RetrievalHit(doc["document_id"], rank, score, doc["summary"],
                                     self._chunks[-negative_chunk_id]["text"], doc["historical_count"], evidence))
        return hits

    def sources(self, document_id: str, offset: int = 0, limit: int = 50):
        """Page through complete comment provenance without changing search ranking."""
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid source pagination")
        doc = self._by_id[document_id]
        sources = [{"body": e["body"], **source} for e in doc["evidence"] for source in e["sources"]]
        return {"document_id": document_id, "total": len(sources),
                "offset": offset, "sources": sources[offset:offset + limit]}

    def describe(self, document_id: str):
        """Exact group text and source services for downstream interpretation."""
        doc = self._by_id[document_id]
        return {"document_id": document_id, "summary": doc["summary"],
                "description": doc["description"],
                "services": sorted({s for e in doc["evidence"] for ref in e["sources"]
                                    for s in ref["services"]})}

    def service_catalog(self):
        """Historical service names, with no team or assignee predictions."""
        return sorted({s for doc in self._documents for e in doc["evidence"]
                       for ref in e["sources"] for s in ref["services"]})

    def service_team_catalog(self):
        """Observed mappings, deduplicated by source row; never a live owner roster."""
        rows = {}
        for doc in self._documents:
            for comment in doc["evidence"]:
                for ref in comment["sources"]:
                    if len(ref["services"]) != 1:
                        continue  # Multi-service records do not establish a unique mapping.
                    service = ref["services"][0]
                    for team in ref.get("teams", []):
                        rows.setdefault(service, {}).setdefault(team, set()).add(ref["row_index"])
        return {service: [{"team": team, "historical_rows": len(indices), "example_row_indices": sorted(indices)[:3]}
                          for team, indices in sorted(teams.items())] for service, teams in sorted(rows.items())}
