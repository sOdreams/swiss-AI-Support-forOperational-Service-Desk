"""Evaluate triage confidence with a leakage-safe pseudo-holdout.

The historical data is split into a reference portion and a holdout portion.
For each holdout ticket, routing fields are hidden before prediction. The
report measures exact-match accuracy for Work type, Service, Team, and the
historical Assignee field, plus empirical confidence calibration.

Priority is checked only for matrix consistency because the README explicitly
states that historical Urgency/Impact/Priority values are random.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Iterable

from .triage_pipeline import (
    DEFAULT_TRAINING,
    LEVEL_LABELS,
    PRIORITY_MATRIX,
    TriageEngine,
    ROOT,
    as_list,
    load_json,
)


TARGET_FIELDS = (
    "Work type",
    "Affected Business or IT Services",
    "Service Team(s)",
    "Assignee",
    "Priority",
    "Urgency",
    "Impact",
    "Resolution",
)

_WORKER_ENGINE: TriageEngine | None = None


def hide_targets(record: dict[str, Any]) -> dict[str, Any]:
    hidden = dict(record)
    hidden["Work type"] = ""
    hidden["Affected Business or IT Services"] = []
    hidden["Service Team(s)"] = []
    hidden["Assignee"] = None
    hidden["Priority"] = None
    hidden["Urgency"] = None
    hidden["Impact"] = None
    hidden["Resolution"] = None
    return hidden


def bucket_for(score: float, bins: int = 5) -> int:
    return min(bins - 1, max(0, int(score * bins)))


def calibration_table(observations: Iterable[tuple[float, bool]], bins: int = 5) -> dict[str, Any]:
    grouped: dict[int, list[tuple[float, bool]]] = defaultdict(list)
    observations = list(observations)
    for score, correct in observations:
        grouped[bucket_for(score, bins)].append((score, correct))

    rows = []
    weighted_error = 0.0
    total = max(len(observations), 1)
    for index in range(bins):
        values = grouped.get(index, [])
        lower = index / bins
        upper = (index + 1) / bins
        if values:
            average_confidence = sum(score for score, _ in values) / len(values)
            accuracy = sum(1 for _, correct in values if correct) / len(values)
            weighted_error += len(values) / total * abs(average_confidence - accuracy)
        else:
            average_confidence = None
            accuracy = None
        rows.append(
            {
                "range": f"[{lower:.1f}, {upper:.1f})" if index < bins - 1 else f"[{lower:.1f}, 1.0]",
                "count": len(values),
                "average_confidence": round(average_confidence, 4) if average_confidence is not None else None,
                "accuracy": round(accuracy, 4) if accuracy is not None else None,
            }
        )

    return {"bins": rows, "ece": round(weighted_error, 4)}


def metric_summary(correct: list[bool], scores: list[float]) -> dict[str, Any]:
    accuracy = sum(correct) / max(len(correct), 1)
    return {
        "count": len(correct),
        "accuracy": round(accuracy, 4),
        "average_confidence": round(sum(scores) / max(len(scores), 1), 4),
        "accuracy_at_confidence_0_7": round(
            sum(value for value, score in zip(correct, scores) if score >= 0.7)
            / max(sum(1 for score in scores if score >= 0.7), 1),
            4,
        ),
        "count_at_confidence_0_7": sum(1 for score in scores if score >= 0.7),
        "calibration": calibration_table(zip(scores, correct)),
    }


def evaluate_one(
    engine: TriageEngine,
    holdout_index: int,
    gold: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    """Evaluate one hidden ticket; safe to run in a worker process."""

    hidden = hide_targets(gold)
    retrieved = engine.retrieve(hidden, top_k=top_k)
    work_type, work_confidence, _ = engine.infer_work_type(hidden)
    service, service_confidence, _ = engine.infer_service(hidden, retrieved)
    assignee, team, owner_confidence, _ = engine.infer_owner(hidden, service, retrieved, work_type)
    priority = engine.infer_urgency_impact(hidden, work_type, service)

    gold_services = as_list(gold.get("Affected Business or IT Services"))
    gold_teams = as_list(gold.get("Service Team(s)"))
    gold_assignee = str(gold.get("Assignee") or "").strip()
    comparisons = {
        "work_type": (work_type == gold.get("Work type"), work_confidence),
        "service": (bool(gold_services) and service == gold_services[0], service_confidence),
        "team": (bool(gold_teams) and team == gold_teams[0], service_confidence),
        "assignee": (bool(gold_assignee) and assignee == gold_assignee, owner_confidence),
    }

    urgency_score = LEVEL_LABELS.index(priority["urgency"])
    impact_score = LEVEL_LABELS.index(priority["impact"])
    priority_consistent = PRIORITY_MATRIX[urgency_score][impact_score] == priority["priority"]

    example = {
        "training_index": holdout_index,
        "summary": gold.get("Summary", ""),
        "gold": {
            "work_type": gold.get("Work type"),
            "service": gold_services,
            "team": gold_teams,
            "assignee": gold_assignee,
        },
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
    return {
        "comparisons": comparisons,
        "priority_consistent": priority_consistent,
        "example": example,
    }


def initialize_worker(reference_records: list[dict[str, Any]]) -> None:
    global _WORKER_ENGINE
    _WORKER_ENGINE = TriageEngine(reference_records)


def evaluate_one_worker(item: tuple[int, dict[str, Any], int]) -> dict[str, Any]:
    if _WORKER_ENGINE is None:
        raise RuntimeError("worker engine was not initialized")
    holdout_index, gold, top_k = item
    return evaluate_one(_WORKER_ENGINE, holdout_index, gold, top_k)


def evaluate(
    training_path: Path,
    sample_size: int,
    seed: int,
    top_k: int,
    workers: int = 1,
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
    metric_correct: dict[str, list[bool]] = defaultdict(list)
    metric_scores: dict[str, list[float]] = defaultdict(list)
    examples: list[dict[str, Any]] = []
    priority_consistent = 0

    items = [(holdout_index, training[holdout_index], top_k) for holdout_index in holdout_indices]
    if workers > 1:
        chunksize = max(1, len(items) // (workers * 4))
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=initialize_worker,
            initargs=(reference,),
        ) as executor:
            evaluations = executor.map(evaluate_one_worker, items, chunksize=chunksize)
            evaluated = list(evaluations)
    else:
        engine = TriageEngine(reference)
        evaluated = [evaluate_one(engine, holdout_index, gold, top_k) for holdout_index, gold, _ in items]

    for result in evaluated:
        comparisons = result["comparisons"]
        for metric, (correct, score) in comparisons.items():
            metric_correct[metric].append(correct)
            metric_scores[metric].append(score)
        if result["priority_consistent"]:
            priority_consistent += 1
        if len(examples) < 25:
            examples.append(result["example"])

    metrics = {
        metric: metric_summary(metric_correct[metric], metric_scores[metric])
        for metric in ("work_type", "service", "team", "assignee")
    }
    return {
        "evaluation": "pseudo_holdout",
        "seed": seed,
        "training_records": len(training),
        "reference_records": len(reference),
        "holdout_records_evaluated": len(holdout_indices),
        "top_k": top_k,
        "workers": workers,
        "metrics": metrics,
        "priority_matrix_consistency": round(priority_consistent / max(len(holdout_indices), 1), 4),
        "examples": examples,
        "interpretation": {
            "warning": "Historical Assignee and Priority labels are noisy in the supplied data.",
            "confidence_note": "Confidence is heuristic until calibrated against this report.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate triage with a leakage-safe pseudo-holdout.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1, help="CPU worker processes; each worker keeps its own reference index")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "pseudo_holdout_report.json")
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be at least 1")
    report = evaluate(args.training, args.sample_size, args.seed, args.top_k, workers=args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Reference records: {report['reference_records']}")
    print(f"Holdout records evaluated: {report['holdout_records_evaluated']}")
    print(f"Worker processes: {report['workers']}")
    for metric, values in report["metrics"].items():
        print(
            f"{metric}: accuracy={values['accuracy']:.3f}, "
            f"avg_confidence={values['average_confidence']:.3f}, "
            f"ECE={values['calibration']['ece']:.3f}"
        )
    print(f"Priority matrix consistency: {report['priority_matrix_consistency']:.3f}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
