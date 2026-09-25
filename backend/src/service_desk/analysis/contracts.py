"""Schemas and deterministic validation/materialization, without provider I/O."""
from copy import deepcopy


def obj(properties):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def string_ids(values, maximum=None):
    item = {"type": "string", "enum": list(values)} if values else {"type": "string"}
    schema = {"type": "array", "items": item}
    if maximum is not None:
        schema["maxItems"] = maximum
    if not values:
        schema["maxItems"] = 0
    return schema


TEXT = {"type": "string"}
STAGE = {"type": "string", "enum": ["request", "external_delivery", "internal_processing", "unknown"]}
SIGNAL_KINDS = ["last_known_good", "first_observed_failure", "change_event", "blocked_outcome",
                "scope", "workaround", "deadline", "constraint"]


def signals_schema(facts):
    cited = {**string_ids(facts, 2), "minItems": 1}
    observation = obj({"kind": {"type": "string", "enum": SIGNAL_KINDS},
                       "text": {"type": "string", "minLength": 1, "maxLength": 220}, "evidence_ids": cited})
    prerequisite = obj({"check": {"type": "string", "minLength": 1, "maxLength": 180},
                        "state": {"type": "string", "enum": ["satisfied", "missing", "contradicted"]},
                        "evidence_ids": cited})
    return obj({"observations": {"type": "array", "items": observation, "maxItems": 8},
                "prerequisites": {"type": "array", "items": prerequisite, "maxItems": 3}})


def clean_schema(facts, catalog):
    return obj({
        "service": {"type": ["string", "null"], "enum": [*catalog, None]},
        "service_evidence_ids": string_ids(facts),
        "work_type": {"type": ["string", "null"], "enum": ["Incident", "Service Request", None]},
        "work_type_evidence_ids": string_ids(facts),
        "title_conflict": {"type": "boolean"},
        "suggested_summary": {"type": ["string", "null"]},
        "title_evidence_ids": string_ids(facts),
        "questions": {"type": "array", "items": TEXT, "maxItems": 5}, "reason": TEXT,
    })


def filter_schema(facts, catalog, groups, comments):
    choice = obj({"id": {"type": "string", **({"enum": list(comments)} if comments else {})},
                  "status": {"type": "string", "enum": ["reference", "conditional", "uncertain"]},
                  "condition": TEXT, "evidence_ids": string_ids(facts), "reason": TEXT, "evidence_stage": STAGE})
    return obj({
        "service": {"type": ["string", "null"], "enum": [*catalog, None]},
        "service_evidence_ids": string_ids(facts),
        "observed_stage": STAGE, "stage_evidence_ids": string_ids(facts),
        "primary_ids": string_ids(groups, 10), "reserve_ids": string_ids(groups, 50),
        "comment_choices": {"type": "array", "items": choice, "maxItems": len(comments)},
        "signals": signals_schema(facts),
        "questions": {"type": "array", "items": TEXT, "maxItems": 5}, "reason": TEXT,
    })


def validate_clean(value, facts):
    errors = []
    for name in ("service", "work_type"):
        if value[name] is not None and not value[name + "_evidence_ids"]:
            errors.append(f"{name} requires current evidence")
    if value["title_conflict"]:
        if not value["suggested_summary"] or not any(facts[i]["source"] != "summary" for i in value["title_evidence_ids"]):
            errors.append("Title correction requires replacement text and body/comment evidence")
    elif value["suggested_summary"] is not None:
        errors.append("A replacement summary requires a title conflict")
    return errors


def validate_filter(value, groups, comments):
    errors = []
    signals = value["signals"]
    kinds = [s["kind"] for s in signals["observations"]]
    if len(kinds) != len(set(kinds)):
        errors.append("Use one observation per signal kind")
    checks = [p["check"].strip().casefold() for p in signals["prerequisites"]]
    if len(checks) != len(set(checks)):
        errors.append("Prerequisite checks must be unique")
    if any(not s["text"].strip() for s in signals["observations"]) or any(not c for c in checks):
        errors.append("Signals require nonempty observations and checks")
    primary, reserve = value["primary_ids"], value["reserve_ids"]
    if len(set(primary + reserve)) != len(primary + reserve):
        errors.append("Group selections must be unique and disjoint")
    if value["service"] is not None and not value["service_evidence_ids"]:
        errors.append("Service interpretation requires current evidence")
    if value["observed_stage"] != "unknown" and not value["stage_evidence_ids"]:
        errors.append("A known observed stage requires current evidence")
    for ident in primary:
        if value["service"] is None or value["service"] not in groups[ident]["services"]:
            errors.append(f"Primary {ident} does not match the supported service")
    seen = set()
    for c in value["comment_choices"]:
        if c["id"] in seen:
            errors.append("Duplicate comment selection")
        seen.add(c["id"])
        if c["status"] != "uncertain":
            if value["observed_stage"] == "unknown" or c["evidence_stage"] != value["observed_stage"]:
                errors.append(f"Comment {c['id']} has an unsupported/different failure stage; reserve as uncertain or omit it")
            if value["service"] is None or value["service"] not in comments[c["id"]]["services"]:
                errors.append(f"Comment {c['id']} has no source in the supported service")
            if not c["evidence_ids"]:
                errors.append("Active comments require current evidence")
        if (c["status"] == "conditional") != bool(c["condition"].strip()):
            errors.append("Only conditional comments require a concrete condition")
    return errors


def quotes(ids, facts):
    return [{"fact_id": i, **facts[i]} for i in ids]


def clean_result(ticket, value, facts):
    fields = []
    comparisons = [
        ("affected_business_or_it_services", list(ticket.current_services),
         [value["service"]] if value["service"] else None, value["service_evidence_ids"]),
        ("work_type", ticket.current_work_type, value["work_type"], value["work_type_evidence_ids"]),
        ("summary", ticket.summary,
         value["suggested_summary"] if value["title_conflict"] else ticket.summary, value["title_evidence_ids"]),
    ]
    for name, current, suggested, evidence in comparisons:
        state = ("needs_clarification" if suggested is None else "keep" if current == suggested else
                 "propose_completion" if not current else "propose_correction")
        fields.append({"field": name, "current": current, "suggested": suggested, "state": state,
                       "evidence": quotes(evidence, facts)})
    return {"status": "ready", "fields": fields, "questions": value["questions"],
            "reason": value["reason"], "interpretation": value}


def filter_result(value, originals, comments, facts):
    """Server attaches exact IDs/ranks/text. Model omission never destroys data."""
    primary = set(value["primary_ids"]) if value else set()
    reserve = set(value["reserve_ids"]) if value else set(originals)
    choices = {c["id"]: c for c in value["comment_choices"]} if value else {}
    candidates, rank = [], 0
    for alias, hit in originals.items():
        selected = alias in primary
        rank += int(selected)
        candidates.append({**deepcopy(hit), "original_rank": hit["rank"],
                           "filter_rank": rank if selected else None,
                           "role": "primary" if selected else "reserve" if alias in reserve else "not_selected"})
    comment_results = []
    for cid, comment in comments.items():
        c = choices.get(cid)
        comment_results.append({**deepcopy(comment), "status": c["status"] if c else ("not_selected" if value else "uncertain"),
            "condition": c["condition"] if c else "", "reason": c["reason"] if c else "No active relevance selection.",
            "evidence_stage": c["evidence_stage"] if c else None,
            "evidence": quotes(c["evidence_ids"], facts) if c else [],
            "requires_current_verification": True, "execution_authorized": False})
    return {"status": "ready" if value else "unfiltered_fallback", "candidates": candidates,
            "comments": comment_results, "primary_document_ids": [g["document_id"] for g in candidates if g["role"] == "primary"],
            "active_comment_ids": [c["id"] for c in comment_results if c["status"] in {"reference", "conditional"}],
            "questions": value["questions"] if value else [], "reason": value["reason"] if value else "Filter unavailable; original retrieval retained.",
            "service": value["service"] if value else None,
            "observed_stage": value["observed_stage"] if value else None,
            "stage_evidence": quotes(value["stage_evidence_ids"], facts) if value else [],
            "signals": {key: [{**deepcopy(item), "evidence": quotes(item["evidence_ids"], facts)}
                              for item in value["signals"][key]] if value else []
                        for key in ("observations", "prerequisites")}}
