"""Build an immutable, versioned FAISS artifact from historical Jira JSON."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import tempfile

import faiss
import numpy as np

from .documents import DIMENSION, MODEL, RECIPE, REVISION, build_documents, chunk_documents
from .retriever import _load_encoder


def _write_artifact(output: Path, documents, chunks, owners, vectors, dataset_hash):
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing artifact: {output}")
    vectors = np.array(vectors, dtype="float32", order="C", copy=True)
    if vectors.shape != (len(chunks), DIMENSION) or not np.isfinite(vectors).all():
        raise ValueError("Invalid embedding shape or values")
    if np.any(np.linalg.norm(vectors, axis=1) == 0):
        raise ValueError("Zero embedding")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(DIMENSION)
    index.add(vectors)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".retrieval-", dir=output.parent))
    try:
        faiss.write_index(index, str(staging / "index.faiss"))
        (staging / "documents.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in documents))
        (staging / "chunks.json").write_text(json.dumps([
            {"owner": int(owner), "text": text} for owner, text in zip(owners, chunks)
        ], ensure_ascii=False))
        checksums = {name: hashlib.sha256((staging / name).read_bytes()).hexdigest()
                     for name in ("index.faiss", "documents.jsonl", "chunks.json")}
        manifest = {"schema_version": 1, "model": MODEL, "revision": REVISION,
                    "dimension": DIMENSION, "metric": "cosine", "normalized": True,
                    "recipe": RECIPE, "dataset_sha256": dataset_hash,
                    "documents": len(documents), "chunks": len(chunks),
                    "chunk_token_budget": 248, "chunk_overlap": 32,
                    "checksums": checksums,
                    "packages": {name: importlib.metadata.version(name)
                                 for name in ("faiss-cpu", "numpy", "sentence-transformers")}}
        manifest["index_version"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:20]
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.rename(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def build(training_path: Path, output: Path):
    raw = training_path.read_bytes()
    documents = build_documents(json.loads(raw))
    encoder = _load_encoder()
    chunks, owners = chunk_documents(encoder, documents)
    vectors = encoder.encode(chunks, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
    return _write_artifact(output, documents, chunks, owners, vectors, hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.training, args.output), indent=2))


if __name__ == "__main__":
    main()
