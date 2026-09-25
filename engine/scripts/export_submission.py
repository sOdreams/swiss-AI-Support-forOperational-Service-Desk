"""Export a compact, score-oriented submission from the full triage output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .triage_pipeline import (
    LEVEL_LABELS,
    PRIORITY_MATRIX,
    RESOLUTION_STATUSES,
    ROOT,
    WORK_TYPES,
    load_json,
)


DEFAULT_INPUT = ROOT / "outputs" / "triage_challenge_latest.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "final_submission.json"


def compact_record(record: dict[str, Any]) -> dict[str, Any]:
    prediction = record.get("prediction", {})
    return {
        "ticket_index": record.get("ticket_index"),
        "Summary": record.get("summary", ""),
        "Work type": prediction.get("work_type"),
        "Affected Business or IT Services": prediction.get("affected_services", []),
        "Service Team(s)": prediction.get("service_teams", []),
        "Assignee": prediction.get("assignee"),
        "Urgency": prediction.get("urgency"),
        "Impact": prediction.get("impact"),
        "Priority": prediction.get("priority"),
        "Resolution": prediction.get("resolution"),
        "Resolution comment": prediction.get("resolution_comment", ""),
    }


def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(record.get("ticket_index"), int):
        errors.append("ticket_index is not an integer")
    if not str(record.get("Summary") or "").strip():
        errors.append("Summary is empty")
    if record.get("Work type") not in WORK_TYPES:
        errors.append("invalid Work type")

    services = record.get("Affected Business or IT Services") or []
    teams = record.get("Service Team(s)") or []
    if not isinstance(services, list) or len(services) != 1:
        errors.append("expected exactly one affected service")
    if not isinstance(teams, list) or len(teams) != 1:
        errors.append("expected exactly one service team")
    if record.get("Urgency") not in LEVEL_LABELS:
        errors.append("invalid Urgency")
    if record.get("Impact") not in LEVEL_LABELS:
        errors.append("invalid Impact")
    if record.get("Resolution") not in RESOLUTION_STATUSES:
        errors.append("invalid Resolution")
    if not str(record.get("Resolution comment") or "").strip():
        errors.append("Resolution comment is empty")

    if record.get("Urgency") in LEVEL_LABELS and record.get("Impact") in LEVEL_LABELS:
        urgency = LEVEL_LABELS.index(record["Urgency"])
        impact = LEVEL_LABELS.index(record["Impact"])
        expected = PRIORITY_MATRIX[urgency][impact]
        if record.get("Priority") != expected:
            errors.append(f"Priority is inconsistent with matrix; expected {expected}")
    return errors


def export_submission(input_path: Path, output_path: Path) -> dict[str, Any]:
    payload = load_json(input_path)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("input must be a triage output JSON object with a records array")

    records = [compact_record(record) for record in payload["records"]]
    validation_errors = {
        str(record.get("ticket_index")): validate_record(record)
        for record in records
        if validate_record(record)
    }
    indices = [record.get("ticket_index") for record in records]
    if len(indices) != len(set(indices)):
        validation_errors["submission"] = ["duplicate ticket_index values"]

    result = {
        "submission_format": "compact_jira_triage_v1",
        "source": input_path.name,
        "challenge_records": len(records),
        "validation_errors": validation_errors,
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a compact final triage submission.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = export_submission(args.input, args.output)
    print(f"Exported {result['challenge_records']} records to {args.output}")
    if result["validation_errors"]:
        print(f"Validation warnings: {len(result['validation_errors'])}")
    else:
        print("Validation: compact submission is structurally consistent.")


if __name__ == "__main__":
    main()
