import hashlib
import json
from dataclasses import asdict

import numpy as np
import pytest
from fastapi.testclient import TestClient

from service_desk.api import create_app
from service_desk.retrieval import TicketQuery, TicketRetriever
from service_desk.retrieval.build import _write_artifact
from service_desk.retrieval.documents import build_documents, chunk_documents, query_text


class Tokenizer:
    def encode(self, text, **kwargs):
        return text.split()

    def decode(self, tokens, **kwargs):
        return " ".join(tokens)


class Encoder:
    tokenizer = Tokenizer()
    max_seq_length = 256

    def encode(self, texts, **kwargs):
        result = np.zeros((len(texts), 384), dtype="float32")
        result[:, 0] = 1
        return result


@pytest.fixture
def artifact(tmp_path, monkeypatch):
    from service_desk.retrieval import retriever
    monkeypatch.setattr(retriever, "_load_encoder", Encoder)
    docs = build_documents([
        {"Summary": f"Ticket {i:03}", "Description": "Description",
         "All Comments": [f"person{i}@example.com: Resolution: Fixed {i}"],
         "Service Team(s)": [f"team{i}"], "Affected Business or IT Services": [f"service{i}"]}
        for i in range(55)
    ])
    chunks = [d["text"] for d in docs] + ["second chunk for first document"]
    owners = list(range(55)) + [0]
    # Every document ties. A duplicated chunk must not consume a result slot.
    vectors = Encoder().encode(chunks)
    path = tmp_path / "index"
    _write_artifact(path, docs, chunks, owners, vectors, "test-dataset")
    return path, docs


def test_grouped_top50_and_reload(artifact):
    path, docs = artifact
    retriever = TicketRetriever.load(path)
    hits = retriever.search(TicketQuery(summary="query"))
    assert len(hits) == 50
    assert [h.rank for h in hits] == list(range(1, 51))
    assert [h.document_id for h in hits] == [d["document_id"] for d in docs[:50]]
    assert len({h.document_id for h in hits}) == 50
    assert all(h.score == pytest.approx(1.0) for h in hits)
    assert [asdict(h) for h in hits] == [asdict(h) for h in TicketRetriever.load(path).search(TicketQuery(summary="query"))]
    assert len(retriever.search(TicketQuery(summary="query"), top_k=10)) == 10


@pytest.mark.parametrize("query,top_k", [(TicketQuery(), 50), (TicketQuery(summary="word " * 300), 50),
                                              (TicketQuery(summary="q"), 0), (TicketQuery(summary="q"), 51)])
def test_invalid_queries(artifact, query, top_k):
    with pytest.raises(ValueError):
        TicketRetriever.load(artifact[0]).search(query, top_k)


def test_manifest_and_checksum_rejection(artifact):
    path, _ = artifact
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["dimension"] = 10
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest"):
        TicketRetriever.load(path)
    manifest["dimension"] = 384
    (path / "manifest.json").write_text(json.dumps(manifest))
    with (path / "index.faiss").open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        TicketRetriever.load(path)


def test_invalid_owners_rejected(artifact):
    path, _ = artifact
    chunks = json.loads((path / "chunks.json").read_text())
    chunks[0]["owner"] = 999
    (path / "chunks.json").write_text(json.dumps(chunks))
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["checksums"]["chunks.json"] = hashlib.sha256((path / "chunks.json").read_bytes()).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="ownership"):
        TicketRetriever.load(path)


def test_provenance_and_narrative_only():
    rows = [{"Summary": "Title", "Description": "Description", "Assignee": "unrelated",
             "All Comments": [f"{author}@example.com: Resolution: Fixed"],
             "Affected Business or IT Services": [service]}
            for author, service in [("alice", "A"), ("bob", "B")]]
    doc = build_documents(rows)[0]
    assert doc["historical_count"] == 2
    assert doc["text"] == "Title\nDescription\nResolution: Fixed"
    assert [s["author"] for s in doc["evidence"][0]["sources"]] == ["alice@example.com", "bob@example.com"]
    assert [s["services"] for s in doc["evidence"][0]["sources"]] == [["A"], ["B"]]
    assert query_text(TicketQuery("Title", "Description", ("alice@example.com: Note",))) == "Title\nDescription\nNote"


def test_chunks_keep_all_tokens():
    words = [str(i) for i in range(500)]
    chunks, owners = chunk_documents(Encoder(), [{"text": " ".join(words)}])
    assert owners == [0, 0, 0]
    assert max(len(c.split()) for c in chunks) <= 248
    assert chunks[0].split()[-32:] == chunks[1].split()[:32]
    assert set(" ".join(chunks).split()) == set(words)


def test_api_validation_and_provenance(artifact):
    path, docs = artifact
    with TestClient(create_app(path, path.parent / "feedback.sqlite3")) as client:
        result = client.post("/retrieval/search", json={"summary": "query", "description": None, "comments": []})
        assert result.status_code == 200
        data = result.json()
        assert len(data["hits"]) == 50
        assert data["hits"][-1]["rank"] == 50
        assert data["score_type"] == "cosine"
        assert "assignee" not in data
        assert client.post("/retrieval/search", json={}).status_code == 422
        assert client.post("/retrieval/search", json={"summary": "q", "top_k": 51}).status_code == 422
        assert client.post("/retrieval/search", json={"summary": "q", "service": "wrong"}).status_code == 422
        assert client.get("/health").json()["index_version"] == data["index_version"]
        sources = client.get(f"/retrieval/documents/{docs[0]['document_id']}/sources?limit=1").json()
        assert sources["total"] == 1
        assert sources["sources"][0]["author"] == "person0@example.com"
        assert client.get("/retrieval/documents/missing/sources").status_code == 404
        assert client.get(f"/retrieval/documents/{docs[0]['document_id']}/sources?offset=-1").status_code == 422
        assert client.options("/retrieval/search", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}).status_code == 200


def test_missing_artifact_configuration(monkeypatch):
    monkeypatch.delenv("RETRIEVAL_ARTIFACT_DIR", raising=False)
    with pytest.raises(RuntimeError, match="RETRIEVAL_ARTIFACT_DIR"):
        with TestClient(create_app()):
            pass


def test_immutable_artifact(artifact):
    with pytest.raises(FileExistsError):
        _write_artifact(artifact[0], [], [], [], [], "test")


def test_feedback_preserves_provenance_and_is_idempotent(artifact):
    import sqlite3
    path, docs = artifact
    database = path.parent / "feedback.sqlite3"
    before = (path / "index.faiss").read_bytes()
    with TestClient(create_app(path, database)) as client:
        retrieval = client.post("/retrieval/search", json={"summary": "query"}).json()
        payload = {"issue_id": "1", "issue_key": "T-1", "recommended_solution": None,
                   "real_solution": "Verified the fix", "affected_business_aspect": "Service continuity",
                   "processed_at": "2026-09-24T00:00:00Z", "source": "human_resolution_workflow",
                   "retrieval": {"index_version": retrieval["index_version"], "model": retrieval["model"],
                                 "shown_document_ids": [h["document_id"] for h in retrieval["hits"]],
                                 "selected_document_ids": [docs[0]["document_id"]]}}
        first = client.post("/tickets/process", json=payload)
        assert first.status_code == 201
        assert client.post("/tickets/process", json=payload).json() == first.json()
        with sqlite3.connect(database) as db:
            saved = db.execute("SELECT payload FROM feedback").fetchall()
        assert len(saved) == 1
        assert json.loads(saved[0][0])["retrieval"] == payload["retrieval"]
        payload["retrieval"]["selected_document_ids"] = ["not-shown"]
        assert client.post("/tickets/process", json=payload).status_code == 422
    assert (path / "index.faiss").read_bytes() == before


def test_faiss_matches_numpy_group_max_with_nonunit_vectors(tmp_path, monkeypatch):
    from service_desk.retrieval import retriever as module
    monkeypatch.setattr(module, "_load_encoder", Encoder)
    documents = build_documents([{"Summary": f"T{i:03}"} for i in range(55)])
    rng = np.random.default_rng(12)
    vectors = rng.normal(size=(110, 384)).astype("float32") * 7
    owners = np.repeat(np.arange(55), 2)
    path = tmp_path / "random"
    _write_artifact(path, documents, [f"chunk {i}" for i in range(110)], owners, vectors, "test")
    hits = TicketRetriever.load(path).search(TicketQuery(summary="q"))
    normalized = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    group_scores = normalized[:, 0].reshape(55, 2).max(axis=1)
    expected = np.argsort(-group_scores, kind="stable")[:50]
    assert [h.document_id for h in hits] == [documents[i]["document_id"] for i in expected]
    np.testing.assert_allclose([h.score for h in hits], group_scores[expected], atol=1e-6)
