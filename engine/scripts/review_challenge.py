"""Create a compact Markdown review report for the 20 challenge predictions."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .triage_pipeline import ROOT, load_json


DEFAULT_INPUT = ROOT / "outputs" / "triage_challenge_latest.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "challenge_review.md"


def markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def join_values(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item is not None)
    return "" if value is None else str(value)


def review_flags(record: dict[str, Any]) -> list[str]:
    current = record.get("current_fields", {})
    prediction = record.get("prediction", {})
    confidence = prediction.get("confidence", {})
    flags: list[str] = []

    current_work_type = str(current.get("work_type") or "").strip()
    if current_work_type and current_work_type != prediction.get("work_type"):
        flags.append("work type override")

    current_services = current.get("affected_services") or []
    predicted_services = prediction.get("affected_services") or []
    if current_services and predicted_services and current_services[0] != predicted_services[0]:
        flags.append("service override")

    if float(confidence.get("work_type", 1.0)) < 0.7:
        flags.append("low work-type confidence")
    if float(confidence.get("service", 1.0)) < 0.7:
        flags.append("low service confidence")
    if float(confidence.get("owner", 1.0)) < 0.7:
        flags.append("low owner confidence")
    if prediction.get("resolution") == "clarification":
        flags.append("clarification needed")
    return flags


def render(payload: dict[str, Any], source_name: str = DEFAULT_INPUT.name) -> str:
    records = payload.get("records", [])
    flagged = [(record, review_flags(record)) for record in records]
    review_queue = [(record, flags) for record, flags in flagged if flags]

    lines = [
        "# Challenge Prediction Review",
        "",
        f"Generated from `{source_name}`. Records: **{len(records)}**.",
        "",
        "This is a human-review aid, not an official score. The input fields shown as `current` may be deliberately wrong.",
        "",
        f"Manual review queue: **{len(review_queue)} / {len(records)}** records.",
        "",
        "## Summary table",
        "",
        "| # | Summary | Work type | Service | Team | Assignee | Urgency | Impact | Priority | Resolution | Review flags |",
        "|---:|---|---|---|---|---|---|---|---|---|---|",
    ]

    for record, flags in flagged:
        prediction = record.get("prediction", {})
        lines.append(
            "| {index} | {summary} | {work_type} | {service} | {team} | {assignee} | {urgency} | {impact} | {priority} | {resolution} | {flags} |".format(
                index=markdown_cell(record.get("ticket_index")),
                summary=markdown_cell(record.get("summary")),
                work_type=markdown_cell(prediction.get("work_type")),
                service=markdown_cell(join_values(prediction.get("affected_services"))),
                team=markdown_cell(join_values(prediction.get("service_teams"))),
                assignee=markdown_cell(prediction.get("assignee")),
                urgency=markdown_cell(prediction.get("urgency")),
                impact=markdown_cell(prediction.get("impact")),
                priority=markdown_cell(prediction.get("priority")),
                resolution=markdown_cell(prediction.get("resolution")),
                flags=markdown_cell(", ".join(flags) if flags else "-"),
            )
        )

    lines.extend(["", "## Detailed review items", ""])
    if not review_queue:
        lines.append("No records require manual review under the configured checks.")
    else:
        for record, flags in review_queue:
            prediction = record.get("prediction", {})
            confidence = prediction.get("confidence", {})
            reasons = prediction.get("reasoning_summary", {})
            similar = prediction.get("similar_historical_tickets", [])
            lines.extend(
                [
                    f"### Ticket {record.get('ticket_index')}: {record.get('summary', '')}",
                    "",
                    f"- Flags: {', '.join(flags)}",
                    f"- Confidence: Work type `{confidence.get('work_type')}`, Service `{confidence.get('service')}`, Owner `{confidence.get('owner')}`",
                    f"- Work type reasoning: {join_values(reasons.get('work_type'))}",
                    f"- Service reasoning: {join_values(reasons.get('service'))}",
                    f"- Ownership reasoning: {join_values(reasons.get('ownership'))}",
                    f"- Resolution reasoning: {join_values(reasons.get('resolution'))}",
                    f"- Resolution comment: {prediction.get('resolution_comment', '')}",
                ]
            )
            if similar:
                lines.append(f"- Top historical evidence: {similar[0].get('summary', '')} (score `{similar[0].get('score')}`)")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a compact Markdown review of challenge predictions.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = load_json(args.input)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("input must be a triage output JSON object with a records array")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(payload, args.input.name), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
