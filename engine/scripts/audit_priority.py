"""Audit narrative-based Urgency/Impact estimates for the challenge set.

The training labels for Urgency, Impact, and Priority are intentionally not
treated as ground truth. This report documents the rule evidence used for the
challenge predictions and verifies only the deterministic matrix constraint.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .triage_pipeline import (
    DEFAULT_CHALLENGE,
    DEFAULT_TRAINING,
    LEVEL_LABELS,
    PRIORITY_MATRIX,
    ROOT,
    TriageEngine,
    load_json,
)


DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "priority_audit"


def matrix_priority(urgency: Any, impact: Any) -> str | None:
    level_index = {label.casefold(): index for index, label in enumerate(LEVEL_LABELS)}
    urgency_index = level_index.get(str(urgency or "").casefold())
    impact_index = level_index.get(str(impact or "").casefold())
    if urgency_index is None or impact_index is None:
        return None
    return PRIORITY_MATRIX[urgency_index][impact_index]


def priority_rank(value: Any) -> int:
    """Return a comparable rank for a compact before/after audit."""
    order = {label.casefold(): index for index, label in enumerate(LEVEL_LABELS)}
    return order.get(str(value or "").casefold(), -1)


def audit(training_path: Path, challenge_path: Path) -> dict[str, Any]:
    training = load_json(training_path)
    challenge_payload = load_json(challenge_path)
    if not isinstance(training, list):
        raise ValueError("training JSON must be an array")
    challenge = challenge_payload.get("records") if isinstance(challenge_payload, dict) else challenge_payload
    if not isinstance(challenge, list):
        raise ValueError("challenge JSON must contain a records array")

    engine = TriageEngine(training)
    predictions = engine.triage_all(challenge)
    records: list[dict[str, Any]] = []
    supplied_consistent = 0
    predicted_consistent = 0

    for index, (ticket, result) in enumerate(zip(challenge, predictions), start=1):
        prediction = result["prediction"]
        current = result["current_fields"]
        supplied_matrix = matrix_priority(current.get("urgency"), current.get("impact"))
        predicted_matrix = matrix_priority(prediction.get("urgency"), prediction.get("impact"))
        if supplied_matrix and supplied_matrix.casefold() == str(current.get("priority") or "").casefold():
            supplied_consistent += 1
        if predicted_matrix and predicted_matrix == prediction.get("priority"):
            predicted_consistent += 1

        records.append(
            {
                "ticket_index": index,
                "summary": ticket.get("Summary", ""),
                "work_type": prediction.get("work_type"),
                "service": (prediction.get("affected_services") or [None])[0],
                "critical_service": prediction.get("reasoning_summary", {}).get("critical_service"),
                "supplied": {
                    "urgency": current.get("urgency"),
                    "impact": current.get("impact"),
                    "priority": current.get("priority"),
                    "matrix_priority": supplied_matrix,
                    "matrix_consistent": bool(
                        supplied_matrix
                        and supplied_matrix.casefold() == str(current.get("priority") or "").casefold()
                    ),
                },
                "predicted": {
                    "urgency": prediction.get("urgency"),
                    "impact": prediction.get("impact"),
                    "priority": prediction.get("priority"),
                    "matrix_priority": predicted_matrix,
                    "matrix_consistent": predicted_matrix == prediction.get("priority"),
                    "urgency_score": prediction.get("urgency_score"),
                    "impact_score": prediction.get("impact_score"),
                    "rule_trace": prediction.get("reasoning_summary", {}).get("priority_evidence", []),
                },
                "priority_delta": priority_rank(prediction.get("priority")) - priority_rank(current.get("priority")),
            }
        )

    return {
        "report": "priority_audit",
        "warning": "No Urgency/Impact accuracy is reported because training labels are random and not ground truth.",
        "training_records": len(training),
        "challenge_records": len(challenge),
        "supplied_matrix_consistent": supplied_consistent,
        "predicted_matrix_consistent": predicted_consistent,
        "records": records,
    }


def markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(report: dict[str, Any]) -> str:
    records = report["records"]
    lines = [
        "# Challenge Priority Audit",
        "",
        "This is a rule-evidence audit, not an accuracy report. The training set's Urgency/Impact/Priority labels are random, so they are not used as supervised targets.",
        "",
        f"- Training records: **{report['training_records']:,}**",
        f"- Challenge records: **{report['challenge_records']:,}**",
        f"- Supplied fields consistent with the matrix: **{report['supplied_matrix_consistent']}/{report['challenge_records']}**",
        f"- Predicted fields consistent with the matrix: **{report['predicted_matrix_consistent']}/{report['challenge_records']}**",
        "",
        "## Summary",
        "",
        "| # | Work type | Service | Summary | Current U/I/P | Predicted U/I/P | Priority change |",
        "|---:|---|---|---|---|---|---:|",
    ]
    for item in records:
        supplied = item["supplied"]
        predicted = item["predicted"]
        lines.append(
            "| {index} | {work_type} | {service} | {summary} | {su}/{si}/{sp} | {pu}/{pi}/{pp} | {delta:+d} |".format(
                index=item["ticket_index"],
                work_type=markdown_cell(item["work_type"]),
                service=markdown_cell(item["service"]),
                summary=markdown_cell(item["summary"]),
                su=markdown_cell(supplied["urgency"]),
                si=markdown_cell(supplied["impact"]),
                sp=markdown_cell(supplied["priority"]),
                pu=markdown_cell(predicted["urgency"]),
                pi=markdown_cell(predicted["impact"]),
                pp=markdown_cell(predicted["priority"]),
                delta=item["priority_delta"],
            )
        )

    lines.extend(["", "## Rule evidence", ""])
    for item in records:
        predicted = item["predicted"]
        lines.extend(
            [
                f"### Ticket {item['ticket_index']}: {item['summary']}",
                "",
                f"- Work type: `{item['work_type']}`",
                f"- Service: `{item['service']}`; critical service: `{item['critical_service']}`",
                f"- Predicted Urgency / Impact / Priority: `{predicted['urgency']} / {predicted['impact']} / {predicted['priority']}`",
                f"- Scores: urgency `{predicted['urgency_score']}`, impact `{predicted['impact_score']}`",
                "- Rules: " + "; ".join(predicted["rule_trace"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit challenge Urgency/Impact rules and matrix Priority.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--challenge", type=Path, default=DEFAULT_CHALLENGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = audit(args.training, args.challenge)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "priority_audit_report.json"
    markdown_path = args.output_dir / "priority_audit_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Audited {report['challenge_records']} challenge records.")
    print(f"Supplied matrix consistency: {report['supplied_matrix_consistent']}/{report['challenge_records']}")
    print(f"Predicted matrix consistency: {report['predicted_matrix_consistent']}/{report['challenge_records']}")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    main()
