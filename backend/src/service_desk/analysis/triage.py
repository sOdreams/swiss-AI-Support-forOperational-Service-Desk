"""Reviewable priority and routing, separate from retrieval and execution."""
from copy import deepcopy


RULE_VERSION = "swisslife-00fea7d-priority-v1"
RULE_SOURCE = "https://github.com/Swiss-ai-Weeks/SwissLife-2026/blob/00fea7dbe887454436297d5aa19865dea5553434/README.md"
URGENCIES = ["Critical", "High", "Medium", "Low", "Lowest"]
IMPACTS = ["Major / Widespread", "Significant / Large", "Moderate / Limited",
           "Minor / Localized", "No direct impact / Information"]
PRIORITY_MATRIX = [
    ["Highest", "Highest", "High", "Medium", "Medium"],
    ["Highest", "High", "High", "Medium", "Low"],
    ["High", "High", "Medium", "Low", "Low"],
    ["Medium", "Medium", "Low", "Low", "Lowest"],
    ["Medium", "Low", "Low", "Lowest", "Lowest"],
]
CRITICAL_SERVICES = {"Trading Platform", "Order Management", "Trade Matching", "Securities Settlement",
                     "Corporate Actions", "Fund Pricing", "NAV Calculation", "Portfolio Accounting",
                     "Cash Management", "Risk & Compliance Monitoring", "Regulatory Reporting",
                     "SimCorp Dimension", "Rimes Data Feed", "Client Reporting"}
NON_CRITICAL_SERVICES = {"Tax Reporting", "CRM & Client Portal", "Identity & Access Management",
                         "SharePoint & File Storage", "Outlook & Email", "Emailed Support Tickets"}
PRIORITY_GUIDANCE = {
    "urgency": dict(zip(URGENCIES, [
        "Immediate action for regulatory breach, security compromise or major outage; no workaround.",
        "Action within hours to avoid escalation; any workaround is difficult/time-consuming.",
        "Important soon, without immediate operational/regulatory threat; easy workaround available.",
        "Normal workflow without urgent escalation.",
        "Routine/informational with no operational or compliance effect.",
    ])),
    "impact": dict(zip(IMPACTS, [
        "Full unavailability of critical services supporting key operations, over two hours downtime.",
        "Partial unavailability of critical services, one or more business entities affected, or financial counterparts affected.",
        "Full unavailability of non-critical services, or up to one business entity affected.",
        "Partial unavailability of non-critical services, or individuals affected.",
        "No direct operational impact; informational/maintenance without degradation.",
    ])),
    "critical_services": sorted(CRITICAL_SERVICES),
    "non_critical_services": sorted(NON_CRITICAL_SERVICES),
}


def calculate_priority(urgency, impact):
    """Unknown dimensions stay unknown; there is no default low priority."""
    if urgency not in URGENCIES or impact not in IMPACTS:
        return None
    return PRIORITY_MATRIX[URGENCIES.index(urgency)][IMPACTS.index(impact)]


def build_triage(analysis, routing_catalog=None):
    """Pure downstream composition from trusted pipeline output and a catalogue."""
    facts = analysis.get("facts", {})
    clean = analysis.get("clean") or {}
    interpreted = clean.get("interpretation") or {}
    conflicts = analysis.get("conflicts", [])
    dimensions = {}
    for field, choices in (("urgency", URGENCIES), ("impact", IMPACTS)):
        ids = interpreted.get(field + "_evidence_ids", [])
        supported = clean.get("status") == "ready" and interpreted.get(field) in choices and ids and all(i in facts for i in ids)
        dimensions[field] = {"value": interpreted[field] if supported else None,
                             "evidence": [{"fact_id": i, **facts[i]} for i in ids] if supported else []}
    proposed = calculate_priority(dimensions["urgency"]["value"], dimensions["impact"]["value"])
    status = "unavailable" if clean.get("status") != "ready" else "needs_review" if conflicts else "suggested" if proposed else "needs_information"
    priority = {"status": status, **dimensions, "value": proposed if status == "suggested" else None,
                "proposed_value": proposed, "rule_version": RULE_VERSION, "rule_source": RULE_SOURCE,
                "reason": "Review the service disagreement before applying this priority." if conflicts else
                          "Priority is calculated from the cited urgency and impact using the challenge matrix." if proposed else
                          "Urgency or impact is not established; priority remains unknown.",
                "requires_review": True}

    filtered = analysis.get("filter") or {}
    service = filtered.get("service")
    usable = filtered.get("status") == "ready" and service and not conflicts
    catalogue = deepcopy((routing_catalog or {}).get(service, [])) if usable else []
    team = catalogue[0]["team"] if len(catalogue) == 1 else None
    routing_status = "needs_review" if conflicts or (filtered.get("status") == "ready" and not service) else (
        "unavailable" if not usable else "suggested" if team else "needs_information")
    reason = ("Review the service interpretation before proposing ownership." if routing_status == "needs_review" else
              "Routing evidence is unavailable." if routing_status == "unavailable" else
              "The interpreted service has one team in the historical catalogue; confirm current ownership." if team else
              "The historical catalogue has no unique team for this service; verify the service directory.")
    contributors = {}
    if usable:
        active = set(filtered.get("active_comment_ids", []))
        for comment in filtered.get("comments", []):
            if comment["id"] not in active or comment["status"] not in {"reference", "conditional"}:
                continue
            for source in comment["sources"]:
                for ref in source["examples"]:
                    author = ref.get("author")
                    if not author or service not in ref.get("services", []):
                        continue
                    person = contributors.setdefault(author, {"author": author, "evidence": []})
                    if not any(e["comment_id"] == comment["id"] for e in person["evidence"]):
                        person["evidence"].append({"comment_id": comment["id"], "text": comment["text"],
                            "condition": comment["condition"], "document_id": source["document_id"],
                            "original_rank": source["original_rank"], "row_index": ref["row_index"]})
    routing = {"status": routing_status, "service": service if usable else None, "team": team,
               "reason": reason, "service_evidence": deepcopy(filtered.get("service_evidence", [])) if usable else [],
               "catalogue_evidence": catalogue, "historical_contributors": list(contributors.values())[:3],
               "index_version": (analysis.get("retrieval") or {}).get("index_version"),
               "assignee": None, "assignment_authorized": False, "requires_review": True}
    return {"priority": priority, "routing": routing}
