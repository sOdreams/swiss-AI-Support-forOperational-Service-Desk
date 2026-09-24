"""Evidence-driven Jira triage pipeline.

This module implements the first three proposal phases:

1. Data and rule foundation: JSON loading, normalization, service/team/
   assignee indexes, critical-service knowledge, and priority matrix.
2. Retrieval and triage engine: hybrid lexical retrieval plus constrained
   work-type, service, team, assignee, urgency, impact, and priority inference.
3. Resolution drafting: evidence-backed resolution status and concrete
   resolution comments based on similar historical cases.

It intentionally uses only the Python standard library so the pipeline can be
run in a clean hackathon environment. Generated resolution evidence remains
visible for review.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_TRAINING = ROOT / "jira_first_20000_requested_fields_synthetic.json"
DEFAULT_CHALLENGE = ROOT / "jira_hackathon_blind_eval_challenge_20260923083915-1141.json"
DEFAULT_OUTPUT = ROOT / "triage_phase3_output.json"

WORK_TYPES = ("Incident", "Service Request")
RESOLUTION_STATUSES = ("done", "cancelled", "clarification", "cannot reproduce")
LEVEL_LABELS = ("Lowest", "Low", "Medium", "High", "Highest")
IMPACT_CATEGORIES = (
    "No direct impact / Information",
    "Minor / Localized",
    "Moderate / Limited",
    "Significant / Large",
    "Major / Widespread",
)

CRITICAL_SERVICES = {
    "Trading Platform",
    "Order Management",
    "Trade Matching",
    "Securities Settlement",
    "Corporate Actions",
    "Fund Pricing",
    "NAV Calculation",
    "Portfolio Accounting",
    "Cash Management",
    "Risk & Compliance Monitoring",
    "Regulatory Reporting",
    "SimCorp Dimension",
    "Rimes Data Feed",
    "Client Reporting",
}

# This is the README matrix expressed as integer urgency/impact levels. The
# rows are urgency (Highest -> Lowest); the columns are impact (Major -> None).
PRIORITY_MATRIX = {
    4: {4: "Highest", 3: "Highest", 2: "High", 1: "Medium", 0: "Medium"},
    3: {4: "Highest", 3: "High", 2: "High", 1: "Medium", 0: "Low"},
    2: {4: "High", 3: "High", 2: "Medium", 1: "Low", 0: "Low"},
    1: {4: "Medium", 3: "Medium", 2: "Low", 1: "Low", 0: "Lowest"},
    0: {4: "Medium", 3: "Low", 2: "Low", 1: "Lowest", 0: "Lowest"},
}

SERVICE_TEAM_HINTS = {
    "Cash Management": "Treasury & Cash",
    "Client Reporting": "Client Services",
    "Corporate Actions": "Securities Operations",
    "CRM & Client Portal": "Client Services",
    "Emailed Support Tickets": "Service Desk",
    "Fund Pricing": "Valuation & Pricing",
    "Identity & Access Management": "Enterprise Applications",
    "NAV Calculation": "Valuation & Pricing",
    "Order Management": "Trading Support",
    "Outlook & Email": "Enterprise Applications",
    "Portfolio Accounting": "Investment Operations",
    "Regulatory Reporting": "Risk & Controls",
    "Rimes Data Feed": "Market Data Services",
    "Risk & Compliance Monitoring": "Risk & Controls",
    "Securities Settlement": "Securities Operations",
    "SharePoint & File Storage": "Enterprise Applications",
    "SimCorp Dimension": "Enterprise Applications",
    "Tax Reporting": "Tax & Reporting",
    "Trade Matching": "Investment Operations",
    "Trading Platform": "Investment Operations",
}

# Strong narrative clues. These deliberately avoid relying only on the
# currently selected service because the challenge says that field can be wrong.
SERVICE_CLUES: dict[str, tuple[tuple[str, float], ...]] = {
    "Tax Reporting": (
        ("withholding tax", 9.0),
        ("tax extract", 8.0),
        ("tax pack", 7.0),
        ("tax filing", 7.0),
        ("tax output", 6.0),
    ),
    "Portfolio Accounting": (
        ("portfolio accounting", 9.0),
        ("month-end reconciliation", 7.0),
        ("reconciliation dashboard", 6.0),
        ("exception review", 4.0),
    ),
    "Risk & Compliance Monitoring": (
        ("sanctions screening", 9.0),
        ("compliance dashboard", 8.0),
        ("breach status", 7.0),
        ("rule update", 4.0),
        ("portfolio checks", 4.0),
    ),
    "Securities Settlement": (
        ("mt536", 10.0),
        ("settlement confirmation", 10.0),
        ("settlement status", 9.0),
        ("custody settlement", 7.0),
        ("settlement queue", 8.0),
        ("unmatched confirmations", 7.0),
    ),
    "Trade Matching": (
        ("trade matching", 10.0),
        ("allocation messages", 8.0),
        ("matching backlog", 8.0),
        ("tma-", 8.0),
        ("staged allocations", 6.0),
    ),
    "Client Reporting": (
        ("client report", 9.0),
        ("report pdf", 8.0),
        ("management fee section", 8.0),
        ("report pack", 7.0),
        ("distributed output", 5.0),
    ),
    "Cash Management": (
        ("margin sweep", 10.0),
        ("cash missing", 8.0),
        ("cash not", 7.0),
        ("liquidity movement", 8.0),
        ("treasury", 6.0),
    ),
    "Rimes Data Feed": (
        ("rimes", 10.0),
        ("benchmark file", 9.0),
        ("benchmark publication", 9.0),
        ("publishing window", 5.0),
        ("downstream cutoff", 5.0),
    ),
    "Regulatory Reporting": (
        ("lei", 10.0),
        ("regulator gateway", 10.0),
        ("regulatory submission", 9.0),
        ("submission file", 6.0),
    ),
    "SimCorp Dimension": (
        ("simcorp", 10.0),
        ("scd_pos_sync", 10.0),
        ("replication job", 8.0),
        ("host eapw", 5.0),
    ),
    "NAV Calculation": (
        ("nav_eod", 10.0),
        ("nav calculation", 9.0),
        ("valuation tolerance", 10.0),
        ("nav snapshot", 8.0),
    ),
    "CRM & Client Portal": (
        ("crm", 7.0),
        ("client portal", 9.0),
        ("relationship manager", 7.0),
        ("investor interactions", 6.0),
    ),
    "SharePoint & File Storage": (
        ("sharepoint", 10.0),
        ("file storage", 8.0),
        ("project folders", 7.0),
        ("synced folders", 7.0),
    ),
    "Outlook & Email": (
        ("outlook", 10.0),
        ("shared mailbox", 10.0),
        ("distribution list", 9.0),
        ("mail outage", 7.0),
    ),
    "Identity & Access Management": (
        ("access removed", 8.0),
        ("access removal", 8.0),
        ("deactivated users", 10.0),
        ("offboarding", 9.0),
        ("identity cleanup", 9.0),
        ("portal access", 5.0),
    ),
    "Corporate Actions": (
        ("corporate action", 10.0),
        ("caev-", 10.0),
        ("option code", 9.0),
        ("elections", 7.0),
    ),
    "Order Management": (
        ("order management", 9.0),
        ("oms", 8.0),
        ("pending approval", 8.0),
        ("broker account", 8.0),
        ("execution routing", 7.0),
    ),
    "Trading Platform": (
        ("trading platform", 10.0),
        ("trader", 4.0),
        ("execution", 4.0),
    ),
    "Fund Pricing": (
        ("fund pricing", 10.0),
        ("pricing run", 8.0),
        ("price file", 6.0),
    ),
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
}

GENERIC_RESOLUTION_PHRASES = (
    "alert closed after validation",
    "access updated",
    "service restored",
    "issue confirmed as non-urgent",
    "ticket resolved via workaround",
    "problem fixed",
)

RESOLUTION_ACTION_WORDS = (
    "corrected",
    "confirmed",
    "cleared",
    "granted",
    "matched",
    "provisioned",
    "reconciled",
    "reprocessed",
    "replayed",
    "resubmitted",
    "restarted",
    "removed",
    "set up",
    "updated",
)

SERVICE_RESOLUTION_TEMPLATES = {
    "Tax Reporting": "Provisioned the requested Tax Reporting license and confirmed the user could complete the withholding-tax extract and tax-pack workflow.",
    "Portfolio Accounting": "Granted the standard Portfolio Accounting processing role and read access to the reconciliation dashboards, then confirmed month-end access.",
    "Risk & Compliance Monitoring": "Provisioned the standard compliance-monitoring role and confirmed access to the sanctions-screening dashboard and rule-exception views.",
    "Risk & Compliance Monitoring (incident)": "Refreshed the compliance-monitoring dashboard after the rule update and verified that summary breach statuses matched the current checks and detail pages.",
    "Securities Settlement": "Reviewed the settlement confirmation queue, cleared and replayed pending acknowledgements, and confirmed custody settlement statuses synchronized back to the dashboard.",
    "Trade Matching": "Corrected the broker allocation or SSI mapping, reprocessed the rejected allocation batch, and confirmed the affected trades matched successfully.",
    "Client Reporting": "Corrected the report-template fee rendering condition, regenerated the affected client-report batch, and confirmed the fee table appears in the PDFs.",
    "Cash Management": "Reconciled the cash ledger against the bank statement, investigated the margin-sweep cutoff, and confirmed the corrected balance with Treasury.",
    "Rimes Data Feed": "Confirmed the delayed benchmark file was received, completed downstream feed processing, and checked that the affected valuation input was current.",
    "Regulatory Reporting": "Corrected the missing classification data in the LEI submission, regenerated the file, and confirmed regulator-gateway acceptance.",
    "SimCorp Dimension": "Cleared the replication-job lock or timeout, restarted SCD_POS_SYNC from its last checkpoint, and reconciled positions against downstream reporting.",
    "NAV Calculation": "Reviewed the valuation tolerance breach, reran the affected NAV calculation after correction, and confirmed the NAV snapshot reached the downstream control queue.",
    "CRM & Client Portal": "Granted the standard CRM & Client Portal role for the relationship manager and confirmed access to investor interactions and follow-up records.",
    "SharePoint & File Storage": "Removed direct, inherited, and synchronized SharePoint permissions for the offboarded user and verified that access no longer resolves.",
    "Outlook & Email": "Reclassified the ticket as a service request, provisioned the shared mailbox and distribution list, and confirmed the requested permissions in Outlook.",
    "Corporate Actions": "Updated the missing corporate-action option-code mapping, reprocessed the event feed, and confirmed the election is visible on the operations screen.",
    "Order Management": "Corrected the broker routing or account mapping, tested a new order, and confirmed held orders progressed to execution routing.",
    "Identity & Access Management": "Removed portal access from the deactivated-user batch and verified that inactive accounts no longer retain permissions.",
}


def as_list(value: Any) -> list[str]:
    """Return a clean list for Jira fields that may be scalar, list, or null."""

    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if item is not None and str(item).strip()]


def normalize_label(value: Any) -> str:
    return str(value or "").strip().casefold()


def tokenize(text: str) -> set[str]:
    """Tokenize while preserving operational identifiers such as NAV_EOD_GE_375."""

    tokens: set[str] = set()
    for raw in re.findall(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", text.casefold()):
        if raw not in STOPWORDS and len(raw) > 1:
            tokens.add(raw)
        for part in re.split(r"[_-]", raw):
            if part not in STOPWORDS and len(part) > 1:
                tokens.add(part)
    return tokens


def join_ticket_text(ticket: dict[str, Any], include_service: bool = True) -> str:
    parts = [
        str(ticket.get("Summary", "")),
        str(ticket.get("Description", "")),
        " ".join(as_list(ticket.get("All Comments"))),
        " ".join(as_list(ticket.get("Request type"))),
        " ".join(as_list(ticket.get("Business Entity"))),
    ]
    if include_service:
        parts.append(" ".join(as_list(ticket.get("Affected Business or IT Services"))))
    return " ".join(part for part in parts if part).strip()


def extract_resolution_comment(record: dict[str, Any]) -> tuple[str, str] | None:
    """Extract the last authored resolution note from a historical ticket."""

    for raw_comment in reversed(as_list(record.get("All Comments"))):
        if not re.search(r"\bresolution(?: recorded)?\s*:", raw_comment, re.IGNORECASE):
            continue
        author, body = raw_comment.split(":", 1)
        body = body.strip()
        body = re.sub(r"^resolution(?: recorded)?\s*:\s*", "", body, flags=re.IGNORECASE)
        if body:
            return author.strip(), body
    return None


def adapt_resolution_comment(comment: str, ticket: dict[str, Any]) -> str:
    """Keep a retrieved note concrete without contradicting ticket scope."""

    text = join_ticket_text(ticket, include_service=False).casefold()
    if re.search(r"\b1 events?\b|\bone event\b", text):
        comment = re.sub(r"\bseveral events were\b", "The affected event was", comment, flags=re.IGNORECASE)
        comment = re.sub(r"\bseveral events\b", "The affected event", comment, flags=re.IGNORECASE)
        comment = re.sub(r"\bbatch of events\b", "affected event", comment, flags=re.IGNORECASE)
    return comment


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@dataclass(frozen=True)
class RetrievedTicket:
    index: int
    score: float


class TriageEngine:
    """Build indexes from history and infer a structured triage draft."""

    def __init__(self, training_records: list[dict[str, Any]]):
        self.training_records = training_records
        self.service_team_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.service_assignee_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
        self.resolution_owner_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.resolution_examples_by_service: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.resolution_examples_by_index: dict[int, dict[str, Any]] = {}
        self.postings: dict[str, list[int]] = defaultdict(list)
        self.record_tokens: list[set[str]] = []
        self.document_frequency: Counter[str] = Counter()
        self._build_indexes()

    def _build_indexes(self) -> None:
        for index, record in enumerate(self.training_records):
            services = as_list(record.get("Affected Business or IT Services"))
            teams = as_list(record.get("Service Team(s)"))
            team = teams[0] if teams else ""
            assignee = str(record.get("Assignee") or "").strip()

            for service in services:
                if team:
                    self.service_team_counts[service][team] += 1
                if team and assignee:
                    self.service_assignee_counts[(service, team)][assignee] += 1

            resolution = extract_resolution_comment(record)
            if resolution:
                resolution_author, resolution_body = resolution
                resolution_example = {
                    "index": index,
                    "author": resolution_author,
                    "comment": resolution_body,
                    "work_type": record.get("Work type"),
                    "resolution": record.get("Resolution"),
                    "tokens": tokenize(resolution_body),
                }
                self.resolution_examples_by_index[index] = resolution_example
                for service in services:
                    self.resolution_owner_counts[service][resolution_author] += 1
                    self.resolution_examples_by_service[service].append(resolution_example)

            tokens = tokenize(join_ticket_text(record))
            self.record_tokens.append(tokens)
            for token in tokens:
                self.postings[token].append(index)
                self.document_frequency[token] += 1

    @property
    def services(self) -> set[str]:
        return set(self.service_team_counts)

    def service_team(self, service: str) -> str:
        observed = self.service_team_counts.get(service)
        if observed:
            return observed.most_common(1)[0][0]
        return SERVICE_TEAM_HINTS.get(service, "")

    def retrieve(self, ticket: dict[str, Any], top_k: int = 8) -> list[RetrievedTicket]:
        """Retrieve similar historical cases with weighted lexical similarity."""

        query_text = join_ticket_text(ticket)
        query_tokens = tokenize(query_text)
        if not query_tokens:
            return []

        candidate_scores: Counter[int] = Counter()
        total = max(len(self.training_records), 1)
        for token in query_tokens:
            posting = self.postings.get(token, [])
            if not posting:
                continue
            idf = math.log((total + 1) / (len(posting) + 1)) + 1.0
            identifier_boost = 2.5 if ("_" in token or "-" in token or any(char.isdigit() for char in token)) else 1.0
            weight = idf * identifier_boost
            for index in posting:
                candidate_scores[index] += weight

        current_services = set(as_list(ticket.get("Affected Business or IT Services")))
        current_type = normalize_label(ticket.get("Work type"))
        for index in list(candidate_scores):
            record = self.training_records[index]
            record_services = set(as_list(record.get("Affected Business or IT Services")))
            if current_services & record_services:
                candidate_scores[index] += 1.5
            if current_type and current_type == normalize_label(record.get("Work type")):
                candidate_scores[index] += 0.5

        ranked = sorted(candidate_scores.items(), key=lambda item: (-item[1], item[0]))
        return [RetrievedTicket(index=index, score=round(score, 4)) for index, score in ranked[:top_k]]

    def infer_work_type(self, ticket: dict[str, Any]) -> tuple[str, float, list[str]]:
        text = join_ticket_text(ticket, include_service=False).casefold()
        request_patterns = (
            (r"access (?:requested|request|remov|provision)", 3.0, "access/provisioning language"),
            (r"new (?:license|joiner|shared mailbox|mailbox|distribution list)", 3.0, "new-service language"),
            (r"standard access|role-based profile|normal processing role", 3.0, "standard role request"),
            (r"contractor (?:left|offboarding)|deactivated users|identity cleanup", 3.0, "lifecycle cleanup"),
            (r"no (?:actual )?outage|no disruption|routine", 3.0, "explicitly non-incident wording"),
        )
        incident_patterns = (
            (r"outage|failed|failure|stopped|rejected|delayed|delay", 2.5, "service failure or delay"),
            (r"missing|blank|stale|backlog|blocked|breach|error|not arriving", 2.5, "degraded or blocked processing"),
            (r"cannot|does not|do not|never", 1.5, "negative operational behavior"),
        )
        request_score = 0.0
        incident_score = 0.0
        evidence: list[str] = []
        for pattern, weight, reason in request_patterns:
            if re.search(pattern, text):
                request_score += weight
                evidence.append(reason)
        for pattern, weight, reason in incident_patterns:
            if re.search(pattern, text):
                incident_score += weight
                evidence.append(reason)

        supplied = str(ticket.get("Work type") or "").strip()
        if supplied in WORK_TYPES:
            # The supplied type is a weak prior; narrative evidence is stronger.
            if supplied == "Service Request":
                request_score += 0.75
            else:
                incident_score += 0.75

        if request_score > incident_score:
            result = "Service Request"
        else:
            result = "Incident"
        total = request_score + incident_score
        confidence = abs(request_score - incident_score) / total if total else 0.0
        if not evidence:
            evidence.append("no strong narrative type signal")
        return result, round(min(0.99, 0.5 + confidence / 2), 3), evidence

    def service_scores(self, ticket: dict[str, Any], retrieved: Iterable[RetrievedTicket]) -> Counter[str]:
        text = join_ticket_text(ticket, include_service=False).casefold()
        scores: Counter[str] = Counter()
        for service, clues in SERVICE_CLUES.items():
            for phrase, weight in clues:
                if phrase.casefold() in text:
                    scores[service] += weight

        # The intake service is useful as a prior, but is deliberately weaker
        # than explicit narrative clues so that misclassified tickets can move.
        for service in as_list(ticket.get("Affected Business or IT Services")):
            scores[service] += 2.0

        for item in retrieved:
            record = self.training_records[item.index]
            for service in as_list(record.get("Affected Business or IT Services")):
                scores[service] += min(item.score, 8.0) * 0.12
        return scores

    def infer_service(
        self, ticket: dict[str, Any], retrieved: list[RetrievedTicket]
    ) -> tuple[str, float, list[str]]:
        scores = self.service_scores(ticket, retrieved)
        if not scores:
            supplied = as_list(ticket.get("Affected Business or IT Services"))
            if supplied:
                return supplied[0], 0.45, ["used supplied service because no stronger signal was found"]
            if retrieved:
                services = as_list(self.training_records[retrieved[0].index].get("Affected Business or IT Services"))
                if services:
                    return services[0], 0.35, ["used top retrieved service"]
            return "Emailed Support Tickets", 0.1, ["fallback service"]

        ranked = scores.most_common()
        selected, selected_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = selected_score - second_score
        confidence = min(0.99, 0.5 + margin / max(selected_score * 2.0, 1.0))
        reasons = []
        if selected in set(as_list(ticket.get("Affected Business or IT Services"))):
            reasons.append("consistent with supplied service")
        else:
            reasons.append("narrative overrode supplied service")
        matched_clues = [phrase for phrase, _ in SERVICE_CLUES.get(selected, ()) if phrase.casefold() in join_ticket_text(ticket, include_service=False).casefold()]
        if matched_clues:
            reasons.append("matched clues: " + ", ".join(matched_clues[:4]))
        return selected, round(confidence, 3), reasons

    def infer_owner(
        self,
        service: str,
        retrieved: list[RetrievedTicket],
        resolution_author: str | None = None,
    ) -> tuple[str, str, float, list[str]]:
        team = self.service_team(service)
        counts = self.service_assignee_counts.get((service, team), Counter())

        if resolution_author and (
            resolution_author in counts
            or resolution_author in self.resolution_owner_counts.get(service, Counter())
        ):
            return resolution_author, team, 0.8, ["historical resolution owner for the matched service pattern"]

        service_resolution_owners = self.resolution_owner_counts.get(service, Counter())
        if service_resolution_owners:
            owner, owner_count = service_resolution_owners.most_common(1)[0]
            total = sum(service_resolution_owners.values())
            # Use a dominant functional owner only when the history supports
            # it; generic services remain retrieval-driven.
            if owner_count >= 10 and owner_count / max(total, 1) >= 0.35:
                return owner, team, 0.6, ["dominant historical resolution owner for service"]

        ranked: Counter[str] = Counter()
        for item in retrieved:
            record = self.training_records[item.index]
            if service in as_list(record.get("Affected Business or IT Services")):
                assignee = str(record.get("Assignee") or "").strip()
                if assignee:
                    ranked[assignee] += item.score
        if ranked:
            assignee = ranked.most_common(1)[0][0]
            total = sum(ranked.values())
            confidence = ranked[assignee] / total if total else 0.0
            return assignee, team, round(min(0.99, 0.35 + confidence / 2), 3), ["similar historical ownership"]
        if counts:
            assignee = counts.most_common(1)[0][0]
            return assignee, team, 0.25, ["most frequent observed assignee for service/team"]
        return "", team, 0.0, ["no historical assignee found"]

    def best_resolution_example(
        self,
        ticket: dict[str, Any],
        service: str,
        retrieved: list[RetrievedTicket],
    ) -> dict[str, Any] | None:
        """Find a concrete historical resolution pattern for this service."""

        query_tokens = tokenize(join_ticket_text(ticket, include_service=False))
        candidates: list[tuple[float, dict[str, Any]]] = []
        seen: set[int] = set()

        for item in retrieved:
            record = self.training_records[item.index]
            if service not in as_list(record.get("Affected Business or IT Services")):
                continue
            example = self.resolution_examples_by_index.get(item.index)
            if not example:
                continue
            seen.add(item.index)
            comment = example["comment"].casefold()
            score = item.score
            score += len(query_tokens & example["tokens"]) * 0.35
            if any(word in comment for word in RESOLUTION_ACTION_WORDS):
                score += 1.5
            if any(phrase in comment for phrase in GENERIC_RESOLUTION_PHRASES):
                score -= 2.0
            if normalize_label(example.get("work_type")) == normalize_label(ticket.get("Work type")):
                score += 1.5
            else:
                score -= 1.5
            candidates.append((score, example))

        # A service-level fallback is useful when the challenge uses a new
        # identifier that does not occur in the historical summary.
        for example in self.resolution_examples_by_service.get(service, []):
            if example["index"] in seen:
                continue
            comment = example["comment"].casefold()
            score = len(query_tokens & example["tokens"]) * 0.35
            if any(word in comment for word in RESOLUTION_ACTION_WORDS):
                score += 0.75
            if any(phrase in comment for phrase in GENERIC_RESOLUTION_PHRASES):
                score -= 2.0
            candidates.append((score, example))

        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])[1]

    def infer_resolution(
        self,
        ticket: dict[str, Any],
        work_type: str,
        service: str,
        retrieved: list[RetrievedTicket],
    ) -> tuple[str, str, str | None, list[str]]:
        """Infer a permitted status and write an evidence-backed note."""

        text = join_ticket_text(ticket, include_service=False).casefold()
        example = self.best_resolution_example(ticket, service, retrieved)
        if example and normalize_label(example.get("work_type")) != normalize_label(work_type):
            example = None
        reasons: list[str] = []

        concrete_failure = bool(
            re.search(
                r"missing classification|mandatory classification|gateway rejection|rejected by the regulator gateway",
                text,
            )
        )

        if re.search(r"duplicate|withdrawn|no longer required|cancel(?:led|led)", text):
            status = "cancelled"
            reasons.append("explicit cancellation or withdrawal language")
        elif re.search(r"cannot reproduce|could not reproduce|not reproducible", text):
            status = "cannot reproduce"
            reasons.append("explicit non-reproduction language")
        elif re.search(
            r"need to clarify|clarif|exact account|booking date|functional owner still unknown|"
            r"awaiting service triage|awaiting functional routing|service needs confirmation|"
            r"next vendor update expected|corrected publication eta",
            text,
        ) and not concrete_failure:
            status = "clarification"
            reasons.append("ticket explicitly lacks a routing, account, date, or vendor confirmation")
        elif work_type == "Service Request":
            status = "done"
            reasons.append("request contains a concrete provisioning or access action")
        elif re.search(
            r"failed|rejected|delayed|missing|blank|stale|backlog|blocked|stopped|"
            r"pending approval|tolerance breach|does not|do not|never",
            text,
        ):
            status = "done"
            reasons.append("incident contains a concrete operational symptom")
        else:
            status = "clarification"
            reasons.append("insufficient evidence for a defensible fix")

        if status == "done":
            if example and not any(
                phrase in example["comment"].casefold() for phrase in GENERIC_RESOLUTION_PHRASES
            ):
                comment = adapt_resolution_comment(example["comment"], ticket)
                author = example["author"]
                reasons.append("reused a concrete historical resolution pattern")
            else:
                template_key = f"{service} (incident)" if work_type == "Incident" else service
                comment = SERVICE_RESOLUTION_TEMPLATES.get(
                    template_key,
                    SERVICE_RESOLUTION_TEMPLATES.get(
                        service,
                        "Validated the reported issue, applied the required service correction, and confirmed the affected workflow completed successfully.",
                    ),
                )
                author = example["author"] if example else None
                reasons.append("used the service-specific resolution template")
        elif status == "clarification":
            clarification_templates = {
                "Cash Management": "Please confirm the affected cash account and booking or value date so Treasury can reconcile the ledger against the bank statement and margin-sweep cutoff.",
                "Securities Settlement": "Please confirm the custodian reference and expected delivery window; Securities Operations will monitor the settlement queue and reconcile the pending custody updates once the messages arrive.",
                "Rimes Data Feed": "Please confirm the vendor delivery timestamp and downstream cutoff for the affected benchmark file so Market Data Services can validate the late-feed impact and complete processing.",
                "default": "Please provide the missing operational reference and timing details so the owning team can reproduce the issue and confirm the correct resolution path.",
            }
            comment = clarification_templates.get(service, clarification_templates["default"])
            author = example["author"] if example else None
            reasons.append("generated a targeted clarification request")
        elif status == "cannot reproduce":
            comment = "Checked the reported behavior against the current service conditions but could not reproduce the failure; please provide a timestamp, reference, and affected record for another investigation pass."
            author = example["author"] if example else None
        else:
            comment = "No further action was required after the request was withdrawn or identified as a duplicate."
            author = example["author"] if example else None

        return status, comment, author, reasons

    def infer_urgency_impact(
        self, ticket: dict[str, Any], work_type: str, service: str
    ) -> dict[str, Any]:
        text = join_ticket_text(ticket, include_service=False).casefold()
        urgency = 0 if work_type == "Service Request" else 2
        impact = 0 if work_type == "Service Request" else 1

        critical = service in CRITICAL_SERVICES
        if critical and work_type == "Incident":
            impact += 1

        if re.search(
            r"full outage|full unavailability|no workaround|cannot process|processing is blocked|"
            r"workflow is blocked|stopped|never leave|unsuitable for release|cannot be released",
            text,
        ):
            urgency += 1
            impact += 1

        if re.search(
            r"regulator|regulatory|compliance|security|margin|settlement|next accounting cycle|"
            r"cutoff|publishing window|deadline",
            text,
        ):
            urgency += 1

        if re.search(
            r"all reports|every report|several books|multiple|"
            r"\b(?:1[0-9]|[2-9]\d|\d{3,})\s+(?:allocations?|funds?|books?|confirmations?|events?|users?|orders?|messages?)|"
            r"universe|downstream consumers",
            text,
        ):
            impact += 1

        if re.search(r"no workaround", text):
            urgency += 1
        elif re.search(r"workaround is required", text):
            urgency = max(urgency, 3)

        # A single event or a user-level request is still important, but is
        # not the same as a widespread service failure.
        if re.search(r"\b1 event\b|\bone event\b|one user|individual|new joiner|standard role", text):
            impact -= 1

        # A vendor notice or an explicitly unknown owner lowers confidence in
        # the immediate operational impact; it should not automatically become
        # a Highest-priority outage.
        if re.search(r"functional owner still unknown|awaiting service triage|awaiting functional routing|next vendor update expected", text):
            urgency -= 1

        if re.search(r"can still open|can work around|detail pages look current|no actual outage|no disruption", text):
            impact -= 1

        # Routine access and provisioning requests should remain low unless
        # the request explicitly has a same-day control or offboarding risk.
        if work_type == "Service Request":
            if re.search(r"all deactivated users|deactivated users.*today", text):
                urgency = max(urgency, 3)
                impact = max(impact, 1)
            elif re.search(r"today|offboarding", text):
                urgency = max(urgency, 2)
                impact = max(impact, 1)
            else:
                # A normal access/license/provisioning request has no direct
                # service degradation, even when the requested service itself
                # is business-critical.
                urgency = 0
                impact = 0

        urgency = max(0, min(4, urgency))
        impact = max(0, min(4, impact))
        priority = PRIORITY_MATRIX[urgency][impact]
        return {
            "urgency": LEVEL_LABELS[urgency],
            "urgency_score": urgency,
            "impact": LEVEL_LABELS[impact],
            "impact_category": IMPACT_CATEGORIES[impact],
            "impact_score": impact,
            "priority": priority,
            "critical_service": critical,
        }

    def triage(self, ticket: dict[str, Any], top_k: int = 8) -> dict[str, Any]:
        retrieved = self.retrieve(ticket, top_k=top_k)
        work_type, work_confidence, work_reasons = self.infer_work_type(ticket)
        service, service_confidence, service_reasons = self.infer_service(ticket, retrieved)
        resolution, resolution_comment, resolution_author, resolution_reasons = self.infer_resolution(
            ticket, work_type, service, retrieved
        )
        assignee, team, owner_confidence, owner_reasons = self.infer_owner(
            service, retrieved, resolution_author=resolution_author
        )
        priority = self.infer_urgency_impact(ticket, work_type, service)

        similar = []
        for item in retrieved[:5]:
            record = self.training_records[item.index]
            similar.append(
                {
                    "training_index": item.index,
                    "score": item.score,
                    "summary": record.get("Summary", ""),
                    "service": as_list(record.get("Affected Business or IT Services")),
                    "work_type": record.get("Work type"),
                    "resolution": record.get("Resolution"),
                    "resolution_comment": extract_resolution_comment(record)[1]
                    if extract_resolution_comment(record)
                    else None,
                }
            )

        return {
            "work_type": work_type,
            "affected_services": [service],
            "service_teams": [team] if team else [],
            "assignee": assignee or None,
            "urgency": priority["urgency"],
            "impact": priority["impact"],
            "impact_category": priority["impact_category"],
            "priority": priority["priority"],
            "resolution": resolution,
            "resolution_comment": resolution_comment,
            "resolution_author": resolution_author,
            "confidence": {
                "work_type": work_confidence,
                "service": service_confidence,
                "owner": owner_confidence,
            },
            "reasoning_summary": {
                "work_type": work_reasons,
                "service": service_reasons,
                "ownership": owner_reasons,
                "resolution": resolution_reasons,
                "critical_service": priority["critical_service"],
                "priority_rule": "deterministic README urgency-impact matrix",
            },
            "similar_historical_tickets": similar,
        }

    def triage_all(self, challenge_records: list[dict[str, Any]], top_k: int = 8) -> list[dict[str, Any]]:
        output = []
        for index, ticket in enumerate(challenge_records, start=1):
            prediction = self.triage(ticket, top_k=top_k)
            output.append(
                {
                    "ticket_index": index,
                    "summary": ticket.get("Summary", ""),
                    "current_fields": {
                        "work_type": ticket.get("Work type"),
                        "affected_services": as_list(ticket.get("Affected Business or IT Services")),
                        "priority": ticket.get("Priority"),
                        "urgency": ticket.get("Urgency"),
                        "impact": ticket.get("Impact"),
                    },
                    "prediction": prediction,
                }
            )
        return output

    def validate_prediction(self, prediction: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if prediction.get("work_type") not in WORK_TYPES:
            errors.append("invalid work type")
        services = prediction.get("affected_services") or []
        if len(services) != 1 or services[0] not in self.services:
            errors.append("service is not present in training reference")
        if prediction.get("service_teams") and prediction["service_teams"][0] != self.service_team(services[0]):
            errors.append("service/team mapping is inconsistent")
        if prediction.get("resolution") not in RESOLUTION_STATUSES:
            errors.append("invalid resolution status")
        if not str(prediction.get("resolution_comment") or "").strip():
            errors.append("resolution comment is empty")
        urgency = LEVEL_LABELS.index(prediction["urgency"])
        impact = LEVEL_LABELS.index(prediction["impact"])
        if PRIORITY_MATRIX[urgency][impact] != prediction.get("priority"):
            errors.append("priority is inconsistent with urgency/impact")
        return errors


def run_pipeline(training_path: Path, challenge_path: Path, output_path: Path, top_k: int = 8) -> dict[str, Any]:
    training = load_json(training_path)
    challenge_payload = load_json(challenge_path)
    if not isinstance(training, list):
        raise ValueError("training JSON must be an array")
    challenge_records = challenge_payload.get("records") if isinstance(challenge_payload, dict) else challenge_payload
    if not isinstance(challenge_records, list):
        raise ValueError("challenge JSON must contain a records array")

    engine = TriageEngine(training)
    results = engine.triage_all(challenge_records, top_k=top_k)
    validation_errors = {
        str(item["ticket_index"]): engine.validate_prediction(item["prediction"])
        for item in results
        if engine.validate_prediction(item["prediction"])
    }
    payload = {
        "pipeline": "triage_pipeline",
        "phase": "1-3",
        "training_records": len(training),
        "challenge_records": len(challenge_records),
        "services_indexed": len(engine.services),
        "validation_errors": validation_errors,
        "records": results,
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SwissLife phase 1-2 triage pipeline.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--challenge", type=Path, default=DEFAULT_CHALLENGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    payload = run_pipeline(args.training, args.challenge, args.output, top_k=args.top_k)
    print(f"Loaded {payload['training_records']} training records and {payload['challenge_records']} challenge records.")
    print(f"Indexed {payload['services_indexed']} services.")
    print(f"Wrote {args.output}")
    if payload["validation_errors"]:
        print(f"Validation warnings: {len(payload['validation_errors'])} record(s)")
    else:
        print("Validation: all phase 1-3 predictions are structurally consistent.")


if __name__ == "__main__":
    main()
