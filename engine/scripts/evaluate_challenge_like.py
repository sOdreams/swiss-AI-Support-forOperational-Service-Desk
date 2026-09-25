"""Evaluate robustness against challenge-like missing and corrupted fields.

This is an internal validation tool. It uses the same deterministic 80/20
split as ``evaluate_pseudo_holdout.py`` but changes the observed holdout
records to resemble the official 20-ticket challenge:

* Service Team, Assignee, and Resolution are blank;
* a configurable fraction of Work type and Service values are wrong;
* Urgency and Impact are populated independently, with Priority regenerated
  from the README matrix so the observed fields remain structurally valid.

The original holdout records remain the gold labels and are never modified.
The pipeline is expected to rely on narrative evidence rather than these
corrupted target fields.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from .triage_pipeline import (
    DEFAULT_TRAINING,
    IMPACT_CATEGORIES,
    LEVEL_LABELS,
    PRIORITY_MATRIX,
    ROOT,
    TriageEngine,
    as_list,
    load_json,
)


DEFAULT_OUTPUT = ROOT / "outputs" / "challenge_like_4000_report.json"
_WORKER_ENGINE: TriageEngine | None = None


def challenge_like_record(
    gold: dict[str, Any],
    rng: random.Random,
    services: list[str],
    service_corruption_rate: float,
    work_type_corruption_rate: float,
) -> tuple[dict[str, Any], dict[str, bool]]:
    """Return a noisy observed ticket and flags describing its corruption."""

    observed = dict(gold)
    flags = {
        "work_type_corrupted": False,
        "service_corrupted": False,
        "team_blank": True,
        "assignee_blank": True,
        "resolution_blank": True,
    }

    if rng.random() < work_type_corruption_rate:
        observed["Work type"] = "Service Request" if gold.get("Work type") == "Incident" else "Incident"
        flags["work_type_corrupted"] = True

    gold_services = as_list(gold.get("Affected Business or IT Services"))
    if gold_services and rng.random() < service_corruption_rate:
        alternatives = [service for service in services if service not in gold_services]
        if alternatives:
            observed["Affected Business or IT Services"] = [rng.choice(alternatives)]
            flags["service_corrupted"] = True

    observed["Service Team(s)"] = []
    observed["Assignee"] = None
    observed["Resolution"] = None

    urgency = rng.randrange(len(LEVEL_LABELS))
    impact = rng.randrange(len(LEVEL_LABELS))
    observed["Urgency"] = LEVEL_LABELS[urgency]
    observed["Impact"] = LEVEL_LABELS[impact]
    observed["Priority"] = PRIORITY_MATRIX[urgency][impact]
    return observed, flags


def evaluate_one(
    engine: TriageEngine,
    holdout_index: int,
    gold: dict[str, Any],
    top_k: int,
    seed: int,
    services: list[str],
    service_corruption_rate: float,
    work_type_corruption_rate: float,
) -> dict[str, Any]:
    rng = random.Random(seed + holdout_index * 1009)
    observed, flags = challenge_like_record(
        gold,
        rng,
        services,
        service_corruption_rate,
        work_type_corruption_rate,
    )
    prediction = engine.triage(observed, top_k=top_k)

    gold_services = as_list(gold.get("Affected Business or IT Services"))
    gold_teams = as_list(gold.get("Service Team(s)"))
    predicted_services = prediction.get("affected_services") or []
    predicted_teams = prediction.get("service_teams") or []
    comparisons = {
        "work_type": prediction.get("work_type") == gold.get("Work type"),
        "service": bool(gold_services) and predicted_services[:1] == gold_services[:1],
        "team": bool(gold_teams) and predicted_teams[:1] == gold_teams[:1],
        "assignee": bool(str(gold.get("Assignee") or "").strip())
        and prediction.get("assignee") == str(gold.get("Assignee") or "").strip(),
    }
    urgency_score = LEVEL_LABELS.index(prediction["urgency"])
    impact_score = LEVEL_LABELS.index(prediction["impact"])
    priority_consistent = PRIORITY_MATRIX[urgency_score][impact_score] == prediction["priority"]

    return {
        "comparisons": comparisons,
        "priority_consistent": priority_consistent,
        "flags": flags,
        "example": {
            "training_index": holdout_index,
            "summary": gold.get("Summary", ""),
            "observed_fields": {
                "work_type": observed.get("Work type"),
                "service": as_list(observed.get("Affected Business or IT Services")),
                "team": as_list(observed.get("Service Team(s)")),
                "assignee": observed.get("Assignee"),
                "priority": observed.get("Priority"),
                "urgency": observed.get("Urgency"),
                "impact": observed.get("Impact"),
                "resolution": observed.get("Resolution"),
            },
            "gold": {
                "work_type": gold.get("Work type"),
                "service": gold_services,
                "team": gold_teams,
                "assignee": str(gold.get("Assignee") or "").strip(),
            },
            "prediction": {
                "work_type": prediction.get("work_type"),
                "service": predicted_services,
                "team": predicted_teams,
                "assignee": prediction.get("assignee"),
                "priority": prediction.get("priority"),
                "confidence": prediction.get("confidence", {}),
            },
        },
    }


def initialize_worker(reference_records: list[dict[str, Any]]) -> None:
    global _WORKER_ENGINE
    _WORKER_ENGINE = TriageEngine(reference_records)


def evaluate_one_worker(item: tuple[Any, ...]) -> dict[str, Any]:
    if _WORKER_ENGINE is None:
        raise RuntimeError("worker engine was not initialized")
    return evaluate_one(_WORKER_ENGINE, *item)


def evaluate(
    training_path: Path,
    sample_size: int,
    seed: int,
    top_k: int,
    workers: int,
    service_corruption_rate: float,
    work_type_corruption_rate: float,
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
    reference_engine = TriageEngine(reference)
    services = sorted(reference_engine.services)
    items = [
        (
            holdout_index,
            training[holdout_index],
            top_k,
            seed,
            services,
            service_corruption_rate,
            work_type_corruption_rate,
        )
        for holdout_index in holdout_indices
    ]

    if workers > 1:
        chunksize = max(1, len(items) // (workers * 4))
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=initialize_worker,
            initargs=(reference,),
        ) as executor:
            evaluated = list(executor.map(evaluate_one_worker, items, chunksize=chunksize))
    else:
        evaluated = [evaluate_one(reference_engine, *item) for item in items]

    correct: dict[str, list[bool]] = defaultdict(list)
    corruption_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    priority_consistent = 0
    for result in evaluated:
        for metric, value in result["comparisons"].items():
            correct[metric].append(value)
        for name, value in result["flags"].items():
            if value:
                corruption_counts[name] += 1
        priority_consistent += int(result["priority_consistent"])
        if len(examples) < 25:
            examples.append(result["example"])

    metrics = {
        metric: {
            "count": len(values),
            "accuracy": round(sum(values) / max(len(values), 1), 4),
        }
        for metric, values in correct.items()
    }
    return {
        "evaluation": "challenge_like_pseudo_validation",
        "seed": seed,
        "training_records": len(training),
        "reference_records": len(reference),
        "holdout_records_evaluated": len(holdout_indices),
        "top_k": top_k,
        "workers": workers,
        "corruption_profile": {
            "service_corruption_rate": service_corruption_rate,
            "work_type_corruption_rate": work_type_corruption_rate,
            "team_blank_rate": 1.0,
            "assignee_blank_rate": 1.0,
            "resolution_blank_rate": 1.0,
            "priority_rule": "regenerated from independently populated urgency and impact",
        },
        "observed_corruption_counts": dict(corruption_counts),
        "metrics": metrics,
        "priority_matrix_consistency": round(priority_consistent / max(len(holdout_indices), 1), 4),
        "examples": examples,
        "interpretation": {
            "warning": "This is an internal robustness test, not the official challenge score.",
            "success_criterion": "Predictions should remain accurate despite corrupted target fields.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate challenge-like missing and corrupted fields.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--service-corruption-rate", type=float, default=0.10)
    parser.add_argument("--work-type-corruption-rate", type=float, default=0.10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be at least 1")
    for name, value in (
        ("--service-corruption-rate", args.service_corruption_rate),
        ("--work-type-corruption-rate", args.work_type_corruption_rate),
    ):
        if not 0.0 <= value <= 1.0:
            parser.error(f"{name} must be between 0 and 1")

    report = evaluate(
        args.training,
        args.sample_size,
        args.seed,
        args.top_k,
        args.workers,
        args.service_corruption_rate,
        args.work_type_corruption_rate,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Reference records: {report['reference_records']}")
    print(f"Holdout records evaluated: {report['holdout_records_evaluated']}")
    print(f"Worker processes: {report['workers']}")
    for metric, values in report["metrics"].items():
        print(f"{metric}: accuracy={values['accuracy']:.3f}")
    print(f"Priority matrix consistency: {report['priority_matrix_consistency']:.3f}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
