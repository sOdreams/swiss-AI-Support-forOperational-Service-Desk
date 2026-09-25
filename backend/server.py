"""Small dependency-free HTTP API for the SwissLife triage workbench.

The service deliberately keeps the existing triage engine as the source of
truth.  It exposes a thin JSON API for the React workbench and stores analyst
feedback as append-only JSON files under ``runtime``.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = PROJECT_ROOT / "engine"
DATA_ROOT = PROJECT_ROOT / "data"
RUNTIME_ROOT = PROJECT_ROOT / "runtime"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
sys.path.insert(0, str(ENGINE_ROOT))

from scripts.triage_pipeline import TriageEngine, as_list, load_json  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def first(value: Any, default: str | None = None) -> str | None:
    values = as_list(value)
    return values[0] if values else default


def clean_user(value: Any) -> dict[str, str] | None:
    if value in (None, "", []):
        return None
    if isinstance(value, dict):
        display = value.get("display_name") or value.get("displayName") or value.get("name") or value.get("id")
        user_id = value.get("id") or value.get("account_id") or display
    else:
        display = str(value)
        user_id = display
    if not display:
        return None
    return {"id": str(user_id or display), "display_name": str(display)}


def clean_comments(value: Any, ticket_key: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    comments: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            body = str(item.get("body") or item.get("comment") or item.get("text") or "")
            author = clean_user(item.get("author") or item.get("user")) or {"id": "unknown", "display_name": "Unknown author"}
            created = str(item.get("created_at") or item.get("created") or item.get("date") or "")
            visibility = item.get("visibility") if item.get("visibility") in {"public", "internal"} else None
        else:
            raw = str(item)
            split_at = raw.find(":")
            author_name = raw[:split_at].strip() if split_at > 0 else "Unknown author"
            body = raw[split_at + 1 :].strip() if split_at > 0 else raw
            author = {"id": author_name, "display_name": author_name}
            created = ""
            visibility = None
        lower = body.casefold()
        role = "result" if any(word in lower for word in ("failed", "not resolved", "still", "continues")) else "action" if any(word in lower for word in ("updated", "verified", "checked", "restarted", "granted", "removed")) else "comment"
        comments.append({
            "id": f"{ticket_key}-comment-{index}",
            "author": author,
            "body": body,
            "created_at": created,
            "visibility": visibility,
            "semantic_role": role,
        })
    return comments


def record_to_ticket(record: dict[str, Any], index: int) -> dict[str, Any]:
    issue_key = str(record.get("Issue Key") or record.get("issue_key") or f"TICKET-{index + 1}")
    issue_id = str(record.get("Issue ID") or record.get("issue_id") or issue_key)
    services = as_list(record.get("Affected Business or IT Services") or record.get("affected_business_or_it_services"))
    teams = as_list(record.get("Service Team(s)") or record.get("service_teams"))
    business_entity = first(record.get("Business Entity") or record.get("business_entity"))
    critical = record.get("Business Critical for Entity")
    if isinstance(critical, list):
        critical = critical[0] if critical else None
    if isinstance(critical, str):
        critical = critical.casefold() in {"true", "yes", "1"}
    elif not isinstance(critical, bool):
        critical = None
    linked = record.get("Linked issues") or record.get("linked_issues") or []
    linked_issues: list[dict[str, Any]] = []
    if isinstance(linked, list):
        for item in linked:
            if isinstance(item, dict):
                linked_issues.append({
                    "relation": str(item.get("relation") or item.get("type") or "related to"),
                    "issue_key": str(item.get("issue_key") or item.get("key") or item.get("id") or "LINK"),
                    "summary": str(item.get("summary") or item.get("title") or "Linked issue"),
                    "status": item.get("status"),
                })
            else:
                linked_issues.append({"relation": "related to", "issue_key": str(item), "summary": "Linked issue", "status": None})
    return {
        "issue_id": issue_id,
        "issue_key": issue_key,
        "work_type": record.get("Work type") or record.get("work_type"),
        "request_type": record.get("Request type") or record.get("request_type"),
        "summary": str(record.get("Summary") or record.get("summary") or "Untitled ticket"),
        "description": record.get("Description") or record.get("description"),
        "affected_business_or_it_services": services,
        "business_entity": business_entity,
        "business_critical_for_entity": critical,
        "service_teams": teams,
        "reporter": clean_user(record.get("Reporter") or record.get("reporter")),
        "assignee": clean_user(record.get("Assignee") or record.get("assignee")),
        "priority": record.get("Priority") or record.get("priority"),
        "urgency": record.get("Urgency") or record.get("urgency"),
        "impact": record.get("Impact") or record.get("impact"),
        "severity": record.get("Severity") or record.get("severity"),
        "created_date": str(record.get("Created date") or record.get("created_date") or ""),
        "status": str(record.get("Status") or record.get("status") or "Not recorded"),
        "linked_issues": linked_issues,
        "resolution": record.get("Resolution") or record.get("resolution"),
        "due_date": record.get("Due date") or record.get("due_date"),
        "all_comments": clean_comments(record.get("All Comments") or record.get("all_comments"), issue_key),
        "raw": record,
    }


def frontend_to_raw(record: dict[str, Any], index: int) -> dict[str, Any]:
    raw = record.get("raw")
    if isinstance(raw, dict) and raw:
        normalized = dict(raw)
        normalized.setdefault("Issue ID", record.get("issue_id") or f"TICKET-{index + 1}")
        normalized.setdefault("Issue Key", record.get("issue_key") or f"TICKET-{index + 1}")
        return normalized
    return {
        "Issue ID": record.get("issue_id") or f"TICKET-{index + 1}",
        "Issue Key": record.get("issue_key") or f"TICKET-{index + 1}",
        "Work type": record.get("work_type"),
        "Request type": record.get("request_type"),
        "Summary": record.get("summary"),
        "Description": record.get("description"),
        "Affected Business or IT Services": record.get("affected_business_or_it_services", []),
        "Business Entity": record.get("business_entity"),
        "Business Critical for Entity": record.get("business_critical_for_entity"),
        "Service Team(s)": record.get("service_teams", []),
        "Reporter": (record.get("reporter") or {}).get("display_name") if isinstance(record.get("reporter"), dict) else record.get("reporter"),
        "Assignee": (record.get("assignee") or {}).get("display_name") if isinstance(record.get("assignee"), dict) else record.get("assignee"),
        "Priority": record.get("priority"),
        "Urgency": record.get("urgency"),
        "Impact": record.get("impact"),
        "Severity": record.get("severity"),
        "Created date": record.get("created_date"),
        "Status": record.get("status"),
        "Linked issues": record.get("linked_issues", []),
        "Resolution": record.get("resolution"),
        "Due date": record.get("due_date"),
        "All Comments": [comment.get("body", "") if isinstance(comment, dict) else str(comment) for comment in record.get("all_comments", [])],
    }


class AppState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.training_path = DATA_ROOT / "training.json"
        self.challenge_path = DATA_ROOT / "challenge.json"
        training = load_json(self.training_path)
        challenge_payload = load_json(self.challenge_path)
        challenge_records = challenge_payload.get("records", []) if isinstance(challenge_payload, dict) else challenge_payload
        self.training_records: list[dict[str, Any]] = training if isinstance(training, list) else []
        self.records: list[dict[str, Any]] = []
        for index, record in enumerate(challenge_records if isinstance(challenge_records, list) else []):
            if not isinstance(record, dict):
                continue
            initial = dict(record)
            initial.setdefault("Issue ID", f"TICKET-{index + 1}")
            initial.setdefault("Issue Key", f"TICKET-{index + 1}")
            self.records.append(initial)
        self.engine = TriageEngine(self.training_records)
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

    def tickets(self) -> list[dict[str, Any]]:
        with self.lock:
            return [record_to_ticket(record, index) for index, record in enumerate(self.records)]

    def find(self, ticket_id: str) -> tuple[int, dict[str, Any]] | None:
        wanted = unquote(ticket_id)
        with self.lock:
            for index, record in enumerate(self.records):
                ticket = record_to_ticket(record, index)
                if ticket["issue_id"] == wanted or ticket["issue_key"] == wanted:
                    return index, record
        return None

    def replace_records(self, records: list[dict[str, Any]]) -> None:
        with self.lock:
            self.records = [frontend_to_raw(record, index) for index, record in enumerate(records)]

    def append_runtime(self, name: str, payload: dict[str, Any]) -> None:
        path = RUNTIME_ROOT / name
        with self.lock:
            existing: list[Any] = []
            if path.exists():
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(loaded, list):
                        existing = loaded
                except (OSError, json.JSONDecodeError):
                    existing = []
            existing.append(payload)
            path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def read_runtime(self, name: str) -> list[Any]:
        path = RUNTIME_ROOT / name
        if not path.exists():
            return []
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, list) else []
        except (OSError, json.JSONDecodeError):
            return []


STATE = AppState()


def make_proposal(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = STATE.engine.triage(ticket, top_k=8)
    reasons = prediction.get("reasoning_summary", {})
    confidence_map = prediction.get("confidence", {})
    confidence_values = [float(value) for value in confidence_map.values() if isinstance(value, (int, float))]
    confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.5
    team = first(prediction.get("service_teams"), "Unassigned")
    service = first(prediction.get("affected_services"), "Unknown service")
    source_items: list[dict[str, Any]] = []
    for similar in prediction.get("similar_historical_tickets", [])[:5]:
        comment = similar.get("resolution_comment") or "Historical routing and resolution pattern."
        source_items.append({
            "id": f"HIST-{int(similar.get('training_index', 0)) + 1:05d}",
            "title": similar.get("summary") or "Historical ticket",
            "document_type": "historical_ticket",
            "section": ", ".join(similar.get("service") or []),
            "relevance_score": min(1.0, max(0.0, float(similar.get("score", 0.0)) / 20.0)),
            "excerpt": comment,
        })
    pending: list[str] = []
    if not str(ticket.get("Description") or "").strip():
        pending.append("Description is missing; confirm the affected workflow before applying the recommendation.")
    if float(confidence_map.get("owner", 0.0)) < 0.65:
        pending.append("Ownership evidence is limited; verify the suggested team and assignee.")
    if prediction.get("resolution") in {"clarification", "cannot reproduce"}:
        pending.append("Historical evidence does not support a fully verified resolution yet.")
    priority_evidence = reasons.get("priority_evidence") or []
    priority_reason = (
        f"{prediction['urgency']} urgency × {prediction['impact']} impact → {prediction['priority']}. "
        + " ".join(priority_evidence[:3])
    )
    resolution_text = prediction.get("resolution_comment") or "Clarification is required before a verified resolution can be drafted."
    source_ids = [item["id"] for item in source_items[:2]]
    resolution_needs_clarification = prediction.get("resolution") in {"clarification", "cannot reproduce"} or bool(pending)
    if resolution_needs_clarification:
        first_option = {
            "id": "option_1",
            "title": "Clarify before resolving",
            "description": resolution_text,
            "kind": "clarification",
            "prerequisites": pending[:3] or ["Confirm the missing operational details before applying a change."],
            "expected_outcome": "The owning team has enough verified information to choose a safe next step.",
            "source_ids": source_ids,
        }
        second_option = {
            "id": "option_2",
            "title": "Escalate with an evidence gap",
            "description": f"Route the case to {team} for specialist review while clearly recording the missing information.",
            "kind": "escalation",
            "prerequisites": ["Record which information is still missing before handoff."],
            "expected_outcome": "The receiving team can continue triage without treating an unverified fix as completed.",
            "source_ids": [],
        }
    else:
        first_option = {
            "id": "option_1",
            "title": "Use evidence-backed resolution",
            "description": resolution_text,
            "kind": "recommended",
            "prerequisites": [],
            "expected_outcome": "The owning team verifies the historical resolution pattern against the current ticket.",
            "source_ids": source_ids,
        }
        second_option = {
            "id": "option_2",
            "title": "Escalate for specialist review",
            "description": f"Confirm the route with {team} and ask the specialist owner to validate the next operational step.",
            "kind": "escalation",
            "prerequisites": ["Confirm the suggested service team before handoff."],
            "expected_outcome": "The specialist owner confirms the route and next check before any change is applied.",
            "source_ids": [],
        }
    resolution_options = [first_option, second_option]
    case_summary = f"{prediction['work_type']} for {service}, routed to {team}. {prediction['impact']} impact with {prediction['urgency']} urgency; the matrix yields {prediction['priority']} priority."
    return {
        "ticket_id": str(ticket.get("Issue ID") or ticket.get("Issue Key") or ""),
        "issue_key": str(ticket.get("Issue Key") or ticket.get("Issue ID") or ""),
        "case_summary": case_summary,
        "proposed_work_type": prediction.get("work_type"),
        "proposed_request_type": ticket.get("Request type"),
        "proposed_priority": prediction.get("priority"),
        "priority_reason": priority_reason,
        "proposed_service_team": team,
        "service_team_reason": " ".join(reasons.get("ownership") or []) or "Service ownership inferred from historical routing patterns.",
        "proposed_assignee": prediction.get("assignee"),
        "assignee_reason": " ".join(reasons.get("ownership") or []) or "Assignee selected from service and historical ownership evidence.",
        "proposed_urgency": prediction.get("urgency"),
        "urgency_reason": " ".join(priority_evidence[:2]) or "Urgency inferred from operational timing and failure language.",
        "proposed_impact": prediction.get("impact"),
        "impact_reason": prediction.get("impact_category") or "Impact inferred from affected scope and service criticality.",
        "proposed_severity": ticket.get("Severity"),
        "severity_reason": "Severity is retained for analyst review because the source field is not consistently populated.",
        "proposed_resolution": prediction.get("resolution"),
        "resolution_reason": " ".join(reasons.get("resolution") or []) or "Resolution status and note are grounded in the closest historical cases.",
        "affected_services_suggestion": prediction.get("affected_services", []),
        "pending_questions": pending,
        "resolution_options": resolution_options,
        "sources": source_items,
        "draft_response": resolution_text,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "analyzed_at": now_iso(),
        "prediction": prediction,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "SwissLifeServiceDesk/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json({"error": message, "status": status}, status)

    def read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        parsed = json.loads(raw.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("JSON body must be an object")
        return parsed

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            self.send_json({"status": "ok", "training_records": len(STATE.training_records), "tickets": len(STATE.records)})
            return
        if path == "/stats":
            self.send_json({"tickets": len(STATE.records), "processed": len(STATE.read_runtime("processed.json")), "reviews": len(STATE.read_runtime("reviews.json")), "training_records": len(STATE.training_records)})
            return
        if path == "/tickets":
            self.send_json(STATE.tickets())
            return
        if path == "/processed":
            self.send_json(STATE.read_runtime("processed.json"))
            return
        if path.startswith("/tickets/"):
            ticket_id = path.split("/", 2)[2]
            found = STATE.find(ticket_id)
            if not found:
                self.send_error_json(HTTPStatus.NOT_FOUND, "Ticket not found")
                return
            index, record = found
            self.send_json(record_to_ticket(record, index))
            return
        if path == "/" or path.startswith("/assets/") or path == "/favicon.svg":
            self.serve_static(path)
            return
        self.send_error_json(HTTPStatus.NOT_FOUND, "Route not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            body = self.read_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
            return
        if path == "/tickets/import":
            records = body.get("tickets")
            if not isinstance(records, list) or not records:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "tickets must be a non-empty array")
                return
            STATE.replace_records([item for item in records if isinstance(item, dict)])
            self.send_json({"tickets": STATE.tickets(), "count": len(STATE.records)})
            return
        if path == "/tickets/process":
            body["saved_at"] = now_iso()
            STATE.append_runtime("processed.json", body)
            self.send_json({"status": "saved", "saved_at": body["saved_at"]}, HTTPStatus.CREATED)
            return
        if path == "/feedback":
            body["saved_at"] = now_iso()
            STATE.append_runtime("reviews.json", body)
            self.send_json({"status": "saved", "saved_at": body["saved_at"]}, HTTPStatus.CREATED)
            return
        if path == "/feedback/learning":
            body["saved_at"] = now_iso()
            STATE.append_runtime("learning_feedback.json", body)
            self.send_json({"status": "saved", "saved_at": body["saved_at"]}, HTTPStatus.CREATED)
            return
        if path.startswith("/tickets/") and path.endswith("/assist"):
            ticket_id = path.split("/", 3)[2]
            found = STATE.find(ticket_id)
            if not found:
                self.send_error_json(HTTPStatus.NOT_FOUND, "Ticket not found")
                return
            _, record = found
            self.send_json(make_proposal(record))
            return
        self.send_error_json(HTTPStatus.NOT_FOUND, "Route not found")

    def serve_static(self, path: str) -> None:
        if path == "/":
            relative = Path("dist/index.html") if (FRONTEND_ROOT / "dist/index.html").exists() else Path("index.html")
        elif path == "/favicon.svg":
            relative = Path("public/favicon.svg")
        elif path.startswith("/assets/") and (FRONTEND_ROOT / "dist" / path.lstrip("/")).is_file():
            relative = Path("dist") / Path(path.lstrip("/"))
        else:
            relative = Path(path.lstrip("/"))
        target = (FRONTEND_ROOT / relative).resolve()
        try:
            target.relative_to(FRONTEND_ROOT.resolve())
        except ValueError:
            self.send_error_json(HTTPStatus.NOT_FOUND, "File not found")
            return
        if not target.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "File not found")
            return
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SwissLife Service Desk API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"SwissLife Service Desk API listening on http://{args.host}:{args.port}")
    print(f"Loaded {len(STATE.training_records):,} historical tickets and {len(STATE.records):,} active tickets")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SwissLife Service Desk API")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
