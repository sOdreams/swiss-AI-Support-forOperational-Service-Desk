"""Profile the training set and generate dependency-free visual reports.

The script intentionally uses only the Python standard library. It produces
JSON/Markdown summaries plus SVG charts and a small HTML dashboard under
``outputs/training_analysis``.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .triage_pipeline import (
    DEFAULT_TRAINING,
    GENERIC_RESOLUTION_PHRASES,
    LEVEL_LABELS,
    PRIORITY_MATRIX,
    RESOLUTION_ACTION_WORDS,
    ROOT,
    as_list,
    extract_resolution_comment,
    load_json,
)


DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "training_analysis"


def first(value: Any) -> str:
    values = as_list(value)
    return values[0] if values else "<empty>"


def entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if not total or len(counter) <= 1:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counter.values())


def normalized_entropy(counter: Counter[str]) -> float:
    if len(counter) <= 1:
        return 0.0
    return entropy(counter) / math.log2(len(counter))


def purity(counter: Counter[str]) -> float:
    total = sum(counter.values())
    return counter.most_common(1)[0][1] / total if total else 0.0


def grouping_stats(groups: dict[Any, Counter[str]], min_support: int = 5) -> dict[str, Any]:
    """Measure how deterministic Assignee is within each candidate grouping."""
    total_rows = sum(sum(counter.values()) for counter in groups.values())
    majority_rows = sum(counter.most_common(1)[0][1] for counter in groups.values() if counter)
    supported = [counter for counter in groups.values() if sum(counter.values()) >= min_support]
    pure_supported = [counter for counter in supported if len(counter) == 1]
    largest = max(groups.items(), key=lambda item: sum(item[1].values()), default=("", Counter()))
    return {
        "groups": len(groups),
        "rows": total_rows,
        "weighted_majority_accuracy": round(majority_rows / max(total_rows, 1), 4),
        "groups_with_min_support": len(supported),
        "pure_groups_with_min_support": len(pure_supported),
        "largest_group": str(largest[0]),
        "largest_group_support": sum(largest[1].values()),
        "largest_group_purity": round(purity(largest[1]), 4),
    }


def summary_template(summary: str, service_names: Iterable[str]) -> str:
    text = str(summary or "").casefold()
    text = re.sub(r"\b[^\s:@]+@[^\s:]+\b", "<email>", text)
    text = re.sub(r"\b[a-z]{2,}[\w-]*[_-][\w-]+\b", "<identifier>", text)
    text = re.sub(r"\b\d+\b", "<number>", text)
    for service in sorted(service_names, key=len, reverse=True):
        text = text.replace(service.casefold(), "<service>")
    return re.sub(r"\s+", " ", text).strip()


def matrix_consistency(records: list[dict[str, Any]]) -> dict[str, Any]:
    consistent = 0
    valid = 0
    examples: list[dict[str, Any]] = []
    level_index = {label.casefold(): index for index, label in enumerate(LEVEL_LABELS)}
    for index, record in enumerate(records, start=1):
        try:
            urgency = level_index[str(record.get("Urgency") or "").casefold()]
            impact = level_index[str(record.get("Impact") or "").casefold()]
        except ValueError:
            continue
        except KeyError:
            continue
        valid += 1
        expected = PRIORITY_MATRIX[urgency][impact]
        if str(expected).casefold() == str(record.get("Priority") or "").casefold():
            consistent += 1
        elif len(examples) < 10:
            examples.append(
                {
                    "row": index,
                    "priority": record.get("Priority"),
                    "urgency": record.get("Urgency"),
                    "impact": record.get("Impact"),
                    "expected": expected,
                }
            )
    return {
        "valid_rows": valid,
        "consistent_rows": consistent,
        "consistency": round(consistent / max(valid, 1), 4),
        "examples": examples,
    }


def build_analysis(records: list[dict[str, Any]]) -> dict[str, Any]:
    services = sorted({first(record.get("Affected Business or IT Services")) for record in records})
    service_counts: Counter[str] = Counter()
    team_counts: Counter[str] = Counter()
    assignee_counts: Counter[str] = Counter()
    reporter_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    work_type_counts: Counter[str] = Counter()
    resolution_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    service_team_counts: dict[str, Counter[str]] = defaultdict(Counter)
    service_assignee_counts: dict[str, Counter[str]] = defaultdict(Counter)
    service_work_counts: dict[str, Counter[str]] = defaultdict(Counter)
    service_work_assignee_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    template_assignee_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    entity_assignee_counts: dict[str, Counter[str]] = defaultdict(Counter)
    reporter_assignee_counts: dict[str, Counter[str]] = defaultdict(Counter)

    comment_tickets = 0
    comment_count = 0
    resolution_note_count = 0
    concrete_resolution_count = 0
    resolution_assignee_matches = 0

    for record in records:
        service = first(record.get("Affected Business or IT Services"))
        team = first(record.get("Service Team(s)"))
        assignee = str(record.get("Assignee") or "").strip() or "<empty>"
        reporter = str(record.get("Reporter") or "").strip() or "<empty>"
        entity = first(record.get("Business Entity"))
        work_type = str(record.get("Work type") or "<empty>")
        resolution = str(record.get("Resolution") or "<empty>")
        status = str(record.get("Status") or "<empty>")

        service_counts[service] += 1
        team_counts[team] += 1
        assignee_counts[assignee] += 1
        reporter_counts[reporter] += 1
        entity_counts[entity] += 1
        work_type_counts[work_type] += 1
        resolution_counts[resolution] += 1
        status_counts[status] += 1
        service_team_counts[service][team] += 1
        service_assignee_counts[service][assignee] += 1
        service_work_counts[service][work_type] += 1
        service_work_assignee_counts[(service, work_type)][assignee] += 1
        entity_assignee_counts[entity][assignee] += 1
        reporter_assignee_counts[reporter][assignee] += 1

        template = summary_template(record.get("Summary", ""), services)
        template_assignee_counts[(service, template)][assignee] += 1

        comments = as_list(record.get("All Comments"))
        if comments:
            comment_tickets += 1
            comment_count += len(comments)
        resolution_note = extract_resolution_comment(record)
        if resolution_note:
            resolution_note_count += 1
            author, body = resolution_note
            body_lower = body.casefold()
            if any(word in body_lower for word in RESOLUTION_ACTION_WORDS) and not any(
                phrase in body_lower for phrase in GENERIC_RESOLUTION_PHRASES
            ):
                concrete_resolution_count += 1
            if author.strip() == str(record.get("Assignee") or "").strip():
                resolution_assignee_matches += 1

    service_team_summary = {}
    for service, counter in service_team_counts.items():
        top = counter.most_common(1)[0] if counter else ("", 0)
        service_team_summary[service] = {
            "tickets": sum(counter.values()),
            "teams": len(counter),
            "top_team": top[0],
            "top_team_share": round(purity(counter), 4),
            "distribution": dict(counter.most_common()),
        }

    service_assignee_summary = {}
    for service, counter in service_assignee_counts.items():
        service_assignee_summary[service] = {
            "tickets": sum(counter.values()),
            "unique_assignees": len(counter),
            "top_assignee": counter.most_common(1)[0][0] if counter else "",
            "top_assignee_share": round(purity(counter), 4),
            "normalized_entropy": round(normalized_entropy(counter), 4),
            "top_candidates": [
                {"assignee": assignee, "count": count}
                for assignee, count in counter.most_common(5)
            ],
        }

    template_summary = []
    for (service, template), counter in template_assignee_counts.items():
        total = sum(counter.values())
        template_summary.append(
            {
                "service": service,
                "template": template,
                "tickets": total,
                "unique_assignees": len(counter),
                "top_assignee": counter.most_common(1)[0][0],
                "top_assignee_share": round(purity(counter), 4),
            }
        )
    template_summary.sort(key=lambda item: (-item["tickets"], item["service"], item["template"]))

    field_missingness = {}
    for field in (
        "Work type",
        "Affected Business or IT Services",
        "Service Team(s)",
        "Assignee",
        "Request type",
        "Business Entity",
        "Resolution",
        "All Comments",
    ):
        missing = sum(not as_list(record.get(field)) for record in records)
        field_missingness[field] = {
            "missing": missing,
            "missing_rate": round(missing / max(len(records), 1), 4),
        }

    return {
        "dataset": {
            "records": len(records),
            "unique_services": len(service_counts),
            "unique_teams": len(team_counts),
            "unique_assignees": len([key for key in assignee_counts if key != "<empty>"]),
            "unique_reporters": len([key for key in reporter_counts if key != "<empty>"]),
            "unique_business_entities": len([key for key in entity_counts if key != "<empty>"]),
        },
        "field_missingness": field_missingness,
        "distributions": {
            "services": dict(service_counts.most_common()),
            "teams": dict(team_counts.most_common()),
            "assignees": dict(assignee_counts.most_common()),
            "work_types": dict(work_type_counts.most_common()),
            "resolutions": dict(resolution_counts.most_common()),
            "statuses": dict(status_counts.most_common()),
            "business_entities": dict(entity_counts.most_common()),
        },
        "service_team": service_team_summary,
        "service_work_type": {
            service: {
                "tickets": sum(counter.values()),
                "distribution": dict(counter.most_common()),
            }
            for service, counter in service_work_counts.items()
        },
        "service_assignee": service_assignee_summary,
        "assignee_pattern_checks": {
            "service": grouping_stats(dict(service_assignee_counts)),
            "service_and_work_type": grouping_stats(dict(service_work_assignee_counts)),
            "business_entity": grouping_stats(dict(entity_assignee_counts)),
            "reporter": grouping_stats(dict(reporter_assignee_counts)),
            "service_and_summary_template": grouping_stats(dict(template_assignee_counts)),
        },
        "summary_templates": template_summary[:100],
        "resolution_quality": {
            "tickets_with_comments": comment_tickets,
            "total_comments": comment_count,
            "tickets_with_resolution_note": resolution_note_count,
            "concrete_resolution_notes": concrete_resolution_count,
            "concrete_resolution_rate_among_notes": round(
                concrete_resolution_count / max(resolution_note_count, 1), 4
            ),
            "resolution_author_equals_assignee": resolution_assignee_matches,
            "resolution_author_assignee_overlap_rate": round(
                resolution_assignee_matches / max(resolution_note_count, 1), 4
            ),
        },
        "priority_matrix": matrix_consistency(records),
    }


def svg_bar_chart(title: str, rows: list[tuple[str, float]], suffix: str = "", color: str = "#2f6fed") -> str:
    width = 1100
    left = 310
    row_height = 28
    top = 70
    height = top + max(len(rows), 1) * row_height + 35
    max_value = max((value for _, value in rows), default=1.0)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,sans-serif;fill:#1f2937}.label{font-size:13px}.title{font-size:18px;font-weight:700}.value{font-size:12px}</style>',
        f'<text x="20" y="28" class="title">{html.escape(title)}</text>',
    ]
    for index, (label, value) in enumerate(rows):
        y = top + index * row_height
        bar_width = max(1, int(650 * value / max_value))
        parts.append(f'<text x="20" y="{y + 16}" class="label">{html.escape(label)}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{bar_width}" height="18" rx="3" fill="{color}"/>')
        parts.append(f'<text x="{left + bar_width + 8}" y="{y + 14}" class="value">{value:,.0f}{html.escape(suffix)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def svg_stacked_work_chart(title: str, service_work: dict[str, Counter[str]]) -> str:
    width = 1150
    left = 300
    top = 70
    row_height = 30
    services = sorted(service_work, key=lambda service: -sum(service_work[service].values()))
    height = top + max(len(services), 1) * row_height + 45
    max_value = max((sum(service_work[service].values()) for service in services), default=1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,sans-serif;fill:#1f2937}.label{font-size:13px}.title{font-size:18px;font-weight:700}.legend{font-size:12px}</style>',
        f'<text x="20" y="28" class="title">{html.escape(title)}</text>',
        '<rect x="850" y="14" width="12" height="12" fill="#2f6fed"/><text x="868" y="25" class="legend">Incident</text>',
        '<rect x="950" y="14" width="12" height="12" fill="#f59e0b"/><text x="968" y="25" class="legend">Service Request</text>',
    ]
    for index, service in enumerate(services):
        y = top + index * row_height
        counter = service_work[service]
        incident = counter.get("Incident", 0)
        request = counter.get("Service Request", 0)
        incident_width = int(650 * incident / max_value)
        request_width = int(650 * request / max_value)
        parts.append(f'<text x="20" y="{y + 16}" class="label">{html.escape(service)}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{incident_width}" height="18" fill="#2f6fed"/>')
        parts.append(f'<rect x="{left + incident_width}" y="{y}" width="{request_width}" height="18" fill="#f59e0b"/>')
        parts.append(f'<text x="{left + incident_width + request_width + 8}" y="{y + 14}" class="legend">{incident + request:,}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def render_markdown(analysis: dict[str, Any], chart_names: list[str]) -> str:
    dataset = analysis["dataset"]
    resolution = analysis["resolution_quality"]
    matrix = analysis["priority_matrix"]
    lines = [
        "# Training Pattern Analysis",
        "",
        f"Records analyzed: **{dataset['records']:,}**",
        "",
        "## Main findings",
        "",
        f"- Services: **{dataset['unique_services']}**; teams: **{dataset['unique_teams']}**; unique Assignees: **{dataset['unique_assignees']}**.",
        f"- Resolution author equals Assignee in only **{resolution['resolution_author_assignee_overlap_rate']:.2%}** of resolution notes.",
        f"- Training Priority/Urgency/Impact matrix consistency: **{matrix['consistency']:.2%}**; these labels should not be learned as severity truth.",
        f"- Concrete resolution notes: **{resolution['concrete_resolution_rate_among_notes']:.2%}** of notes containing a resolution marker.",
        "",
        "## Assignee pattern checks",
        "",
        "The table reports the weighted accuracy of assigning each group its majority Assignee. A high value would support a deterministic routing rule; values near the global 3.33% Assignee prior do not.",
        "",
        "| Candidate grouping | Groups | Weighted majority accuracy | Pure groups (support ≥ 5) | Largest group purity |",
        "|---|---:|---:|---:|---:|",
    ]
    grouping_labels = {
        "service": "Service",
        "service_and_work_type": "Service + Work type",
        "business_entity": "Business Entity",
        "reporter": "Reporter",
        "service_and_summary_template": "Service + Summary template",
    }
    for key, label in grouping_labels.items():
        item = analysis["assignee_pattern_checks"][key]
        lines.append(
            f"| {label} | {item['groups']:,} | {item['weighted_majority_accuracy']:.1%} | "
            f"{item['pure_groups_with_min_support']:,} | {item['largest_group_purity']:.1%} |"
        )

    lines.extend([
        "",
        "## Missingness and label quality",
        "",
        "| Field | Missing rows | Missing rate |",
        "|---|---:|---:|",
    ])
    for field, item in analysis["field_missingness"].items():
        lines.append(f"| {field} | {item['missing']:,} | {item['missing_rate']:.1%} |")

    lines.extend([
        "",
        "## Service → Team",
        "",
        "| Service | Tickets | Unique teams | Dominant team | Share |",
        "|---|---:|---:|---|---:|",
    ])
    for service, item in sorted(analysis["service_team"].items(), key=lambda pair: -pair[1]["tickets"]):
        lines.append(f"| {service} | {item['tickets']:,} | {item['teams']} | {item['top_team']} | {item['top_team_share']:.1%} |")

    lines.extend(["", "## Service → Assignee concentration", "", "| Service | Tickets | Unique Assignees | Top Assignee share | Normalized entropy |", "|---|---:|---:|---:|---:|"])
    for service, item in sorted(analysis["service_assignee"].items(), key=lambda pair: -pair[1]["tickets"]):
        lines.append(f"| {service} | {item['tickets']:,} | {item['unique_assignees']} | {item['top_assignee_share']:.1%} | {item['normalized_entropy']:.3f} |")

    lines.extend(["", "## Largest summary templates", "", "| Service | Template | Tickets | Unique Assignees | Top share |", "|---|---|---:|---:|---:|"])
    for item in analysis["summary_templates"][:20]:
        lines.append(f"| {item['service']} | `{item['template']}` | {item['tickets']:,} | {item['unique_assignees']} | {item['top_assignee_share']:.1%} |")

    lines.extend(["", "## Resolution and data quality", "", f"- Tickets with comments: **{resolution['tickets_with_comments']:,}**", f"- Total comments: **{resolution['total_comments']:,}**", f"- Tickets with a resolution note: **{resolution['tickets_with_resolution_note']:,}**", f"- Resolution author/Assignee overlap: **{resolution['resolution_author_equals_assignee']:,}**", "", "## Charts", ""])
    for chart in chart_names:
        lines.append(f"- [{chart}]({chart})")
    return "\n".join(lines) + "\n"


def render_dashboard(analysis: dict[str, Any], chart_names: list[str]) -> str:
    dataset = analysis["dataset"]
    rows = [
        ("Records", f"{dataset['records']:,}"),
        ("Services", str(dataset["unique_services"])),
        ("Teams", str(dataset["unique_teams"])),
        ("Unique Assignees", str(dataset["unique_assignees"])),
        ("Resolution author = Assignee", f"{analysis['resolution_quality']['resolution_author_assignee_overlap_rate']:.2%}"),
        ("Priority matrix consistency", f"{analysis['priority_matrix']['consistency']:.2%}"),
    ]
    cards = "".join(f'<div class="card"><b>{html.escape(label)}</b><br/><span>{html.escape(value)}</span></div>' for label, value in rows)
    images = "".join(f'<h2>{html.escape(Path(chart).stem.replace("_", " ").title())}</h2><img src="{html.escape(chart)}"/>' for chart in chart_names)
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><title>SwissLife Training Pattern Dashboard</title>
<style>body{{font-family:Arial,sans-serif;max-width:1200px;margin:30px auto;color:#1f2937}}.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{background:#eef4ff;border-radius:8px;padding:14px 18px;min-width:150px}}.card span{{font-size:24px}}img{{max-width:100%;border:1px solid #e5e7eb}}</style>
</head><body><h1>SwissLife Training Pattern Dashboard</h1><div class="cards">{cards}</div>{images}</body></html>'''


def analyze(training_path: Path, output_dir: Path) -> dict[str, Any]:
    records = load_json(training_path)
    if not isinstance(records, list):
        raise ValueError("training JSON must be an array")
    analysis = build_analysis(records)
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_data = {
        "service_volume.svg": svg_bar_chart(
            "Tickets by service",
            [(key, value) for key, value in sorted(analysis["distributions"]["services"].items(), key=lambda pair: -pair[1])],
        ),
        "assignee_volume.svg": svg_bar_chart(
            "Top Assignee frequencies",
            [(key, value) for key, value in list(analysis["distributions"]["assignees"].items())[:15] if key != "<empty>"],
            color="#7c3aed",
        ),
        "service_team_purity.svg": svg_bar_chart(
            "Dominant Service → Team share",
            [(service, item["top_team_share"] * 100) for service, item in sorted(analysis["service_team"].items(), key=lambda pair: -pair[1]["top_team_share"])],
            suffix="%",
            color="#059669",
        ),
        "service_assignee_concentration.svg": svg_bar_chart(
            "Top Assignee share within each service",
            [(service, item["top_assignee_share"] * 100) for service, item in sorted(analysis["service_assignee"].items(), key=lambda pair: -pair[1]["top_assignee_share"])],
            suffix="%",
            color="#dc2626",
        ),
    }
    # Build the stacked chart from raw records to preserve service-level mix.
    service_work: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        service_work[first(record.get("Affected Business or IT Services"))][str(record.get("Work type") or "<empty>")] += 1
    chart_data["service_work_type.svg"] = svg_stacked_work_chart("Work type mix by service", service_work)

    for filename, content in chart_data.items():
        (output_dir / filename).write_text(content, encoding="utf-8")

    chart_names = list(chart_data)
    (output_dir / "training_pattern_report.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "training_pattern_report.md").write_text(render_markdown(analysis, chart_names), encoding="utf-8")
    (output_dir / "training_pattern_dashboard.html").write_text(render_dashboard(analysis, chart_names), encoding="utf-8")
    return analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze patterns in the historical training set.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    analysis = analyze(args.training, args.output_dir)
    print(f"Analyzed {analysis['dataset']['records']} records.")
    print(f"Services: {analysis['dataset']['unique_services']}; teams: {analysis['dataset']['unique_teams']}; assignees: {analysis['dataset']['unique_assignees']}")
    print(f"Priority/Urgency/Impact matrix consistency: {analysis['priority_matrix']['consistency']:.3f}")
    print(f"Resolution author/Assignee overlap: {analysis['resolution_quality']['resolution_author_assignee_overlap_rate']:.3f}")
    print(f"Wrote reports to {args.output_dir}")


if __name__ == "__main__":
    main()
