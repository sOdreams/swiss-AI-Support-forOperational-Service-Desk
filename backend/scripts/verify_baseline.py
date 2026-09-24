"""Compare public FAISS search against the existing NumPy experiment artifacts."""
import argparse
import json
from pathlib import Path

import numpy as np

from service_desk.retrieval import TicketQuery, TicketRetriever
from service_desk.retrieval.documents import comment_parts

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--artifact", type=Path, required=True)
parser.add_argument("--experiment", type=Path, required=True)
parser.add_argument("--examples", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
inputs = json.loads((args.experiment / "inputs.json").read_text())
reference = json.loads((args.experiment / "blind_top50.json").read_text())["minilm/SDC/SDC"]
old_index = np.load(args.experiment / "minilm_SDC_index.npz")
documents = [json.loads(line) for line in (args.artifact / "documents.jsonl").read_text().splitlines()]
assert [d["text"] for d in documents] == [d["SDC"] for d in inputs["documents"]]
chunks = json.loads((args.artifact / "chunks.json").read_text())
assert [c["owner"] for c in chunks] == old_index["owners"].tolist()
rows = json.loads(args.examples.read_text())["records"]
retriever = TicketRetriever.load(args.artifact)
id_to_owner = {d["document_id"]: i for i, d in enumerate(documents)}
checks = []
for i, row in enumerate(rows):
    hits = retriever.search(TicketQuery(row["Summary"], row["Description"],
                            tuple(comment_parts(c)[1] for c in row["All Comments"])))
    actual = [id_to_owner[h.document_id] for h in hits]
    error = float(np.max(np.abs(np.array([h.score for h in hits]) - reference["scores"][i])))
    expected = reference["ids"][i]
    expected_scores = dict(zip(expected, reference["scores"][i]))
    same_set = set(actual) == set(expected)
    differences = [{"rank": rank, "actual_group": a, "reference_group": b,
                    "reference_score_gap": abs(expected_scores.get(a, float("inf")) - expected_scores[b])}
                   for rank, (a, b) in enumerate(zip(actual, expected), 1) if a != b]
    near_ties_only = same_set and all(d["reference_score_gap"] <= 1e-6 for d in differences)
    per_id_error = max(abs(hit.score - expected_scores.get(owner, float("inf"))) for hit, owner in zip(hits, actual))
    checks.append({"example": i + 1, "same_top50_set": same_set,
                   "near_ties_only": near_ties_only, "rank_differences": differences,
                   "max_per_document_score_error": per_id_error, "top50_identical": actual == reference["ids"][i],
                   "top10_identical": actual[:10] == reference["ids"][i][:10],
                   "max_ranked_score_error": error})
report = {"index_version": retriever.manifest["index_version"], "examples": len(rows),
          "documents": len(documents), "chunks": len(chunks), "checks": checks,
          "note": "Migration parity against previous development runs; not ground-truth accuracy."}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n")
assert all(c["same_top50_set"] and c["near_ties_only"] and c["max_per_document_score_error"] < 1e-5 for c in checks), report
print(f"All {len(rows)} queries: identical Top-50 sets; any rank changes are near ties; score error < 1e-5")
