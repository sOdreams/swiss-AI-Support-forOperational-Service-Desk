"""Compare lexical, embedding, hybrid, and optional local-LLM retrieval.

The evaluation keeps the existing leakage-safe 80/20 split and does not use
historical Urgency/Impact/Priority values as labels.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from .evaluate_pseudo_holdout import hide_targets
from .retrieval_variants import EmbeddingRetriever, HybridRetriever, LexicalRetriever, LocalLLMReranker
from .triage_pipeline import (
    DEFAULT_TRAINING,
    LEVEL_LABELS,
    PRIORITY_MATRIX,
    ROOT,
    TriageEngine,
    as_list,
    load_json,
)


def build_retriever(
    method: str,
    engine: TriageEngine,
    reference: list[dict[str, Any]],
    model_name: str,
    device: str | None,
    lexical_weight: float,
    candidate_pool: int,
    llm_model: str | None,
) -> Any:
    lexical = LexicalRetriever(engine)
    if method == "lexical":
        return lexical

    embedding = EmbeddingRetriever(reference, model_name=model_name, device=device)
    if method == "embedding":
        return embedding
    if method == "hybrid":
        return HybridRetriever(
            engine,
            embedding,
            lexical_weight=lexical_weight,
            candidate_pool=candidate_pool,
        )
    if method == "llm":
        if not llm_model:
            raise ValueError("--llm-model is required when --method llm is selected")
        base = HybridRetriever(
            engine,
            embedding,
            lexical_weight=lexical_weight,
            candidate_pool=candidate_pool,
        )
        return LocalLLMReranker(
            base,
            reference,
            model_name=llm_model,
            candidate_pool=candidate_pool,
        )
    raise ValueError(f"unknown method: {method}")


def evaluate(
    training_path: Path,
    method: str,
    sample_size: int,
    seed: int,
    top_k: int,
    model_name: str,
    device: str | None,
    lexical_weight: float,
    candidate_pool: int,
    llm_model: str | None,
    retrieval_vote_weight: float,
) -> dict[str, Any]:
    training = load_json(training_path)
    if not isinstance(training, list) or len(training) < 10:
        raise ValueError("training JSON must contain at least 10 records")

    indices = list(range(len(training)))
    random.Random(seed).shuffle(indices)
    split = int(len(indices) * 0.8)
    reference_indices = indices[:split]
    holdout_indices = indices[split:]
    if sample_size > 0:
        holdout_indices = holdout_indices[: min(sample_size, len(holdout_indices))]

    reference = [training[index] for index in reference_indices]
    engine = TriageEngine(reference)
    retriever = build_retriever(
        method,
        engine,
        reference,
        model_name,
        device,
        lexical_weight,
        candidate_pool,
        llm_model,
    )

    correct: dict[str, list[bool]] = defaultdict(list)
    retrieval_hits: dict[str, list[bool]] = defaultdict(list)
    priority_consistent = 0
    examples: list[dict[str, Any]] = []

    for holdout_index in holdout_indices:
        gold = training[holdout_index]
        hidden = hide_targets(gold)
        retrieved = retriever.retrieve(hidden, top_k=top_k)
        work_type, work_confidence, _ = engine.infer_work_type(hidden)
        service, service_confidence, _ = engine.infer_service(
            hidden,
            retrieved,
            retrieval_vote_weight=retrieval_vote_weight,
        )
        assignee, team, owner_confidence, _ = engine.infer_owner(hidden, service, retrieved, work_type)
        priority = engine.infer_urgency_impact(hidden, work_type, service)

        gold_services = as_list(gold.get("Affected Business or IT Services"))
        gold_teams = as_list(gold.get("Service Team(s)"))
        gold_assignee = str(gold.get("Assignee") or "").strip()
        correct["work_type"].append(work_type == gold.get("Work type"))
        correct["service"].append(bool(gold_services) and service == gold_services[0])
        correct["team"].append(bool(gold_teams) and team == gold_teams[0])
        correct["assignee"].append(bool(gold_assignee) and assignee == gold_assignee)

        retrieved_services = [
            as_list(reference[item.index].get("Affected Business or IT Services"))
            for item in retrieved
        ]
        flat_services = {service_name for services in retrieved_services for service_name in services}
        retrieval_hits["service_hit_at_k"].append(bool(gold_services and gold_services[0] in flat_services))
        retrieval_hits["service_hit_at_1"].append(
            bool(gold_services and retrieved_services and gold_services[0] in retrieved_services[0])
        )
        retrieved_types = [reference[item.index].get("Work type") for item in retrieved]
        retrieval_hits["work_type_hit_at_k"].append(gold.get("Work type") in retrieved_types)

        urgency_score = LEVEL_LABELS.index(priority["urgency"])
        impact_score = LEVEL_LABELS.index(priority["impact"])
        if PRIORITY_MATRIX[urgency_score][impact_score] == priority["priority"]:
            priority_consistent += 1

        if len(examples) < 25:
            examples.append(
                {
                    "training_index": holdout_index,
                    "summary": gold.get("Summary", ""),
                    "retrieved_indices": [item.index for item in retrieved],
                    "prediction": {
                        "work_type": work_type,
                        "service": service,
                        "team": team,
                        "assignee": assignee,
                        "confidence": {
                            "work_type": work_confidence,
                            "service": service_confidence,
                            "owner": owner_confidence,
                        },
                    },
                }
            )

    count = max(len(holdout_indices), 1)
    return {
        "evaluation": "retrieval_variants",
        "method": method,
        "seed": seed,
        "training_records": len(training),
        "reference_records": len(reference),
        "holdout_records_evaluated": len(holdout_indices),
        "top_k": top_k,
        "embedding_model": model_name if method in {"embedding", "hybrid", "llm"} else None,
        "llm_model": llm_model if method == "llm" else None,
        "lexical_weight": lexical_weight if method in {"hybrid", "llm"} else None,
        "retrieval_vote_weight": retrieval_vote_weight,
        "metrics": {
            key: {
                "count": len(values),
                "accuracy": round(sum(values) / max(len(values), 1), 4),
            }
            for key, values in correct.items()
        },
        "retrieval_metrics": {
            key: {
                "count": len(values),
                "recall": round(sum(values) / max(len(values), 1), 4),
            }
            for key, values in retrieval_hits.items()
        },
        "priority_matrix_consistency": round(priority_consistent / count, 4),
        "examples": examples,
        "interpretation": {
            "warning": "Historical Urgency/Impact/Priority labels are random and are not evaluated as accuracy targets.",
            "note": "Assignee exact match remains a noisy-label metric; retrieval gains should be judged primarily on Service, Team, and evidence recall.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare lexical, embedding, hybrid, and optional local-LLM retrieval.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--method", choices=("lexical", "embedding", "hybrid", "llm"), default="lexical")
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--candidate-pool", type=int, default=50)
    parser.add_argument("--lexical-weight", type=float, default=0.65)
    parser.add_argument("--embedding-model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--device", default=None, help="Embedding device, e.g. cuda or cpu; defaults to library selection")
    parser.add_argument("--llm-model", default=None, help="Local Hugging Face model used only with --method llm")
    parser.add_argument(
        "--retrieval-vote-weight",
        type=float,
        default=0.0,
        help="Additional rank-weighted Service evidence from retrieved candidates; default 0 keeps baseline behavior",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "retrieval_variants" / "retrieval_variant_report.json")
    args = parser.parse_args()

    report = evaluate(
        args.training,
        args.method,
        args.sample_size,
        args.seed,
        args.top_k,
        args.embedding_model,
        args.device,
        args.lexical_weight,
        args.candidate_pool,
        args.llm_model,
        args.retrieval_vote_weight,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Method: {report['method']}")
    print(f"Holdout records evaluated: {report['holdout_records_evaluated']}")
    for metric, values in report["metrics"].items():
        print(f"{metric}: {values['accuracy']:.3f}")
    for metric, values in report["retrieval_metrics"].items():
        print(f"{metric}: {values['recall']:.3f}")
    print(f"Priority matrix consistency: {report['priority_matrix_consistency']:.3f}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
